from __future__ import annotations

"""Bounded behavioral perturbation layer for synthetic contact matrices."""

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize

import contact_matrix_fr.metrics as metrics


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class BehavioralState:
    adherence_level: float
    risk_perception: float
    trust_in_authorities: float
    policy_regime: str


@dataclass(frozen=True, slots=True)
class BehavioralCalibrationResult:
    parameters: dict[str, float]
    optimization_success: bool
    optimization_message: str
    objective_value: float
    iterations: int
    train_metrics: dict[str, float]


class BehavioralLayer:
    """Apply bounded behavioral adjustments to an age-contact matrix.

    The layer keeps the original design philosophy, but exposes a compact set of
    calibratable parameters so the behavioral multipliers can be fitted against
    observed French time-series data instead of being only hand tuned.
    """

    def __init__(
        self,
        base_matrix: Array,
        behavioral_states: Iterable[BehavioralState],
        *,
        age_axis: Array | None = None,
        setting_templates: Mapping[str, Array] | None = None,
        dry_run: bool = False,
        parameters: Mapping[str, float] | None = None,
    ) -> None:
        self.base_matrix = _validate_square_matrix(base_matrix)
        self.dimension = int(self.base_matrix.shape[0])
        self.age_axis = _make_age_axis(self.dimension) if age_axis is None else np.asarray(age_axis, dtype=float)
        if self.age_axis.shape != (self.dimension,):
            raise ValueError("age_axis must have one entry per matrix row")

        states = tuple(behavioral_states)
        if not states:
            raise ValueError("at least one behavioral state is required")
        self.behavioral_states = states
        self.dry_run = bool(dry_run)

        if setting_templates is None:
            self.setting_templates = self._derive_setting_templates(self.base_matrix)
        else:
            self.setting_templates = {
                name: _validate_square_matrix(template) for name, template in setting_templates.items()
            }
        self._ensure_template_coverage()
        self.parameters = self.default_parameters()
        if parameters:
            self.parameters.update({str(key): float(value) for key, value in parameters.items()})

    @staticmethod
    def default_parameters() -> dict[str, float]:
        return {
            "home_risk_gain": 0.30,
            "home_adherence_gain": 0.10,
            "school_response_gain": 0.50,
            "work_response_gain": 0.42,
            "other_response_gain": 0.55,
            "school_trust_penalty": 0.10,
            "work_trust_penalty": 0.06,
            "other_adherence_penalty": 0.08,
            "policy_mask_scale": 1.00,
            "policy_confinement_scale": 1.00,
            "policy_relaxation_scale": 1.00,
            "prevention_weight_adherence": 0.50,
            "prevention_weight_risk": 0.30,
            "prevention_weight_trust": 0.20,
            "policy_bonus_baseline": -0.02,
            "policy_bonus_mask_mandate": 0.015,
            "policy_bonus_confinement": 0.03,
            "policy_bonus_risk_relaxation": -0.01,
        }

    def apply(self, state: BehavioralState | None = None) -> Array:
        effective_state = state if state is not None else self.aggregate_state()
        response = self._behavioral_response(effective_state)
        policy_shift = self._policy_shift(effective_state.policy_regime)

        adjusted_components: dict[str, Array] = {}
        for setting, template in self.setting_templates.items():
            setting_multiplier = self._setting_multiplier(setting, response, effective_state)
            policy_multiplier = policy_shift.get(setting, 1.0)
            adjusted_components[setting] = template * setting_multiplier * policy_multiplier

        total = np.zeros_like(self.base_matrix)
        for component in adjusted_components.values():
            total = total + component

        total = 0.5 * (total + total.T)
        return np.clip(total, a_min=0.0, a_max=None)

    def prevention_score(self, state: BehavioralState) -> float:
        weights = self.parameters
        raw_score = (
            weights["prevention_weight_adherence"] * _clip01(state.adherence_level)
            + weights["prevention_weight_risk"] * _clip01(state.risk_perception)
            + weights["prevention_weight_trust"] * _clip01(state.trust_in_authorities)
        )
        bonus_key = f"policy_bonus_{str(state.policy_regime).strip().lower()}"
        policy_bonus = float(weights.get(bonus_key, 0.0))
        return float(np.clip(raw_score + policy_bonus, 0.0, 1.0))

    def contact_ratio(self, state: BehavioralState, participant_weights: Array, base_contact_level: float) -> float:
        adjusted = self.apply(state)
        row_sums = np.asarray(adjusted, dtype=float).sum(axis=1)
        normalized_weights = np.asarray(participant_weights, dtype=float)
        normalized_weights = normalized_weights / np.clip(normalized_weights.sum(), a_min=1.0, a_max=None)
        adjusted_level = float(np.dot(row_sums, normalized_weights))
        return float(adjusted_level / max(float(base_contact_level), 1e-9))

    def calibrate(
        self,
        *,
        prevention_states: Sequence[BehavioralState],
        prevention_targets: Sequence[float],
        contact_states: Sequence[BehavioralState],
        contact_targets: Sequence[float],
        participant_weights: Sequence[float],
        base_contact_level: float,
        regularization_strength: float = 0.01,
        maxiter: int = 2000,
    ) -> BehavioralCalibrationResult:
        prevention_targets_arr = np.asarray(prevention_targets, dtype=float)
        contact_targets_arr = np.asarray(contact_targets, dtype=float)
        if len(prevention_states) != prevention_targets_arr.size:
            raise ValueError("prevention states and targets must have matching lengths")
        if len(contact_states) != contact_targets_arr.size:
            raise ValueError("contact states and targets must have matching lengths")

        parameter_names = [
            "home_risk_gain",
            "home_adherence_gain",
            "school_response_gain",
            "work_response_gain",
            "other_response_gain",
            "school_trust_penalty",
            "work_trust_penalty",
            "other_adherence_penalty",
            "policy_mask_scale",
            "policy_confinement_scale",
            "policy_relaxation_scale",
            "prevention_weight_adherence",
            "prevention_weight_risk",
            "prevention_weight_trust",
            "policy_bonus_baseline",
            "policy_bonus_mask_mandate",
            "policy_bonus_confinement",
            "policy_bonus_risk_relaxation",
        ]
        bounds = {
            "home_risk_gain": (0.0, 0.8),
            "home_adherence_gain": (0.0, 0.4),
            "school_response_gain": (0.0, 1.0),
            "work_response_gain": (0.0, 1.0),
            "other_response_gain": (0.0, 1.0),
            "school_trust_penalty": (0.0, 0.4),
            "work_trust_penalty": (0.0, 0.4),
            "other_adherence_penalty": (0.0, 0.4),
            "policy_mask_scale": (0.3, 1.8),
            "policy_confinement_scale": (0.3, 2.2),
            "policy_relaxation_scale": (0.0, 1.8),
            "prevention_weight_adherence": (0.0, 1.0),
            "prevention_weight_risk": (0.0, 1.0),
            "prevention_weight_trust": (0.0, 1.0),
            "policy_bonus_baseline": (-0.10, 0.10),
            "policy_bonus_mask_mandate": (-0.10, 0.10),
            "policy_bonus_confinement": (-0.10, 0.10),
            "policy_bonus_risk_relaxation": (-0.10, 0.10),
        }
        x0 = np.array([self.parameters[name] for name in parameter_names], dtype=float)

        def unpack(x: Array) -> dict[str, float]:
            params = dict(self.parameters)
            params.update({name: float(value) for name, value in zip(parameter_names, x, strict=True)})
            return params

        participant_weights_arr = np.asarray(participant_weights, dtype=float)

        def objective(x: Array) -> float:
            params = unpack(x)
            candidate = BehavioralLayer(
                self.base_matrix,
                self.behavioral_states,
                age_axis=self.age_axis,
                setting_templates=self.setting_templates,
                dry_run=self.dry_run,
                parameters=params,
            )
            predicted_prevention = np.array([candidate.prevention_score(state) for state in prevention_states], dtype=float)
            predicted_contacts = np.array(
                [candidate.contact_ratio(state, participant_weights_arr, base_contact_level) for state in contact_states],
                dtype=float,
            )
            prevention_mae = metrics.series_mae(predicted_prevention, prevention_targets_arr)
            contact_mae = metrics.series_mae(predicted_contacts, contact_targets_arr)
            weight_sum = (
                params["prevention_weight_adherence"]
                + params["prevention_weight_risk"]
                + params["prevention_weight_trust"]
            )
            weight_penalty = (weight_sum - 1.0) ** 2
            regularization = float(np.mean((x - x0) ** 2))
            return float(prevention_mae + contact_mae + 0.5 * weight_penalty + regularization_strength * regularization)

        result = minimize(
            objective,
            x0=x0,
            method="Powell",
            bounds=[bounds[name] for name in parameter_names],
            options={"maxiter": int(maxiter), "xtol": 1e-5, "ftol": 1e-7},
        )
        calibrated = unpack(np.asarray(result.x, dtype=float))
        self.parameters.update(calibrated)

        train_prevention = np.array([self.prevention_score(state) for state in prevention_states], dtype=float)
        train_contacts = np.array(
            [self.contact_ratio(state, participant_weights_arr, base_contact_level) for state in contact_states],
            dtype=float,
        )
        train_metrics = {
            "prevention_mae": float(metrics.series_mae(train_prevention, prevention_targets_arr)),
            "prevention_direction_agreement": float(metrics.trend_direction_agreement(train_prevention, prevention_targets_arr)),
            "contact_mae": float(metrics.series_mae(train_contacts, contact_targets_arr)),
            "contact_direction_agreement": float(metrics.trend_direction_agreement(train_contacts, contact_targets_arr)),
        }
        return BehavioralCalibrationResult(
            parameters=calibrated,
            optimization_success=bool(result.success),
            optimization_message=str(result.message),
            objective_value=float(result.fun),
            iterations=int(getattr(result, "nit", 0) or 0),
            train_metrics=train_metrics,
        )

    def evolve_states(self, steps: int = 1, seed: int | None = None) -> list[BehavioralState]:
        rng = np.random.default_rng(seed)
        states = list(self.behavioral_states)
        for _ in range(max(steps, 0)):
            states = [self._transition_state(state, rng) for state in states]
        return states

    def generate_scenarios(self, scenario_count: int = 3, seed: int | None = None) -> list[dict[str, object]]:
        rng = np.random.default_rng(seed)
        scenarios: list[dict[str, object]] = []
        regimes = ["baseline", "mask_mandate", "confinement", "risk_relaxation"]

        for idx in range(max(scenario_count, 1)):
            if self.dry_run:
                state = BehavioralState(
                    adherence_level=float(np.clip(0.45 + 0.08 * idx, 0.0, 1.0)),
                    risk_perception=float(np.clip(0.40 + 0.06 * idx, 0.0, 1.0)),
                    trust_in_authorities=float(np.clip(0.55 + 0.04 * idx, 0.0, 1.0)),
                    policy_regime=regimes[idx % len(regimes)],
                )
            else:
                state = BehavioralState(
                    adherence_level=float(rng.uniform(0.25, 0.90)),
                    risk_perception=float(rng.uniform(0.20, 0.95)),
                    trust_in_authorities=float(rng.uniform(0.30, 0.95)),
                    policy_regime=regimes[int(rng.integers(0, len(regimes)))],
                )
            matrix = self.apply(state)
            scenarios.append(
                {
                    "name": f"scenario_{idx + 1}",
                    "state": {
                        "adherence_level": state.adherence_level,
                        "risk_perception": state.risk_perception,
                        "trust_in_authorities": state.trust_in_authorities,
                        "policy_regime": state.policy_regime,
                    },
                    "matrix": matrix,
                }
            )
        return scenarios

    def aggregate_state(self) -> BehavioralState:
        adherence = float(np.mean([state.adherence_level for state in self.behavioral_states]))
        risk = float(np.mean([state.risk_perception for state in self.behavioral_states]))
        trust = float(np.mean([state.trust_in_authorities for state in self.behavioral_states]))
        regime = max(
            {state.policy_regime for state in self.behavioral_states},
            key=lambda item: sum(1 for state in self.behavioral_states if state.policy_regime == item),
        )
        return BehavioralState(adherence, risk, trust, regime)

    def _derive_setting_templates(self, matrix: Array) -> dict[str, Array]:
        age = self.age_axis
        child = _window(age, 0.0, 17.0)
        student = _window(age, 5.0, 22.0)
        worker = _window(age, 18.0, 64.0)
        senior = _window(age, 65.0, 85.0)
        universal = np.ones_like(age, dtype=float)

        home_weight = 0.34 * _band_matrix(universal, width=1.8)
        home_weight += 0.40 * (_outer(child, worker) + _outer(worker, child))
        home_weight += 0.18 * (_outer(child, senior) + _outer(senior, child))
        home_weight += 0.08 * _band_matrix(senior + 0.4 * worker, width=2.1)

        school_weight = 0.82 * _band_matrix(student, width=1.2)
        school_weight += 0.18 * (_outer(student, worker) + _outer(worker, student))

        work_weight = 0.88 * _band_matrix(worker, width=2.5)
        work_weight += 0.12 * (_outer(worker, senior) + _outer(senior, worker))

        other_weight = 0.55 * np.outer(universal, universal)
        other_weight += 0.45 * _band_matrix(universal, width=4.0)

        weights = {
            "home": _normalize_matrix(home_weight),
            "school": _normalize_matrix(school_weight),
            "work": _normalize_matrix(work_weight),
            "other": _normalize_matrix(other_weight),
        }

        total_weight = np.zeros_like(matrix)
        for weight in weights.values():
            total_weight = total_weight + weight
        total_weight = np.clip(total_weight, a_min=1e-9, a_max=None)

        return {name: matrix * (weight / total_weight) for name, weight in weights.items()}

    def _ensure_template_coverage(self) -> None:
        required = {"home", "school", "work", "other"}
        missing = required.difference(self.setting_templates)
        if missing:
            raise ValueError(f"missing setting templates: {sorted(missing)}")

    def _behavioral_response(self, state: BehavioralState) -> float:
        adherence = _clip01(state.adherence_level)
        risk = _clip01(state.risk_perception)
        trust = _clip01(state.trust_in_authorities)
        return float(np.clip(0.50 * adherence + 0.30 * risk + 0.20 * trust, 0.0, 1.0))

    def _setting_multiplier(self, setting: str, response: float, state: BehavioralState) -> float:
        adherence = _clip01(state.adherence_level)
        risk = _clip01(state.risk_perception)
        trust = _clip01(state.trust_in_authorities)
        p = self.parameters

        if setting == "home":
            value = 0.95 + p["home_risk_gain"] * (risk - 0.5) - p["home_adherence_gain"] * (adherence - 0.5)
            return float(np.clip(value, 0.75, 1.20))
        if setting == "school":
            value = 1.05 - p["school_response_gain"] * response + p["school_trust_penalty"] * (1.0 - trust)
            return float(np.clip(value, 0.45, 1.10))
        if setting == "work":
            value = 1.00 - p["work_response_gain"] * response + p["work_trust_penalty"] * (1.0 - trust)
            return float(np.clip(value, 0.50, 1.10))
        if setting == "other":
            value = 1.00 - p["other_response_gain"] * response + p["other_adherence_penalty"] * (1.0 - adherence)
            return float(np.clip(value, 0.35, 1.10))
        raise ValueError(f"unsupported setting: {setting}")

    def _policy_shift(self, regime: str) -> dict[str, float]:
        policy = str(regime).strip().lower()
        if policy == "baseline":
            return {"home": 1.00, "school": 1.00, "work": 1.00, "other": 1.00}

        default = {
            "mask_mandate": {"home": 1.00, "school": 0.96, "work": 0.95, "other": 0.92},
            "confinement": {"home": 1.14, "school": 0.35, "work": 0.48, "other": 0.38},
            "risk_relaxation": {"home": 0.97, "school": 1.04, "work": 1.03, "other": 1.08},
        }
        scale_key = {
            "mask_mandate": "policy_mask_scale",
            "confinement": "policy_confinement_scale",
            "risk_relaxation": "policy_relaxation_scale",
        }.get(policy)
        if scale_key is None or policy not in default:
            return {"home": 1.00, "school": 1.00, "work": 1.00, "other": 1.00}

        scale = float(self.parameters[scale_key])
        return {
            setting: float(np.clip(1.0 + scale * (value - 1.0), 0.15, 1.35))
            for setting, value in default[policy].items()
        }

    def _transition_state(self, state: BehavioralState, rng: np.random.Generator) -> BehavioralState:
        regime = state.policy_regime.strip().lower()
        transition_noise = float(rng.normal(0.0, 0.05))
        policy_pressure = {
            "baseline": (0.00, 0.00, 0.00),
            "mask_mandate": (0.04, 0.03, 0.02),
            "confinement": (0.08, 0.07, -0.02),
            "risk_relaxation": (-0.05, -0.06, -0.03),
        }.get(regime, (0.0, 0.0, 0.0))

        adherence = _clip01(state.adherence_level + 0.15 * (state.risk_perception - 0.5) + policy_pressure[0] + transition_noise)
        risk = _clip01(0.70 * state.risk_perception + 0.20 * state.adherence_level + policy_pressure[1] + float(rng.normal(0.0, 0.04)))
        trust = _clip01(0.80 * state.trust_in_authorities + policy_pressure[2] + float(rng.normal(0.0, 0.03)))

        next_regime = regime
        if regime == "baseline" and risk > 0.75 and adherence > 0.65:
            next_regime = "mask_mandate"
        elif regime == "mask_mandate" and risk > 0.82:
            next_regime = "confinement"
        elif regime == "confinement" and trust < 0.35:
            next_regime = "risk_relaxation"
        elif regime == "risk_relaxation" and risk > 0.70:
            next_regime = "baseline"

        return BehavioralState(adherence, risk, trust, next_regime)


