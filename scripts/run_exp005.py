"""Run experiment exp005: calibrate behavioral multipliers on French time series."""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
VENDOR_ROOT = REPO_ROOT / ".vendor"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.behavioral_layer import BehavioralLayer, BehavioralState  # noqa: E402
from contact_matrix_fr.optimized_baseline import fit_optimized_baseline  # noqa: E402
from contact_matrix_fr.time_series_loader import load_time_series_bundle  # noqa: E402
from run_exp001 import load_real_reference_inputs  # noqa: E402
from run_exp003 import ensure_time_series_inputs, simulate_states, sample_state, weighted_mean_contacts  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp005_calibrated_behavioral.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp005_calibrated_behavioral_results.json"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def load_optimized_base_matrix() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    inputs, reference, reference_payload = load_real_reference_inputs()
    optimized, _ = fit_optimized_baseline(inputs, reference)
    participant_counts = np.asarray(reference_payload["metadata"]["participant_age_counts"], dtype=float)
    return optimized.total_matrix, participant_counts, reference, reference_payload


def build_initial_state(simulation_cfg: dict[str, Any]) -> BehavioralState:
    state_cfg = dict(simulation_cfg["initial_state"])
    return BehavioralState(
        adherence_level=float(state_cfg["adherence_level"]),
        risk_perception=float(state_cfg["risk_perception"]),
        trust_in_authorities=float(state_cfg["trust_in_authorities"]),
        policy_regime=str(state_cfg["policy_regime"]),
    )


