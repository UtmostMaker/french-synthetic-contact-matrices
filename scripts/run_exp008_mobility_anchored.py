"""Run exp008: regime-anchored diagnostic for mobility in exp007."""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp008_mobility_anchored.yaml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"JSON payload is empty or malformed: {path}")
    return payload


def weighted_mean(rows: list[dict[str, Any]], key: str) -> float:
    weights = np.asarray([float(row["population_weight"]) for row in rows], dtype=float)
    values = np.asarray([float(row[key]) for row in rows], dtype=float)
    total = float(weights.sum())
    if total <= 0:
        return 0.0
    return float(np.dot(values, weights) / total)


def pearson_correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    if len(left) == 1:
        return 1.0
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def mae(observed: list[float], predicted: list[float]) -> float:
    return float(np.mean(np.abs(np.asarray(predicted, dtype=float) - np.asarray(observed, dtype=float))))


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    input_path = REPO_ROOT / str(config["input_results_path"])
    source = load_json(input_path)

    llm_records = list(source["llm_profile_records"])
    heuristic_records = list(source["heuristic_profile_records"])
    aggregated = list(source["aggregated_predictions"])

    adjustment = dict(config.get("mobility_adjustment", {}))
    llm_weight = float(adjustment.get("llm_profile_delta_weight", 0.75))
    heuristic_weight = float(adjustment.get("heuristic_profile_delta_weight", 0.25))
    clip_min = float(adjustment.get("clip_min", 0.0))
    clip_max = float(adjustment.get("clip_max", 1.0))

    llm_by_key = {(row["profile_key"], row["policy_regime"]): row for row in llm_records}
    heur_by_key = {(row["profile_key"], row["policy_regime"]): row for row in heuristic_records}

    llm_by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    heur_by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    aggregated_by_regime = {row["policy_regime"]: row for row in aggregated}
    for row in llm_records:
        llm_by_regime[str(row["policy_regime"])].append(row)
    for row in heuristic_records:
        heur_by_regime[str(row["policy_regime"])].append(row)

    adjusted_profile_records: list[dict[str, Any]] = []
    observed_series: list[float] = []
    raw_llm_series: list[float] = []
    heuristic_series: list[float] = []
    anchored_series: list[float] = []
    regime_diagnostics: list[dict[str, Any]] = []

    for regime, agg in aggregated_by_regime.items():
        observed = float(agg["observed_mobility_reduction"])
        raw_llm = float(agg["llm_predicted_mobility_reduction"])
        raw_heur = float(agg["heuristic_predicted_mobility_reduction"])
        regime_rows = llm_by_regime[regime]
        adjusted_rows_for_regime: list[dict[str, Any]] = []

        for llm_row in regime_rows:
            key = (str(llm_row["profile_key"]), str(llm_row["policy_regime"]))
            heur_row = heur_by_key[key]
            llm_delta = float(llm_row["mobility_reduction"]) - raw_llm
            heur_delta = float(heur_row["mobility_reduction"]) - raw_heur
            anchored = float(np.clip(observed + llm_weight * llm_delta + heuristic_weight * heur_delta, clip_min, clip_max))

            adjusted_row = {
                **llm_row,
                "raw_llm_mobility_reduction": float(llm_row["mobility_reduction"]),
                "heuristic_mobility_reduction": float(heur_row["mobility_reduction"]),
                "mobility_reduction": anchored,
                "mobility_anchor_observed_regime": observed,
                "llm_regime_mean_before_anchor": raw_llm,
                "heuristic_regime_mean_before_anchor": raw_heur,
                "llm_profile_delta": llm_delta,
                "heuristic_profile_delta": heur_delta,
            }
            adjusted_rows_for_regime.append(adjusted_row)
            adjusted_profile_records.append(adjusted_row)

        anchored_regime_mean = weighted_mean(adjusted_rows_for_regime, "mobility_reduction")
        regime_diagnostics.append(
            {
                "policy_regime": regime,
                "policy_label": str(agg["policy_label"]),
                "observed_mobility_reduction": observed,
                "raw_llm_mobility_reduction": raw_llm,
                "heuristic_mobility_reduction": raw_heur,
                "anchored_mobility_reduction": anchored_regime_mean,
                "raw_llm_bias": raw_llm - observed,
                "heuristic_bias": raw_heur - observed,
                "anchored_bias": anchored_regime_mean - observed,
            }
        )
        observed_series.append(observed)
        raw_llm_series.append(raw_llm)
        heuristic_series.append(raw_heur)
        anchored_series.append(anchored_regime_mean)

    regime_diagnostics.sort(key=lambda row: row["policy_regime"])

    metrics_payload = {
        "raw_llm_mobility_mae": mae(observed_series, raw_llm_series),
        "heuristic_mobility_mae": mae(observed_series, heuristic_series),
        "anchored_mobility_mae": mae(observed_series, anchored_series),
        "raw_llm_mobility_correlation": pearson_correlation(raw_llm_series, observed_series),
        "heuristic_mobility_correlation": pearson_correlation(heuristic_series, observed_series),
        "anchored_mobility_correlation": pearson_correlation(anchored_series, observed_series),
        "mean_abs_raw_llm_regime_bias": float(np.mean([abs(row["raw_llm_bias"]) for row in regime_diagnostics])),
        "mean_abs_heuristic_regime_bias": float(np.mean([abs(row["heuristic_bias"]) for row in regime_diagnostics])),
        "mean_abs_anchored_regime_bias": float(np.mean([abs(row["anchored_bias"]) for row in regime_diagnostics])),
    }

    diagnosis = {
        "main_read": (
            "If the anchored diagnostic sharply reduces mobility error, exp007 mainly failed on the absolute regime-level mobility scale rather than on the existence of profile-level differentiation."
        ),
        "regime_bias_pattern": [
            {
                "policy_regime": row["policy_regime"],
                "raw_llm_bias": row["raw_llm_bias"],
                "heuristic_bias": row["heuristic_bias"],
            }
            for row in regime_diagnostics
        ],
    }

    return {
        "experiment_name": str(config.get("experiment_name", "exp008_mobility_anchored")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "input_results_path": str(input_path.relative_to(REPO_ROOT)),
        "mobility_adjustment": {
            "llm_profile_delta_weight": llm_weight,
            "heuristic_profile_delta_weight": heuristic_weight,
            "clip_min": clip_min,
            "clip_max": clip_max,
        },
        "source_metrics": dict(source.get("metrics", {})),
        "regime_diagnostics": regime_diagnostics,
        "anchored_profile_records": adjusted_profile_records,
        "metrics": metrics_payload,
        "assessment": {
            "purpose": str(config.get("assessment", {}).get("purpose", "diagnostic_mobility_calibration")),
            "note": str(config.get("assessment", {}).get("note", "")),
            "diagnosis": diagnosis,
        },
    }


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    return (
        "metric                        raw_llm    heuristic  anchored\n"
        f"mobility_mae                   {m['raw_llm_mobility_mae']:.4f}     {m['heuristic_mobility_mae']:.4f}     {m['anchored_mobility_mae']:.4f}\n"
        f"mobility_correlation           {m['raw_llm_mobility_correlation']:.3f}      {m['heuristic_mobility_correlation']:.3f}      {m['anchored_mobility_correlation']:.3f}\n"
        f"mean_abs_regime_bias           {m['mean_abs_raw_llm_regime_bias']:.4f}     {m['mean_abs_heuristic_regime_bias']:.4f}     {m['mean_abs_anchored_regime_bias']:.4f}"
    )


def main() -> int:
    try:
        config = load_config(CONFIG_PATH)
        payload = run_experiment(config)
        output_path = REPO_ROOT / str(config["output_results_path"])
        save_results(payload, output_path)
        print(render_summary(payload))
        print(f"\nSaved results to {output_path.relative_to(REPO_ROOT)}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
