"""Run experiment exp003: time-series validation of the behavioral layer."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import traceback
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
VENDOR_ROOT = REPO_ROOT / ".vendor"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from contact_matrix_fr.baselines import BaselineBuilder  # noqa: E402
from contact_matrix_fr.behavioral_layer import BehavioralLayer, BehavioralState  # noqa: E402
import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.time_series_loader import load_time_series_bundle  # noqa: E402
from run_exp001 import load_real_reference_inputs  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp003_time_series_behavioral.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp003_results.json"
PREVENTIVE_FIGURE_PATH = REPO_ROOT / "manuscript" / "figures" / "exp003_preventive_behavior_timeseries.png"
CONTACT_FIGURE_PATH = REPO_ROOT / "manuscript" / "figures" / "exp003_contact_changes_periods.png"
DOWNLOAD_SCRIPT = REPO_ROOT / "scripts" / "download_time_series_data.py"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def ensure_time_series_inputs() -> None:
    subprocess.run([sys.executable, str(DOWNLOAD_SCRIPT)], cwd=REPO_ROOT, check=True)


def load_base_reference() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    builder = BaselineBuilder()
    inputs, reference, reference_payload = load_real_reference_inputs()
    base_matrix = builder.household_rule_based(inputs).total_matrix
    participant_counts = np.asarray(reference_payload["metadata"]["participant_age_counts"], dtype=float)
    return base_matrix, participant_counts, reference, reference_payload


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    ensure_time_series_inputs()
    bundle = load_time_series_bundle(REPO_ROOT / "data" / "interim")
    base_matrix, participant_counts, _, reference_payload = load_base_reference()
    base_contact_level = weighted_mean_contacts(base_matrix, participant_counts)

    simulation_cfg = dict(config["simulation"])
    initial_state_cfg = dict(simulation_cfg["initial_state"])
    initial_state = BehavioralState(
        adherence_level=float(initial_state_cfg["adherence_level"]),
        risk_perception=float(initial_state_cfg["risk_perception"]),
        trust_in_authorities=float(initial_state_cfg["trust_in_authorities"]),
        policy_regime=str(initial_state_cfg["policy_regime"]),
    )

    policy_timeline = bundle["policy_timeline"]
    weekly_dates, sampled_states = simulate_states(simulation_cfg, policy_timeline, initial_state)

    coviprev_dates = [datetime.fromisoformat(wave.midpoint_date).date() for wave in bundle["coviprev"]]
    observed_prevention = np.asarray(bundle["coviprev_observed_prevention"], dtype=float)
    predicted_prevention = np.asarray(
        [prevention_score(sample_state(date_value, weekly_dates, sampled_states), simulation_cfg) for date_value in coviprev_dates],
        dtype=float,
    )

    socialcov_dates = [datetime.fromisoformat(period.representative_date).date() for period in bundle["socialcov"]]
    observed_contacts = np.asarray(bundle["socialcov_observed_relative_contacts"], dtype=float)
    predicted_contacts = np.asarray(
        [
            contact_ratio_for_state(
                sample_state(date_value, weekly_dates, sampled_states),
                base_matrix,
                participant_counts,
                base_contact_level,
            )
            for date_value in socialcov_dates
        ],
        dtype=float,
    )

    static_prevention = np.full_like(observed_prevention, float(config["comparison"]["static_prevention_level"]))
    static_contacts = np.full_like(observed_contacts, float(config["comparison"]["static_contact_level"]))

    preventive_metrics = compute_series_metrics(predicted_prevention, observed_prevention)
    preventive_static_metrics = compute_series_metrics(static_prevention, observed_prevention)
    contact_metrics = compute_series_metrics(predicted_contacts, observed_contacts)
    contact_static_metrics = compute_series_metrics(static_contacts, observed_contacts)

    payload = {
        "experiment_name": str(config.get("experiment_name", "exp003_time_series_behavioral")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "reference": reference_payload["metadata"],
        "sources": {
            "coviprev": "data.gouv.fr public workbook, national France sheet, waves 17-28",
            "socialcov": "Zenodo record 10.5281/zenodo.13834596, ordered matrices Mat1-Mat6",
            "policy_timeline": "Vie publique chronology of French COVID-19 restrictions",
        },
        "limitations": [
            "CoviPrev risk perception is not observed directly in the downloaded workbook and is therefore modeled indirectly from policy pressure and fatigue.",
            "The SocialCov survey windows are now aligned to the date ranges shown in Fig. 1A of the published paper, but each period is still summarized by a single midpoint date when sampling the simulated state trajectory.",
            "The baseline contact matrix is static and calibrated on COMES-F age structure, so exp003 evaluates relative temporal responsiveness rather than absolute contact counts.",
        ],
        "base_contact_level": base_contact_level,
        "preventive_behavior": {
            "observed": series_to_records(bundle["coviprev"], observed_prevention, predicted_prevention, static_prevention, field_name="wave"),
            "metrics_behavioral": preventive_metrics,
            "metrics_static": preventive_static_metrics,
        },
        "contact_changes": {
            "observed": series_to_records(bundle["socialcov"], observed_contacts, predicted_contacts, static_contacts, field_name="period_id"),
            "metrics_behavioral": contact_metrics,
            "metrics_static": contact_static_metrics,
        },
        "assessment": build_assessment(preventive_metrics, preventive_static_metrics, contact_metrics, contact_static_metrics),
    }

    write_json(payload, OUTPUT_PATH)
    generate_figures(bundle, observed_prevention, predicted_prevention, static_prevention, observed_contacts, predicted_contacts, static_contacts)
    return payload


def simulate_states(
    simulation_cfg: dict[str, Any],
    policy_timeline: list[Any],
    initial_state: BehavioralState,
) -> tuple[list[date], list[BehavioralState]]:
    start_date = date.fromisoformat(str(simulation_cfg["start_date"]))
    end_date = date.fromisoformat(str(simulation_cfg["end_date"]))
    step_days = int(simulation_cfg.get("step_days", 7))
    adaptation_rate = float(simulation_cfg["adaptation_rate"])
    adherence_fatigue = float(simulation_cfg["adherence_fatigue_per_step"])
    risk_fatigue = float(simulation_cfg["risk_fatigue_per_step"])
    trust_fatigue = float(simulation_cfg["trust_fatigue_per_step"])
    policy_targets = {str(key): dict(value) for key, value in dict(simulation_cfg["policy_targets"]).items()}

    dates: list[date] = []
    states: list[BehavioralState] = []
    current_state = initial_state
    current_date = start_date
    step_index = 0
    while current_date <= end_date:
        regime = regime_at(current_date, policy_timeline)
        current_state = advance_state(
            current_state,
            regime,
            policy_targets,
            adaptation_rate,
            adherence_fatigue,
            risk_fatigue,
            trust_fatigue,
        )
        dates.append(current_date)
        states.append(current_state)
        current_date += timedelta(days=step_days)
        step_index += 1
    return dates, states


def regime_at(value: date, policy_timeline: list[Any]) -> str:
    for period in policy_timeline:
        start = date.fromisoformat(period.start_date)
        end = date.fromisoformat(period.end_date)
        if start <= value <= end:
            return period.policy_regime
    return "baseline"


def advance_state(
    state: BehavioralState,
    regime: str,
    policy_targets: dict[str, dict[str, float]],
    adaptation_rate: float,
    adherence_fatigue: float,
    risk_fatigue: float,
    trust_fatigue: float,
) -> BehavioralState:
    target = policy_targets.get(regime, policy_targets["baseline"])
    adherence = np.clip(
        (1.0 - adaptation_rate) * state.adherence_level + adaptation_rate * float(target["adherence_level"]) - adherence_fatigue,
        0.0,
        1.0,
    )
    risk = np.clip(
        (1.0 - 0.9 * adaptation_rate) * state.risk_perception + 0.9 * adaptation_rate * float(target["risk_perception"]) - risk_fatigue,
        0.0,
        1.0,
    )
    trust = np.clip(
        (1.0 - 0.6 * adaptation_rate) * state.trust_in_authorities
        + 0.6 * adaptation_rate * float(target["trust_in_authorities"])
        - trust_fatigue,
        0.0,
        1.0,
    )
    return BehavioralState(float(adherence), float(risk), float(trust), regime)


def prevention_score(state: BehavioralState, simulation_cfg: dict[str, Any]) -> float:
    weights = dict(simulation_cfg["prevention_score_weights"])
    raw_score = (
        float(weights["adherence_level"]) * state.adherence_level
        + float(weights["risk_perception"]) * state.risk_perception
        + float(weights["trust_in_authorities"]) * state.trust_in_authorities
    )
    policy_bonus = {"confinement": 0.03, "mask_mandate": 0.015, "risk_relaxation": -0.01, "baseline": -0.02}.get(
        state.policy_regime,
        0.0,
    )
    return float(np.clip(raw_score + policy_bonus, 0.0, 1.0))


def weighted_mean_contacts(matrix: np.ndarray, weights: np.ndarray) -> float:
    row_sums = np.asarray(matrix, dtype=float).sum(axis=1)
    normalized_weights = weights / np.clip(weights.sum(), a_min=1.0, a_max=None)
    return float(np.dot(row_sums, normalized_weights))


def contact_ratio_for_state(
    state: BehavioralState,
    base_matrix: np.ndarray,
    participant_counts: np.ndarray,
    base_contact_level: float,
) -> float:
    layer = BehavioralLayer(base_matrix, [state])
    adjusted = layer.apply(state)
    adjusted_level = weighted_mean_contacts(adjusted, participant_counts)
    return float(adjusted_level / max(base_contact_level, 1e-9))


def sample_state(target_date: date, simulated_dates: list[date], states: list[BehavioralState]) -> BehavioralState:
    index = min(range(len(simulated_dates)), key=lambda idx: abs((simulated_dates[idx] - target_date).days))
    return states[index]


def compute_series_metrics(predicted: np.ndarray, observed: np.ndarray) -> dict[str, Any]:
    return {
        "series_mae": float(metrics.series_mae(predicted, observed)),
        "trend_direction_agreement": float(metrics.trend_direction_agreement(predicted, observed)),
        "peak_timing_accuracy": float(metrics.peak_timing_accuracy(predicted, observed)),
        "peak_timing_error": int(metrics.peak_timing_error(predicted, observed)),
    }


def series_to_records(
    series_meta: list[Any],
    observed: np.ndarray,
    predicted: np.ndarray,
    static: np.ndarray,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(series_meta):
        label = getattr(item, field_name)
        date_value = getattr(item, "midpoint_date", None) or getattr(item, "representative_date", None)
        policy_regime = getattr(item, "policy_regime", "")
        records.append(
            {
                "label": label,
                "date": date_value,
                "start_date": getattr(item, "start_date", None),
                "end_date": getattr(item, "end_date", None),
                "policy_regime": policy_regime,
                "observed": float(observed[idx]),
                "predicted_behavioral": float(predicted[idx]),
                "predicted_static": float(static[idx]),
            }
        )
    return records


def build_assessment(
    preventive_metrics: dict[str, Any],
    preventive_static_metrics: dict[str, Any],
    contact_metrics: dict[str, Any],
    contact_static_metrics: dict[str, Any],
) -> dict[str, Any]:
    prevention_gain = preventive_static_metrics["series_mae"] - preventive_metrics["series_mae"]
    contact_gain = contact_static_metrics["series_mae"] - contact_metrics["series_mae"]
    adds_value = contact_gain > 0 and contact_metrics["trend_direction_agreement"] >= contact_static_metrics["trend_direction_agreement"]
    if adds_value:
        verdict = "partial_value"
        summary = "The behavioral layer adds value for time-varying contacts, but mostly as a direction-of-change model rather than as a calibrated absolute predictor."
    else:
        verdict = "limited_value"
        summary = "The behavioral layer does not clearly beat a static reference once honest temporal metrics are applied."
    return {
        "verdict": verdict,
        "summary": summary,
        "prevention_mae_gain_vs_static": float(prevention_gain),
        "contact_mae_gain_vs_static": float(contact_gain),
        "defensible_contribution": (
            "A defensible PhD contribution is the empirical demonstration that a transparent rule-based contact baseline can be extended into a policy-responsive time-series generator, plus a clear account of where that extension helps and where stronger behavioral data would still be required."
        ),
        "next_requirement_if_stronger_fit_is_needed": (
            "To claim stronger causal or predictive value, the project would need direct risk-perception variables, exact SocialCov survey windows, and either mobility or incidence covariates for dynamic calibration."
        ),
    }


def generate_figures(
    bundle: dict[str, Any],
    observed_prevention: np.ndarray,
    predicted_prevention: np.ndarray,
    static_prevention: np.ndarray,
    observed_contacts: np.ndarray,
    predicted_contacts: np.ndarray,
    static_contacts: np.ndarray,
) -> None:
    PREVENTIVE_FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    coviprev_labels = [wave.wave.split(":")[0].replace("vague", "V").strip() for wave in bundle["coviprev"]]
    socialcov_labels = [f"P{period.order_index}" for period in bundle["socialcov"]]

    plt.figure(figsize=(10, 4.8))
    x = np.arange(len(observed_prevention))
    plt.plot(x, observed_prevention, marker="o", linewidth=2.2, label="Observé (CoviPrev)")
    plt.plot(x, predicted_prevention, marker="s", linewidth=2.0, label="Simulé comportemental")
    plt.plot(x, static_prevention, linestyle="--", linewidth=1.5, label="Référence statique")
    plt.xticks(x, coviprev_labels, rotation=45, ha="right")
    plt.ylabel("Indice de prévention")
    plt.title("CoviPrev : prévention observée vs simulée")
    plt.ylim(0.45, 0.90)
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(PREVENTIVE_FIGURE_PATH, dpi=200)
    plt.close()

    plt.figure(figsize=(8.8, 4.8))
    x = np.arange(len(observed_contacts))
    plt.plot(x, observed_contacts, marker="o", linewidth=2.2, label="Observé (SocialCov)")
    plt.plot(x, predicted_contacts, marker="s", linewidth=2.0, label="Simulé comportemental")
    plt.plot(x, static_contacts, linestyle="--", linewidth=1.5, label="Référence statique")
    plt.xticks(x, socialcov_labels)
    plt.ylabel("Contacts relatifs au pré-pandémique")
    plt.title("SocialCov : changements de contacts par période")
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(CONTACT_FIGURE_PATH, dpi=200)
    plt.close()


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    pb = payload["preventive_behavior"]
    cc = payload["contact_changes"]
    return (
        "series                    mae    trend_agree  peak_acc\n"
        f"prevention_behavioral   {pb['metrics_behavioral']['series_mae']:.4f}   {pb['metrics_behavioral']['trend_direction_agreement']:.3f}        {pb['metrics_behavioral']['peak_timing_accuracy']:.3f}\n"
        f"prevention_static       {pb['metrics_static']['series_mae']:.4f}   {pb['metrics_static']['trend_direction_agreement']:.3f}        {pb['metrics_static']['peak_timing_accuracy']:.3f}\n"
        f"contact_behavioral      {cc['metrics_behavioral']['series_mae']:.4f}   {cc['metrics_behavioral']['trend_direction_agreement']:.3f}        {cc['metrics_behavioral']['peak_timing_accuracy']:.3f}\n"
        f"contact_static          {cc['metrics_static']['series_mae']:.4f}   {cc['metrics_static']['trend_direction_agreement']:.3f}        {cc['metrics_static']['peak_timing_accuracy']:.3f}"
    )


def main() -> int:
    try:
        config = load_config(CONFIG_PATH)
        payload = run_experiment(config)
        print(render_summary(payload))
        print(f"\nSaved results to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
