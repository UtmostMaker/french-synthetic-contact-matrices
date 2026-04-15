"""Run experiment exp001 against the public COMES-F workbook.

Usage:
    python scripts/run_exp001.py
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from contact_matrix_fr.baselines import BaselineBuilder, BaselineInputs  # noqa: E402
from contact_matrix_fr.data_loader import load_comes_f  # noqa: E402
import contact_matrix_fr.metrics as metrics  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp001_baseline_comparison.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp001_real_results.json"
PLACEHOLDER_OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp001_results.json"
REAL_COMES_F_PATH = REPO_ROOT / "data" / "raw" / "comes_f" / "RawData_ComesF.xlsx"


@dataclass(slots=True)
class BaselineRunResult:
    name: str
    seed: int
    matrix_shape: tuple[int, int]
    metrics: dict[str, Any]
    notes: dict[str, str]


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Experiment config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def derive_reference_templates(reference: np.ndarray) -> dict[str, np.ndarray]:
    dimension = reference.shape[0]
    age_axis = np.linspace(0.0, 85.0, num=dimension, dtype=float)
    child = _window(age_axis, 0.0, 17.0)
    student = _window(age_axis, 5.0, 22.0)
    worker = _window(age_axis, 18.0, 64.0)
    senior = _window(age_axis, 65.0, 85.0)
    universal = np.ones_like(age_axis, dtype=float)

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
    total_weight = np.zeros_like(reference)
    for weight in weights.values():
        total_weight += weight
    total_weight = np.clip(total_weight, a_min=1e-9, a_max=None)
    return {name: reference * (weight / total_weight) for name, weight in weights.items()}


def load_real_reference_inputs(path: Path = REAL_COMES_F_PATH) -> tuple[BaselineInputs, np.ndarray, dict[str, Any]]:
    payload = load_comes_f(path)
    reference = np.asarray(payload["matrix"], dtype=float)
    participant_counts = np.asarray(payload["metadata"].get("participant_age_counts", []), dtype=float)
    if participant_counts.shape != (reference.shape[0],):
        raise ValueError("COMES-F participant age counts do not match the parsed matrix dimension")
    templates = derive_reference_templates(reference)
    inputs = BaselineInputs(
        population_by_age=np.clip(participant_counts, a_min=1.0, a_max=None),
        home_matrix=templates["home"],
        school_matrix=templates["school"],
        work_matrix=templates["work"],
        other_matrix=templates["other"],
        metadata={
            "generator": "comes_f_real_reference",
            "reference": "comes_f_public_workbook",
            "population_proxy": "respondent age counts from public raw workbook",
        },
    )
    return inputs, reference, payload


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


def comparison_to_placeholder(results: list[BaselineRunResult]) -> dict[str, Any]:
    if not PLACEHOLDER_OUTPUT_PATH.exists():
        return {"available": False}
    with PLACEHOLDER_OUTPUT_PATH.open("r", encoding="utf-8") as handle:
        placeholder_payload = json.load(handle)
    previous = {item["name"]: item["metrics"] for item in placeholder_payload.get("results", [])}
    deltas: dict[str, Any] = {}
    for item in results:
        base = previous.get(item.name)
        if not base:
            continue
        deltas[item.name] = {
            "delta_matrix_mae": float(item.metrics["matrix_mae"] - base["matrix_mae"]),
            "delta_matrix_frobenius_distance": float(
                item.metrics["matrix_frobenius_distance"] - base["matrix_frobenius_distance"]
            ),
        }
    return {
        "available": True,
        "source": str(PLACEHOLDER_OUTPUT_PATH.relative_to(REPO_ROOT)),
        "deltas": deltas,
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    builder = BaselineBuilder()
    baseline_specs = config.get("baselines", [])
    metric_names = list(config.get("metrics", []))
    seeds = list(config.get("seeds", [2026]))
    if not baseline_specs:
        raise ValueError("No baselines were configured")
    if not metric_names:
        raise ValueError("No metrics were configured")

    seed = int(seeds[0])
    inputs, reference, reference_payload = load_real_reference_inputs()

    results: list[BaselineRunResult] = []
    for baseline_spec in baseline_specs:
        baseline_name = str(baseline_spec["name"])
        method_name = str(baseline_spec["builder_method"])
        method = getattr(builder, method_name, None)
        if method is None:
            raise ValueError(f"Baseline builder method is not available: {method_name}")

        output = method(inputs)
        notes = dict(output.notes)
        notes["reference_type"] = "real_public_COMES-F_workbook"
        result = BaselineRunResult(
            name=baseline_name,
            seed=seed,
            matrix_shape=tuple(int(x) for x in output.total_matrix.shape),
            metrics=compute_metrics(metric_names, output.total_matrix, reference),
            notes=notes,
        )
        results.append(result)

    payload = {
        "experiment_name": config.get("experiment_name", "exp001_baseline_comparison"),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "seed": seed,
        "reference": {
            "name": "comes_f_public_workbook_symmetrized",
            "shape": list(reference.shape),
            "source": str(REAL_COMES_F_PATH.relative_to(REPO_ROOT)),
            "metadata": reference_payload["metadata"],
        },
        "results": [asdict(item) for item in results],
        "comparison_to_placeholder": comparison_to_placeholder(results),
    }
    return payload


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    headers = ["baseline", "mae", "frobenius", "diag_share", "reciprocity"]
    rows = [headers]
    for result in payload["results"]:
        assortativity = result["metrics"].get("age_assortativity", {})
        rows.append(
            [
                result["name"],
                f"{result['metrics'].get('matrix_mae', float('nan')):.4f}",
                f"{result['metrics'].get('matrix_frobenius_distance', float('nan')):.4f}",
                f"{assortativity.get('diagonal_share', float('nan')):.4f}",
                f"{result['metrics'].get('reciprocity_gap', float('nan')):.4f}",
            ]
        )
    widths = [max(len(str(row[idx])) for row in rows) for idx in range(len(headers))]
    formatted_rows = []
    for row_index, row in enumerate(rows):
        formatted_rows.append("  ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row)))
        if row_index == 0:
            formatted_rows.append("  ".join("-" * width for width in widths))
    return "\n".join(formatted_rows)


def _window(age_axis: np.ndarray, lower: float, upper: float) -> np.ndarray:
    profile = ((age_axis >= lower) & (age_axis <= upper)).astype(float)
    if profile.size <= 2:
        return profile
    kernel = np.array([0.25, 0.50, 0.25], dtype=float)
    padded = np.pad(profile, pad_width=1, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _band_matrix(profile: np.ndarray, width: float) -> np.ndarray:
    idx = np.arange(profile.size, dtype=float)
    distance = np.abs(idx[:, None] - idx[None, :])
    return np.outer(profile, profile) * np.exp(-(distance**2) / max(2.0 * width**2, 1e-9))


def _outer(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.outer(np.asarray(left, dtype=float), np.asarray(right, dtype=float))


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    arr = 0.5 * (np.asarray(matrix, dtype=float) + np.asarray(matrix, dtype=float).T)
    total = float(arr.sum())
    if total <= 0.0:
        return np.zeros_like(arr)
    return arr / total


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
