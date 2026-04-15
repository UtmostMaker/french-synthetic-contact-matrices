"""Run experiment exp004: optimize baseline setting weights against COMES-F."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.baselines import BaselineBuilder  # noqa: E402
from contact_matrix_fr.optimized_baseline import fit_optimized_baseline  # noqa: E402
from run_exp001 import load_real_reference_inputs  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp004_optimized_baseline.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp004_optimized_baseline_results.json"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def compute_metrics(metric_names: list[str], predicted: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    computed: dict[str, Any] = {}
    for metric_name in metric_names:
        metric_fn = getattr(metrics, metric_name, None)
        if metric_fn is None:
            raise ValueError(f"Configured metric is not implemented: {metric_name}")
        if metric_name in {"matrix_mae", "matrix_frobenius_distance"}:
            computed[metric_name] = float(metric_fn(predicted, reference))
        elif metric_name == "age_assortativity":
            computed[metric_name] = metric_fn(predicted)
        elif metric_name == "reciprocity_gap":
            computed[metric_name] = float(metric_fn(predicted))
        else:
            computed[metric_name] = metric_fn(predicted, reference)
    return computed


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    inputs, reference, reference_payload = load_real_reference_inputs()
    baseline_builder = BaselineBuilder()
    heuristic = baseline_builder.household_rule_based(inputs)

    optimization_cfg = dict(config.get("optimization", {}))
    bounds = {key: tuple(value) for key, value in dict(optimization_cfg.get("bounds", {})).items()}
    optimized, fit = fit_optimized_baseline(
        inputs,
        reference,
        initial_weights=dict(optimization_cfg.get("initial_weights", {})),
        bounds=bounds,
        penalty_strength=float(optimization_cfg.get("penalty_strength", 0.01)),
        maxiter=int(optimization_cfg.get("maxiter", 2000)),
    )

    metric_names = list(config.get("metrics", []))
    heuristic_metrics = compute_metrics(metric_names, heuristic.total_matrix, reference)
    optimized_metrics = compute_metrics(metric_names, optimized.total_matrix, reference)

    return {
        "experiment_name": str(config.get("experiment_name", "exp004_optimized_baseline")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "reference": reference_payload["metadata"],
        "heuristic_baseline": {
            "name": heuristic.name,
            "metrics": heuristic_metrics,
        },
        "optimized_baseline": {
            "name": optimized.name,
            "metrics": optimized_metrics,
            "weights": fit.weights,
            "optimizer": {
                "objective_name": fit.objective_name,
                "objective_value": fit.objective_value,
                "success": fit.success,
                "message": fit.optimizer_message,
                "iterations": fit.iterations,
            },
        },
        "comparison": {
            "mae_improvement": float(heuristic_metrics["matrix_mae"] - optimized_metrics["matrix_mae"]),
            "frobenius_improvement": float(
                heuristic_metrics["matrix_frobenius_distance"] - optimized_metrics["matrix_frobenius_distance"]
            ),
            "relative_mae_improvement_pct": float(
                100.0
                * (heuristic_metrics["matrix_mae"] - optimized_metrics["matrix_mae"])
                / max(heuristic_metrics["matrix_mae"], 1e-9)
            ),
        },
        "interpretation": (
            "The optimized baseline is stronger evidence than the heuristic version only if its gain persists on held-out temporal analyses. "
            "If the gain is modest, that is still useful because it quantifies how much of the baseline performance was already due to the original structure rather than arbitrary weights."
        ),
    }


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    heuristic = payload["heuristic_baseline"]["metrics"]
    optimized = payload["optimized_baseline"]["metrics"]
    weights = payload["optimized_baseline"]["weights"]
    return (
        "baseline               mae     frobenius\n"
        f"heuristic              {heuristic['matrix_mae']:.4f}  {heuristic['matrix_frobenius_distance']:.4f}\n"
        f"optimized              {optimized['matrix_mae']:.4f}  {optimized['matrix_frobenius_distance']:.4f}\n"
        f"weights: home={weights['home']:.3f}, school={weights['school']:.3f}, work={weights['work']:.3f}, other={weights['other']:.3f}"
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