def compute_metrics(predicted: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    return {
        "series_mae": float(metrics.series_mae(predicted, observed)),
        "trend_direction_agreement": float(metrics.trend_direction_agreement(predicted, observed)),
        "peak_timing_accuracy": float(metrics.peak_timing_accuracy(predicted, observed)),
        "peak_timing_error": int(metrics.peak_timing_error(predicted, observed)),
    }


def split_indices(dates: list[date], train_end_date: date) -> tuple[list[int], list[int]]:
    train_idx = [idx for idx, item in enumerate(dates) if item <= train_end_date]
    test_idx = [idx for idx, item in enumerate(dates) if item > train_end_date]
    if not train_idx or not test_idx:
        raise ValueError("train/test split produced an empty partition")
    return train_idx, test_idx


def subset(values: np.ndarray, indices: list[int]) -> np.ndarray:
    return np.asarray([values[idx] for idx in indices], dtype=float)


def subset_states(states: list[BehavioralState], indices: list[int]) -> list[BehavioralState]:
    return [states[idx] for idx in indices]


def to_records(labels: list[str], dates: list[date], observed: np.ndarray, default: np.ndarray, calibrated: np.ndarray) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, label in enumerate(labels):
        records.append(
            {
                "label": label,
                "date": dates[idx].isoformat(),
                "observed": float(observed[idx]),
                "predicted_default": float(default[idx]),
                "predicted_calibrated": float(calibrated[idx]),
            }
        )
    return records


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    ensure_time_series_inputs()
    bundle = load_time_series_bundle(REPO_ROOT / "data" / "interim")
    base_matrix, participant_counts, _, reference_payload = load_optimized_base_matrix()
    base_contact_level = weighted_mean_contacts(base_matrix, participant_counts)

    simulation_cfg = dict(config["simulation"])
    initial_state = build_initial_state(simulation_cfg)
    weekly_dates, sampled_states = simulate_states(simulation_cfg, bundle["policy_timeline"], initial_state)

    coviprev_dates = [datetime.fromisoformat(wave.midpoint_date).date() for wave in bundle["coviprev"]]
    coviprev_labels = [str(wave.wave) for wave in bundle["coviprev"]]
    socialcov_dates = [datetime.fromisoformat(period.representative_date).date() for period in bundle["socialcov"]]
    socialcov_labels = [str(period.period_id) for period in bundle["socialcov"]]

    prevention_states = [sample_state(item, weekly_dates, sampled_states) for item in coviprev_dates]
    contact_states = [sample_state(item, weekly_dates, sampled_states) for item in socialcov_dates]
    prevention_targets = np.asarray(bundle["coviprev_observed_prevention"], dtype=float)
    contact_targets = np.asarray(bundle["socialcov_observed_relative_contacts"], dtype=float)

    train_end_date = date.fromisoformat(str(config["split"]["train_end_date"]))
    prevention_train_idx, prevention_test_idx = split_indices(coviprev_dates, train_end_date)
    contact_train_idx, contact_test_idx = split_indices(socialcov_dates, train_end_date)

    layer_default = BehavioralLayer(base_matrix, [initial_state])
    default_prevention = np.asarray([layer_default.prevention_score(state) for state in prevention_states], dtype=float)
    default_contacts = np.asarray(
        [layer_default.contact_ratio(state, participant_counts, base_contact_level) for state in contact_states],
        dtype=float,
    )

    calibration_result = layer_default.calibrate(
        prevention_states=subset_states(prevention_states, prevention_train_idx),
        prevention_targets=subset(prevention_targets, prevention_train_idx),
        contact_states=subset_states(contact_states, contact_train_idx),
        contact_targets=subset(contact_targets, contact_train_idx),
        participant_weights=participant_counts,
        base_contact_level=base_contact_level,
        regularization_strength=float(config["calibration"].get("regularization_strength", 0.01)),
        maxiter=int(config["calibration"].get("maxiter", 2500)),
    )

    calibrated_prevention = np.asarray([layer_default.prevention_score(state) for state in prevention_states], dtype=float)
    calibrated_contacts = np.asarray(
        [layer_default.contact_ratio(state, participant_counts, base_contact_level) for state in contact_states],
        dtype=float,
    )

    static_prevention = np.full_like(prevention_targets, float(config["comparison"]["static_prevention_level"]))
    static_contacts = np.full_like(contact_targets, float(config["comparison"]["static_contact_level"]))

    payload = {
        "experiment_name": str(config.get("experiment_name", "exp005_calibrated_behavioral")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "reference": reference_payload["metadata"],
        "base_contact_level": float(base_contact_level),
        "split": {
            "train_end_date": train_end_date.isoformat(),
            "prevention_train_labels": [coviprev_labels[idx] for idx in prevention_train_idx],
            "prevention_test_labels": [coviprev_labels[idx] for idx in prevention_test_idx],
            "contact_train_labels": [socialcov_labels[idx] for idx in contact_train_idx],
            "contact_test_labels": [socialcov_labels[idx] for idx in contact_test_idx],
        },
        "calibration": asdict(calibration_result),
        "preventive_behavior": {
            "records": to_records(coviprev_labels, coviprev_dates, prevention_targets, default_prevention, calibrated_prevention),
            "train_metrics_default": compute_metrics(subset(default_prevention, prevention_train_idx), subset(prevention_targets, prevention_train_idx)),
            "train_metrics_calibrated": compute_metrics(subset(calibrated_prevention, prevention_train_idx), subset(prevention_targets, prevention_train_idx)),
            "test_metrics_default": compute_metrics(subset(default_prevention, prevention_test_idx), subset(prevention_targets, prevention_test_idx)),
            "test_metrics_calibrated": compute_metrics(subset(calibrated_prevention, prevention_test_idx), subset(prevention_targets, prevention_test_idx)),
            "test_metrics_static": compute_metrics(subset(static_prevention, prevention_test_idx), subset(prevention_targets, prevention_test_idx)),
        },
        "contact_changes": {
            "records": to_records(socialcov_labels, socialcov_dates, contact_targets, default_contacts, calibrated_contacts),
            "train_metrics_default": compute_metrics(subset(default_contacts, contact_train_idx), subset(contact_targets, contact_train_idx)),
            "train_metrics_calibrated": compute_metrics(subset(calibrated_contacts, contact_train_idx), subset(contact_targets, contact_train_idx)),
            "test_metrics_default": compute_metrics(subset(default_contacts, contact_test_idx), subset(contact_targets, contact_test_idx)),
            "test_metrics_calibrated": compute_metrics(subset(calibrated_contacts, contact_test_idx), subset(contact_targets, contact_test_idx)),
            "test_metrics_static": compute_metrics(subset(static_contacts, contact_test_idx), subset(contact_targets, contact_test_idx)),
        },
        "assessment": {
            "honest_summary": (
                "The calibration is only convincing if held-out MAE improves relative to both the uncalibrated layer and the static benchmark. "
                "If test performance degrades while train performance improves, that is evidence of overfitting rather than added explanatory value."
            ),
        },
    }
    return payload


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    prev = payload["preventive_behavior"]
    cont = payload["contact_changes"]
    return (
        "series                    train_mae_default  train_mae_cal  test_mae_default  test_mae_cal\n"
        f"prevention               {prev['train_metrics_default']['series_mae']:.4f}           {prev['train_metrics_calibrated']['series_mae']:.4f}         {prev['test_metrics_default']['series_mae']:.4f}           {prev['test_metrics_calibrated']['series_mae']:.4f}\n"
        f"contacts                 {cont['train_metrics_default']['series_mae']:.4f}           {cont['train_metrics_calibrated']['series_mae']:.4f}         {cont['test_metrics_default']['series_mae']:.4f}           {cont['test_metrics_calibrated']['series_mae']:.4f}"
    )


def main() -> int:
    try:
        config = load_config(CONFIG_PATH)
        payload = run_experiment(config)
        save_results(payload, OUTPUT_PATH)
        print(render_summary(payload))
        print(f"\nSaved results to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
