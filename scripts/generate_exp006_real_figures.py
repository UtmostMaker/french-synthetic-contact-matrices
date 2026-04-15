#!/usr/bin/env python3
"""Generate final exp006 figures from real OmniMart/Claude results."""

from __future__ import annotations

import csv
import json
import sys
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

from contact_matrix_fr.agent_profiles import load_profiles

RESULTS_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp006_llm_agents_results.json"
MOBILITY_PATH = REPO_ROOT / "data" / "interim" / "google_mobility_france.csv"
FIGURES_DIR = REPO_ROOT / "manuscript" / "figures"
FIGURE_MOBILITY = FIGURES_DIR / "exp006_llm_vs_observed_mobility_by_policy.png"
FIGURE_RANKING = FIGURES_DIR / "exp006_profile_responsiveness_ranking.png"
FIGURE_BIAS = FIGURES_DIR / "exp006_social_bias_analysis.png"

POLICY_LABELS = {
    "pre_pandemic_baseline": "Pré-pandémie",
    "first_lockdown": "1er confinement",
    "deconfinement_summer_2020": "Déconfinement",
    "second_wave_restrictions": "Deuxième vague",
    "curfew_winter_2020_2021": "Couvre-feu",
    "pass_sanitaire_summer_2021": "Passe sanitaire",
}

MOBILITY_KEY_MAP = {
    "pass_sanitaire_summer_2021": "pass_sanitaire",
}

RESTRICTIVE_PERIODS = [
    "first_lockdown",
    "second_wave_restrictions",
    "curfew_winter_2020_2021",
]


def load_results() -> dict:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def load_mobility_observed() -> dict[str, float]:
    observed: dict[str, float] = {}
    with MOBILITY_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            observed[str(row["policy_period"])] = float(row["observed_mobility_reduction"])
    return observed


def profile_labels() -> dict[str, str]:
    return {profile.key: profile.display_label for profile in load_profiles()}


def generate_mobility_figure(results: dict, observed_lookup: dict[str, float]) -> None:
    period_averages = results["metrics"]["period_averages"]
    keys = list(period_averages.keys())
    predicted = [period_averages[key]["mobility_reduction"] for key in keys]
    observed = [observed_lookup[MOBILITY_KEY_MAP.get(key, key)] for key in keys]
    masks = [period_averages[key]["mask_adherence"] for key in keys]
    x = np.arange(len(keys))

    fig, ax = plt.subplots(figsize=(10.2, 5.2), constrained_layout=True)
    ax.plot(x, predicted, marker="o", linewidth=2.4, color="#225ea8", label="LLM, réduction de mobilité")
    ax.plot(x, observed, marker="s", linewidth=2.2, color="#d7301f", label="Google Mobility, réduction observée")
    ax.plot(x, masks, marker="^", linewidth=1.8, linestyle="--", color="#238b45", label="LLM, adhésion au masque")
    ax.set_xticks(x, [POLICY_LABELS[key] for key in keys], rotation=20, ha="right")
    ax.set_ylim(0.0, 0.9)
    ax.set_ylabel("Score agrégé")
    ax.set_title("Réponse moyenne des agents LLM selon les régimes sanitaires")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncols=1)
    fig.savefig(FIGURE_MOBILITY, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_responsiveness_figure(results: dict, labels_lookup: dict[str, str]) -> None:
    responsiveness = results["metrics"]["profile_responsiveness"]
    ranked = sorted(responsiveness.items(), key=lambda item: item[1])
    keys = [key for key, _ in ranked]
    values = [value for _, value in ranked]
    labels = [labels_lookup.get(key, key.replace("_", " ")) for key in keys]
    colors = ["#ca0020" if value >= 0.55 else "#0571b0" if value <= 0.35 else "#808080" for value in values]

    fig, ax = plt.subplots(figsize=(10.5, 8.0), constrained_layout=True)
    y = np.arange(len(keys))
    ax.barh(y, values, color=colors)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Réactivité moyenne entre pré-pandémie et premier confinement")
    ax.set_title("Classement des profils selon leur capacité d'ajustement")
    ax.grid(axis="x", alpha=0.25)
    ax.axvline(0.394, color="#444444", linestyle=":", linewidth=1.4)
    ax.text(0.402, len(keys) - 1.2, "écart cadre/agriculteur = 0,394", fontsize=9, color="#444444")
    fig.savefig(FIGURE_RANKING, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_bias_figure(results: dict) -> None:
    scores = results["profile_scores"]
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
            value = float(np.mean([scores[profile_key][period][metric_key] for period in RESTRICTIVE_PERIODS]))
            summary[label].append(value)

    x = np.arange(len(metrics))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    ax.bar(x - width / 2, summary["Cadre 35-49 en couple avec enfants"], width=width, color="#7b3294", label="Cadre 35-49")
    ax.bar(x + width / 2, summary["Agriculteur 50-64 en couple"], width=width, color="#008837", label="Agriculteur 50-64")
    ax.set_xticks(x, list(metrics.keys()))
    ax.set_ylim(0.0, 0.9)
    ax.set_ylabel("Moyenne sur les périodes restrictives")
    ax.set_title("Contraste social sur trois dimensions du comportement")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(FIGURE_BIAS, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    results = load_results()
    observed_lookup = load_mobility_observed()
    labels_lookup = profile_labels()
    plt.style.use("seaborn-v0_8-whitegrid")
    generate_mobility_figure(results, observed_lookup)
    generate_responsiveness_figure(results, labels_lookup)
    generate_bias_figure(results)
    print("Figures générées:")
    for path in [FIGURE_MOBILITY, FIGURE_RANKING, FIGURE_BIAS]:
        print(f"- {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
