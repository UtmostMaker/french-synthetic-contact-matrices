"""Run sensitivity, ablation, and bootstrap checks for the calibrated behavioral layer."""

from __future__ import annotations

import json
import sys
import traceback
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
VENDOR_ROOT = REPO_ROOT / ".vendor"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.behavioral_layer import BehavioralLayer  # noqa: E402
from contact_matrix_fr.time_series_loader import load_time_series_bundle  # noqa: E402
from run_exp005 import load_config, load_optimized_base_matrix, build_initial_state, split_indices, subset_states, subset  # noqa: E402
from run_exp003 import ensure_time_series_inputs, simulate_states, sample_state, weighted_mean_contacts  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp005_calibrated_behavioral.yaml"
EXP005_OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp005_calibrated_behavioral_results.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "robustness_results.json"


def bootstrap_mae(predicted: np.ndarray, observed: np.ndarray, rng: np.random.Generator, n_boot: int = 2000) -> dict[str, float]:
    n = predicted.size
    samples = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        samples.append(float(metrics.series_mae(predicted[idx], observed[idx])))
    arr = np.asarray(samples, dtype=float)
    return {
        "mean": float(arr.mean()),
        "ci_lower": float(np.quantile(arr, 0.025)),
        "ci_upper": float(np.quantile(arr, 0.975)),
    }


