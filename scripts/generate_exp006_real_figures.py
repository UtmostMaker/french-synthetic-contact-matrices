#!/usr/bin/env python3
"""Generate publication figures for exp006 from the archived JSON artifact."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / ".vendor"
SRC_ROOT = REPO_ROOT / "src"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp006_llm_agents_results.json"
FIGURES_DIR = REPO_ROOT / "manuscript" / "figures"
FIGURE_MOBILITY = FIGURES_DIR / "exp006_llm_vs_observed_mobility_by_policy.png"
FIGURE_RANKING = FIGURES_DIR / "exp006_profile_responsiveness_ranking.png"
FIGURE_BIAS = FIGURES_DIR / "exp006_social_bias_analysis.png"
FIGURE_COVIPREV = FIGURES_DIR / "exp006_llm_vs_coviprev_by_profile.png"

BLUE = "#4e79a7"
ORANGE = "#f28e2b"
GREEN = "#59a14f"
RED = "#e15759"
PURPLE = "#b07aa1"
GRAY = "#9d9da1"

POLICY_LABELS = {
    "pre_pandemic_baseline": "Pré-pandémie",
    "first_lockdown": "1er confinement",
    "deconfinement_summer_2020": "Déconfinement",
    "second_wave_restrictions": "Deuxième vague",
    "curfew_winter_2020_2021": "Couvre-feu",
    "pass_sanitaire": "Passe sanitaire",
}

RESPONSIVENESS_FIELDS = [
    "mobility_reduction",
    "social_distancing",
    "mask_adherence",
    "risk_perception",
    "trust_in_measures",
]

RESTRICTIVE_PERIODS = [
    "second_wave_restrictions",
    "curfew_winter_2020_2021",
    "pass_sanitaire",
]


def load_results() -> dict:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def weights_lookup(results: dict) -> dict[str, float]:
    return {row["profile_key"]: float(row["population_weight"]) for row in results["profile_summary"]}


def grouped_scores(results: dict) -> dict[str, dict[str, dict]]:
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in results["profile_regime_scores"]:
        grouped[row["profile_key"]][row["policy_regime"]] = row
    return grouped


def weighted_period_mean(results: dict, regime: str, field: str) -> float:
    weights = weights_lookup(results)
    rows = [row for row in results["profile_regime_scores"] if row["policy_regime"] == regime]
    total = sum(weights[row["profile_key"]] for row in rows)
    if total <= 0.0:
        return 0.0
    return float(sum(weights[row["profile_key"]] * float(row[field]) for row in rows) / total)


def responsiveness_ranking(results: dict) -> list[tuple[str, str, float]]:
    grouped = grouped_scores(results)
    ranking: list[tuple[str, str, float]] = []
    labels = {row["profile_key"]: row["profile_label"] for row in results["profile_summary"]}
    for profile_key, periods in grouped.items():
        baseline = periods.get("pre_pandemic_baseline")
        lockdown = periods.get("first_lockdown")
        if not baseline or not lockdown:
            continue
        delta = float(np.mean([float(lockdown[field]) - float(baseline[field]) for field in RESPONSIVENESS_FIELDS]))
        ranking.append((profile_key, labels.get(profile_key, profile_key), delta))
    ranking.sort(key=lambda item: item[2])
    return ranking


def generate_mobility_figure(results: dict) -> None:
    aggregated = results["aggregated_predictions"]
    keys = [row["policy_regime"] for row in aggregated]
    predicted = [float(row["predicted_mobility_reduction"]) for row in aggregated]
    observed = [float(row["observed_mobility_reduction"]) for row in aggregated]
    masks = [weighted_period_mean(results, key, "mask_adherence") for key in keys]
    x = np.arange(len(keys))

    fig, ax = plt.subplots(figsize=(10.4, 5.4), constrained_layout=True)
    ax.plot(x, predicted, marker="o", linewidth=2.4, color=BLUE, label="LLM, réduction de mobilité")
    ax.plot(x, observed, marker="s", linewidth=2.2, color=ORANGE, label="Google Mobility, réduction observée")
    ax.plot(x, masks, marker="^", linewidth=1.8, linestyle="--", color=GREEN, label="LLM, adhésion au masque")
    ax.set_xticks(x, [POLICY_LABELS[key] for key in keys], rotation=20, ha="right")
    ax.set_ylim(0.0, 0.9)
    ax.set_ylabel("Score agrégé (0-1)")
    ax.set_title("Réponse moyenne des agents LLM selon les régimes sanitaires")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(FIGURE_MOBILITY, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_ranking_figure(results: dict) -> None:
    ranked = responsiveness_ranking(results)
    labels = [item[1] for item in ranked]
    values = [item[2] for item in ranked]
    colors = [RED if value >= 0.55 else BLUE if value <= 0.35 else GRAY for value in values]

    fig, ax = plt.subplots(figsize=(10.6, 7.8), constrained_layout=True)
    y = np.arange(len(labels))
    ax.barh(y, values, color=colors)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Réactivité moyenne entre pré-pandémie et premier confinement")
    ax.set_title("Classement des profils selon leur capacité d'ajustement")
    ax.grid(axis="x", alpha=0.25)
    ax.axvline(0.394, color="#444444", linestyle=":", linewidth=1.4)
    ax.text(0.402, len(labels) - 1.2, "écart cadre/agriculteur = 0,394", fontsize=9, color="#444444")
    ax.text(values[-1] + 0.008, y[-1], f"{values[-1]:.3f}", va="center", fontsize=8.5, color="#222222")
    ax.text(values[0] + 0.008, y[0], f"{values[0]:.3f}", va="center", fontsize=8.5, color="#222222")
    fig.savefig(FIGURE_RANKING, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_bias_figure(results: dict) -> None:
    grouped = grouped_scores(results)
    profile_pair = {
        "Cadre 35-49 en couple avec enfants": "cadre_35_49_couple_enfants",
        "Agriculteur 50-64 en couple": "agriculteur_50_64_couple",
    }
    metrics = {
        "Réduction de mobilité": "mobility_reduction",
        "Adhésion au masque": "mask_adherence",
        "Confiance dans les mesures": "trust_in_measures",
    }

    summary: dict[str, list[float]] = {}
    for label, profile_key in profile_pair.items():
        summary[label] = []
        for metric_key in metrics.values():
            value = float(np.mean([grouped[profile_key][period][metric_key] for period in RESTRICTIVE_PERIODS]))
            summary[label].append(value)

    x = np.arange(len(metrics))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    left = ax.bar(x - width / 2, summary["Cadre 35-49 en couple avec enfants"], width=width, color=PURPLE, label="Cadre 35-49")
    right = ax.bar(x + width / 2, summary["Agriculteur 50-64 en couple"], width=width, color=GREEN, label="Agriculteur 50-64")
    ax.set_xticks(x, list(metrics.keys()))
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Score moyen (0-1) sur les périodes restrictives")
    ax.set_title("Contraste social sur trois dimensions du comportement")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    ax.bar_label(left, fmt="%.2f", padding=3, fontsize=8)
    ax.bar_label(right, fmt="%.2f", padding=3, fontsize=8)
    fig.savefig(FIGURE_BIAS, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_coviprev_profile_figure(results: dict) -> None:
    summary = sorted(results["profile_summary"], key=lambda item: float(item["predicted_behavior_index"]))
    labels = [item["profile_label"] for item in summary]
    llm_values = [float(item["predicted_behavior_index"]) for item in summary]
    target_values = [float(item["coviprev_aligned_target"]) for item in summary]
    x = np.arange(len(labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(13.0, 5.4), constrained_layout=True)
    ax.bar(x - width / 2, llm_values, width=width, color="#4c78a8", label="Indice LLM")
    ax.bar(x + width / 2, target_values, width=width, color="#f58518", label="Cible indirecte alignée CoviPrev")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("Indice de prévention")
    ax.set_title("Comparaison profilée entre sorties LLM et cibles indirectes")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(FIGURE_COVIPREV, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
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
    results = load_results()
    generate_mobility_figure(results)
    generate_ranking_figure(results)
    generate_bias_figure(results)
    generate_coviprev_profile_figure(results)
    print("Figures générées:")
    for path in [FIGURE_MOBILITY, FIGURE_RANKING, FIGURE_BIAS, FIGURE_COVIPREV]:
        print(f"- {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