def _validate_square_matrix(matrix: Array) -> Array:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("matrix must be a square two-dimensional array")
    return np.clip(arr, a_min=0.0, a_max=None)


def _make_age_axis(size: int) -> Array:
    if size <= 0:
        raise ValueError("size must be positive")
    return np.linspace(0.0, 85.0, num=size, dtype=float)


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _window(age_axis: Array, lower: float, upper: float) -> Array:
    mask = ((age_axis >= lower) & (age_axis <= upper)).astype(float)
    if mask.size <= 2:
        return mask
    kernel = np.array([0.25, 0.50, 0.25], dtype=float)
    padded = np.pad(mask, pad_width=1, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _band_matrix(profile: Array, width: float) -> Array:
    profile = np.asarray(profile, dtype=float)
    idx = np.arange(profile.size, dtype=float)
    distance = np.abs(idx[:, None] - idx[None, :])
    band = np.exp(-(distance**2) / max(2.0 * width**2, 1e-9))
    return np.outer(profile, profile) * band


def _outer(left: Array, right: Array) -> Array:
    return np.outer(np.asarray(left, dtype=float), np.asarray(right, dtype=float))


def _normalize_matrix(matrix: Array) -> Array:
    arr = np.asarray(matrix, dtype=float)
    arr = 0.5 * (arr + arr.T)
    total = float(arr.sum())
    if total <= 0.0:
        return np.zeros_like(arr)
    return arr / total
