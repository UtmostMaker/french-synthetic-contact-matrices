"""Generate publication-ready exp001/exp004 figures from real COMES-F results.

Usage:
    python3 scripts/generate_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / ".vendor"
SRC_ROOT = REPO_ROOT / "src"
if VENDOR_ROOT.exists() and str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from contact_matrix_fr.baselines import BaselineBuilder  # noqa: E402
from contact_matrix_fr.optimized_baseline import OptimizedBaselineBuilder  # noqa: E402
from run_exp001 import load_real_reference_inputs  # noqa: E402


EXP001_REAL_RESULTS_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp001_real_results.json"
EXP004_RESULTS_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp004_optimized_baseline_results.json"
FIGURES_DIR = REPO_ROOT / "manuscript" / "figures"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed JSON payload: {path}")
    return payload


def reconstruct_matrices() -> tuple[dict[str, np.ndarray], list[str]]:
    inputs, reference, reference_payload = load_real_reference_inputs()
    baseline_builder = BaselineBuilder()
    optimized_builder = OptimizedBaselineBuilder()

    demographic = baseline_builder.demographic_scaling(inputs).total_matrix
    heuristic = baseline_builder.household_rule_based(inputs).total_matrix

    exp004_payload = load_json(EXP004_RESULTS_PATH)
    optimized_weights = {
        key: float(value)
        for key, value in exp004_payload["optimized_baseline"]["weights"].items()
    }
    optimized_components = optimized_builder.build_components(inputs)
    optimized = optimized_builder.combine_components(optimized_components, optimized_weights)

    age_labels = list(reference_payload.get("age_labels", []))
    if not age_labels:
        age_labels = [str(idx) for idx in range(reference.shape[0])]

    return {
        "Référence COMES-F": reference,
        "Repondération démographique": demographic,
        "Baseline ménage heuristique": heuristic,
        "Baseline ménage optimisée": optimized,
    }, age_labels


def metric_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    exp001_payload = load_json(EXP001_REAL_RESULTS_PATH)
    exp004_payload = load_json(EXP004_RESULTS_PATH)
    return exp001_payload, exp004_payload


def generate_with_matplotlib(
    matrices: dict[str, np.ndarray],
    age_labels: list[str],
    exp001_payload: dict[str, Any],
    exp004_payload: dict[str, Any],
) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 9,
        }
    )
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []

    names = list(matrices.keys())
    all_values = np.concatenate([matrix.ravel() for matrix in matrices.values()])
    positive_values = all_values[all_values > 0.0]
    vmin = float(max(np.quantile(positive_values, 0.01), 1e-3))
    vmax = float(np.quantile(positive_values, 0.995))
    tick_positions = list(range(0, len(age_labels), 2))
    if tick_positions[-1] != len(age_labels) - 1:
        tick_positions.append(len(age_labels) - 1)

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 9.8), constrained_layout=True)
    for ax, name in zip(axes.flat, names, strict=True):
        matrix = matrices[name]
        im = ax.imshow(
            matrix,
            origin="lower",
            cmap="cividis",
            norm=LogNorm(vmin=vmin, vmax=vmax),
            interpolation="nearest",
        )
        ax.set_title(name, fontsize=12)
        ax.set_xticks(tick_positions, [age_labels[idx] for idx in tick_positions], rotation=35, ha="right")
        ax.set_yticks(tick_positions, [age_labels[idx] for idx in tick_positions])
        ax.set_xlabel("Âge cible")
        ax.set_ylabel("Âge source")
        ax.grid(False)
    cbar = fig.colorbar(im, ax=axes, shrink=0.9)
    cbar.set_label("Intensité de contact, échelle logarithmique commune")
    heatmap_path = FIGURES_DIR / "exp001_heatmaps.png"
    fig.suptitle("Matrices de contact sur COMES-F réel", fontsize=14, fontweight="bold")
    fig.savefig(heatmap_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    saved_paths.append(heatmap_path)

    exp001_lookup = {result["name"]: result["metrics"] for result in exp001_payload["results"]}
    heuristic_metrics = exp004_payload["heuristic_baseline"]["metrics"]
    optimized_metrics = exp004_payload["optimized_baseline"]["metrics"]
    metric_lookup = {
        "Repondération démographique": exp001_lookup["demographic_scaling"],
        "Ménage heuristique": heuristic_metrics,
        "Ménage optimisé": optimized_metrics,
    }
    colors = ["#4e79a7", "#f28e2b", "#59a14f"]
    labels = list(metric_lookup.keys())

    metric_specs = [
        ("matrix_mae", "MAE", True),
        ("matrix_frobenius_distance", "Distance de Frobenius", True),
        ("diagonal_share", "Part diagonale", False),
        ("reciprocity_gap", "Écart de réciprocité", False),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.3), constrained_layout=True)
    for ax, (metric_key, metric_title, use_log_scale) in zip(axes.flat, metric_specs, strict=True):
        if metric_key == "diagonal_share":
            values = [float(metric_lookup[label]["age_assortativity"]["diagonal_share"]) for label in labels]
        else:
            values = [float(metric_lookup[label][metric_key]) for label in labels]
        bars = ax.bar(labels, values, color=colors, width=0.62)
        axis_title = metric_title + (" (échelle log)" if use_log_scale else "")
        ax.set_title(axis_title)
        ax.tick_params(axis="x", rotation=0)
        ax.grid(axis="y", alpha=0.22)
        if use_log_scale:
            ax.set_yscale("log")
        for bar, value in zip(bars, values, strict=True):
            y_value = value * (1.10 if use_log_scale else 1.02)
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y_value,
                f"{value:.2f}" if value >= 0.1 else f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    metrics_path = FIGURES_DIR / "exp001_metrics.png"
    fig.suptitle("Comparaison quantitative des modèles statiques", fontsize=14, fontweight="bold")
    fig.savefig(metrics_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    saved_paths.append(metrics_path)

    age_idx = np.arange(next(iter(matrices.values())).shape[0])

    def assortativity_profile(matrix: np.ndarray) -> np.ndarray:
        row_sum = np.clip(matrix.sum(axis=1), a_min=1e-9, a_max=None)
        return np.diag(matrix) / row_sum

    fig, ax = plt.subplots(figsize=(10.2, 5.6), constrained_layout=True)
    line_specs = [
        ("Référence COMES-F", "#2f2f2f", "o"),
        ("Repondération démographique", "#4c78a8", "s"),
        ("Baseline ménage heuristique", "#f58518", "^"),
        ("Baseline ménage optimisée", "#54a24b", "D"),
    ]
    for name, color, marker in line_specs:
        ax.plot(
            age_idx,
            assortativity_profile(matrices[name]),
            label=name,
            color=color,
            linewidth=2.0,
            marker=marker,
            markersize=4.2,
        )
    ax.set_xticks(tick_positions, [age_labels[idx] for idx in tick_positions], rotation=45, ha="right")
    ax.set_xlabel("Classe d'âge")
    ax.set_ylabel("Part des contacts sur la diagonale")
    ax.set_title("Profil d'assortativité par âge")
    ax.grid(alpha=0.25)
    ax.legend(frameon=True, ncols=2)
    assort_path = FIGURES_DIR / "exp001_assortativity_profile.png"
    fig.savefig(assort_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    saved_paths.append(assort_path)

    return saved_paths


def main() -> int:
    matrices, age_labels = reconstruct_matrices()
    exp001_payload, exp004_payload = metric_payloads()
    paths = generate_with_matplotlib(matrices, age_labels, exp001_payload, exp004_payload)

    print("Figures générées:")
    for path in paths:
        print(f"- {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
