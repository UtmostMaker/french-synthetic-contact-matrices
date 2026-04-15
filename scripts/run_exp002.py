"""Run experiment exp002 for the bounded behavioral layer on real COMES-F data.

Usage:
    python scripts/run_exp002.py
"""

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

from contact_matrix_fr.baselines import BaselineBuilder  # noqa: E402
from contact_matrix_fr.behavioral_layer import BehavioralLayer, BehavioralState  # noqa: E402
import contact_matrix_fr.metrics as metrics  # noqa: E402
from run_exp001 import load_config as load_exp001_config, load_real_reference_inputs  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp002_behavioral_layer.yaml"
EXP001_CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp001_baseline_comparison.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp002_real_results.json"
PLACEHOLDER_OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp002_results.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Experiment config not found: {path}")
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


def load_base_matrix(seed: int) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    _ = seed
    exp001_config = load_exp001_config(EXP001_CONFIG_PATH)
    builder = BaselineBuilder()
    inputs, reference, reference_payload = load_real_reference_inputs()
    target_name = str(exp001_config.get("baselines", [])[1]["builder_method"])
    method = getattr(builder, target_name)
    baseline_output = method(inputs)
    return baseline_output.total_matrix, reference, reference_payload


def build_states(config: dict[str, Any]) -> list[BehavioralState]:
    states: list[BehavioralState] = []
    for item in config.get("states", []):
        states.append(
            BehavioralState(
                adherence_level=float(item["adherence_level"]),
                risk_perception=float(item["risk_perception"]),
                trust_in_authorities=float(item["trust_in_authorities"]),
                policy_regime=str(item["policy_regime"]),
            )
        )
    if not states:
        raise ValueError("No behavioral states configured")
    return states


def comparison_to_placeholder(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not PLACEHOLDER_OUTPUT_PATH.exists():
        return {"available": False}
    with PLACEHOLDER_OUTPUT_PATH.open("r", encoding="utf-8") as handle:
        placeholder_payload = json.load(handle)
    previous = {item["seed"]: item for item in placeholder_payload.get("results", [])}
    deltas: dict[str, Any] = {}
    for item in results:
        seed = item["seed"]
        base = previous.get(seed)
        if not base:
            continue
        deltas[str(seed)] = {
            "delta_aggregate_mae": float(item["aggregate_metrics"]["matrix_mae"] - base["aggregate_metrics"]["matrix_mae"]),
            "delta_evolved_mae": float(item["evolved_metrics"]["matrix_mae"] - base["evolved_metrics"]["matrix_mae"]),
        }
    return {
        "available": True,
        "source": str(PLACEHOLDER_OUTPUT_PATH.relative_to(REPO_ROOT)),
        "deltas": deltas,
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    metric_names = list(config.get("metrics", []))
    seeds = [int(seed) for seed in config.get("seeds", [2026])]
    if not metric_names:
        raise ValueError("No metrics configured")

    scenario_cfg = dict(config.get("scenario_generation", {}))
    dry_run = bool(scenario_cfg.get("dry_run", False))
    scenario_count = int(scenario_cfg.get("scenario_count", 3))
    configured_states = build_states(config)

    run_results: list[dict[str, Any]] = []
    reference_payload: dict[str, Any] | None = None
    for seed in seeds:
        base_matrix, reference, reference_payload = load_base_matrix(seed)
        layer = BehavioralLayer(base_matrix, configured_states, dry_run=dry_run)
        aggregate_state = layer.aggregate_state()
        aggregate_matrix = layer.apply(aggregate_state)
        aggregate_metrics = compute_metrics(metric_names, aggregate_matrix, reference)

        evolved_states = layer.evolve_states(steps=2, seed=seed)
        evolved_layer = BehavioralLayer(base_matrix, evolved_states, dry_run=dry_run)
        evolved_matrix = evolved_layer.apply()
        evolved_metrics = compute_metrics(metric_names, evolved_matrix, reference)

        scenarios = []
        if bool(scenario_cfg.get("enabled", True)):
            for scenario in layer.generate_scenarios(scenario_count=scenario_count, seed=seed):
                scenario_matrix = np.asarray(scenario["matrix"], dtype=float)
                scenarios.append(
                    {
                        "name": scenario["name"],
                        "state": scenario["state"],
                        "metrics": compute_metrics(metric_names, scenario_matrix, reference),
                        "matrix_shape": list(scenario_matrix.shape),
                    }
                )

        run_results.append(
            {
                "seed": seed,
                "base_baseline": "household_rule_based",
                "aggregate_state": {
                    "adherence_level": aggregate_state.adherence_level,
                    "risk_perception": aggregate_state.risk_perception,
                    "trust_in_authorities": aggregate_state.trust_in_authorities,
                    "policy_regime": aggregate_state.policy_regime,
                },
                "aggregate_metrics": aggregate_metrics,
                "evolved_state_count": len(evolved_states),
                "evolved_metrics": evolved_metrics,
                "scenarios": scenarios,
            }
        )

    return {
        "experiment_name": str(config.get("experiment_name", "exp002_behavioral_layer")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "base_experiment": {
            **dict(config.get("base_experiment", {})),
            "reference_source": "comes_f_public_workbook_symmetrized",
        },
        "dry_run": dry_run,
        "reference": reference_payload["metadata"] if reference_payload else {},
        "results": run_results,
        "comparison_to_placeholder": comparison_to_placeholder(run_results),
    }


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    lines = ["seed  aggregate_mae  aggregate_frobenius  evolved_mae  scenarios"]
    lines.append("----  -------------  -------------------  -----------  ---------")
    for result in payload["results"]:
        lines.append(
            f"{result['seed']}  "
            f"{result['aggregate_metrics']['matrix_mae']:.4f}         "
            f"{result['aggregate_metrics']['matrix_frobenius_distance']:.4f}              "
            f"{result['evolved_metrics']['matrix_mae']:.4f}       "
            f"{len(result['scenarios'])}"
        )
    return "\n".join(lines)


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