def main_payload() -> dict[str, Any]:
    if not EXP005_OUTPUT_PATH.exists():
        raise FileNotFoundError("exp005 results not found, run scripts/run_exp005.py first")
    with EXP005_OUTPUT_PATH.open("r", encoding="utf-8") as handle:
        exp005_payload = json.load(handle)

    config = load_config(CONFIG_PATH)
    ensure_time_series_inputs()
    bundle = load_time_series_bundle(REPO_ROOT / "data" / "interim")
    base_matrix, participant_counts, _, _ = load_optimized_base_matrix()
    base_contact_level = weighted_mean_contacts(base_matrix, participant_counts)
    simulation_cfg = dict(config["simulation"])
    initial_state = build_initial_state(simulation_cfg)
    weekly_dates, sampled_states = simulate_states(simulation_cfg, bundle["policy_timeline"], initial_state)

    coviprev_dates = [datetime.fromisoformat(wave.midpoint_date).date() for wave in bundle["coviprev"]]
    socialcov_dates = [datetime.fromisoformat(period.representative_date).date() for period in bundle["socialcov"]]
    prevention_states = [sample_state(item, weekly_dates, sampled_states) for item in coviprev_dates]
    contact_states = [sample_state(item, weekly_dates, sampled_states) for item in socialcov_dates]
    prevention_targets = np.asarray(bundle["coviprev_observed_prevention"], dtype=float)
    contact_targets = np.asarray(bundle["socialcov_observed_relative_contacts"], dtype=float)

    train_end_date = date.fromisoformat(str(config["split"]["train_end_date"]))
    _, prevention_test_idx = split_indices(coviprev_dates, train_end_date)
    _, contact_test_idx = split_indices(socialcov_dates, train_end_date)

    calibrated_params = dict(exp005_payload["calibration"]["parameters"])
    calibrated_layer = BehavioralLayer(base_matrix, [initial_state], parameters=calibrated_params)
    prevention_test_states = subset_states(prevention_states, prevention_test_idx)
    contact_test_states = subset_states(contact_states, contact_test_idx)
    prevention_test_targets = subset(prevention_targets, prevention_test_idx)
    contact_test_targets = subset(contact_targets, contact_test_idx)

    calibrated_prevention_test = np.asarray(
        [calibrated_layer.prevention_score(state) for state in prevention_test_states],
        dtype=float,
    )
    calibrated_contact_test = np.asarray(
        [calibrated_layer.contact_ratio(state, participant_counts, base_contact_level) for state in contact_test_states],
        dtype=float,
    )

    sensitivity_specs = {
        "home_risk_gain": 0.10,
        "school_response_gain": 0.10,
        "work_response_gain": 0.10,
        "other_response_gain": 0.10,
        "policy_confinement_scale": 0.10,
        "policy_mask_scale": 0.10,
        "prevention_weight_adherence": 0.10,
        "prevention_weight_risk": 0.10,
    }
    sensitivity_results: dict[str, Any] = {}
    for name, frac in sensitivity_specs.items():
        base_value = float(calibrated_params[name])
        trials = {}
        for direction, multiplier in (("minus", 1.0 - frac), ("plus", 1.0 + frac)):
            params = dict(calibrated_params)
            params[name] = base_value * multiplier
            layer = BehavioralLayer(base_matrix, [initial_state], parameters=params)
            pred_prev = np.asarray([layer.prevention_score(state) for state in prevention_test_states], dtype=float)
            pred_cont = np.asarray([layer.contact_ratio(state, participant_counts, base_contact_level) for state in contact_test_states], dtype=float)
            trials[direction] = {
                "parameter_value": float(params[name]),
                "prevention_test_mae": float(metrics.series_mae(pred_prev, prevention_test_targets)),
                "contact_test_mae": float(metrics.series_mae(pred_cont, contact_test_targets)),
            }
        sensitivity_results[name] = trials

    ablations = {
        "remove_home_behavior": {"home_risk_gain": 0.0, "home_adherence_gain": 0.0},
        "remove_school_behavior": {"school_response_gain": 0.0, "school_trust_penalty": 0.0},
        "remove_work_behavior": {"work_response_gain": 0.0, "work_trust_penalty": 0.0},
        "remove_other_behavior": {"other_response_gain": 0.0, "other_adherence_penalty": 0.0},
        "remove_policy_effects": {
            "policy_mask_scale": 0.0,
            "policy_confinement_scale": 0.0,
            "policy_relaxation_scale": 0.0,
            "policy_bonus_baseline": 0.0,
            "policy_bonus_mask_mandate": 0.0,
            "policy_bonus_confinement": 0.0,
            "policy_bonus_risk_relaxation": 0.0,
        },
    }
    ablation_results: dict[str, Any] = {}
    for name, updates in ablations.items():
        params = dict(calibrated_params)
        params.update(updates)
        layer = BehavioralLayer(base_matrix, [initial_state], parameters=params)
        pred_prev = np.asarray([layer.prevention_score(state) for state in prevention_test_states], dtype=float)
        pred_cont = np.asarray([layer.contact_ratio(state, participant_counts, base_contact_level) for state in contact_test_states], dtype=float)
        ablation_results[name] = {
            "prevention_test_mae": float(metrics.series_mae(pred_prev, prevention_test_targets)),
            "contact_test_mae": float(metrics.series_mae(pred_cont, contact_test_targets)),
            "prevention_direction_agreement": float(metrics.trend_direction_agreement(pred_prev, prevention_test_targets)),
            "contact_direction_agreement": float(metrics.trend_direction_agreement(pred_cont, contact_test_targets)),
        }

    rng = np.random.default_rng(2026)
    bootstrap = {
        "prevention_test_mae": bootstrap_mae(calibrated_prevention_test, prevention_test_targets, rng),
        "contact_test_mae": bootstrap_mae(calibrated_contact_test, contact_test_targets, rng),
    }

    return {
        "source_experiment": str(EXP005_OUTPUT_PATH.relative_to(REPO_ROOT)),
        "baseline_test_metrics": {
            "prevention_test_mae": float(metrics.series_mae(calibrated_prevention_test, prevention_test_targets)),
            "contact_test_mae": float(metrics.series_mae(calibrated_contact_test, contact_test_targets)),
        },
        "sensitivity_analysis": sensitivity_results,
        "ablation_study": ablation_results,
        "bootstrap_confidence_intervals": bootstrap,
        "notes": [
            "Sensitivity is evaluated on held-out periods only.",
            "Bootstrap intervals are empirical percentile intervals over resampled held-out observations.",
            "Because the held-out SocialCov test set has only two periods, the contact-side intervals are necessarily wide and should be interpreted cautiously.",
        ],
    }


def main() -> int:
    try:
        payload = main_payload()
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print(json.dumps(payload["baseline_test_metrics"], indent=2, ensure_ascii=False))
        print(f"\nSaved results to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
