"""Run exp006: LLM-based socio-demographic behavioral agents calibrated on French mobility and CoviPrev data."""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections import defaultdict
from datetime import date
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

import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.agent_profiles import load_profiles  # noqa: E402
from contact_matrix_fr.llm_behavioral_agent import LLMBehavioralAgent, POLICY_REGIMES  # noqa: E402
from contact_matrix_fr.mobility_loader import ensure_google_france_mobility_csv, load_google_france_mobility  # noqa: E402
from contact_matrix_fr.time_series_loader import load_coviprev_waves  # noqa: E402

CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp006_llm_agents.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp006_llm_agents_results.json"
FIGURE_DIR = REPO_ROOT / "manuscript" / "figures"
FIGURE_MOBILITY = FIGURE_DIR / "exp006_llm_vs_observed_mobility_by_policy.png"
FIGURE_COVIPREV = FIGURE_DIR / "exp006_llm_vs_coviprev_by_profile.png"
FIGURE_BIAS = FIGURE_DIR / "exp006_social_bias_analysis.png"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or not config:
        raise ValueError("Experiment config is empty or malformed")
    return config


def weighted_average(values: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return 0.0
    return float(sum(value * weight for value, weight in values) / total_weight)


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


def regime_label(regime_key: str) -> str:
    return str(POLICY_REGIMES[regime_key]["label"])


def prevention_index(mask: float, distancing: float, risk: float, trust: float) -> float:
    return float(np.clip(0.40 * mask + 0.25 * distancing + 0.20 * risk + 0.15 * trust, 0.0, 1.0))


def build_indirect_profile_targets(profiles: list[Any], national_target: float) -> dict[str, float]:
    targets: dict[str, float] = {}
    for profile in profiles:
        raw = national_target * (0.55 + 0.30 * profile.trust_proxy + 0.20 * profile.preventive_behavior_multiplier)
        targets[profile.key] = float(np.clip(raw, 0.0, 1.0))
    return targets


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    ensure_google_france_mobility_csv()
    mobility_rows = load_google_france_mobility()
    coviprev = load_coviprev_waves(REPO_ROOT / "data" / "interim" / "coviprev_behavior_france.csv")
    profiles = load_profiles()

    model_cfg = dict(config.get("model", {}))
    agent = LLMBehavioralAgent(
        model=str(model_cfg.get("name", "claude-sonnet-4-6")),
        fallback_models=tuple(model_cfg.get("fallback_models", ["claude-sonnet-4-6-20260415", "claude-sonnet-4.5", "claude-sonnet-4"])),
        base_url=str(model_cfg.get("base_url", "https://api-provider.example/v1")),
        api_key_env=str(model_cfg.get("api_key_env", "LLM_API_KEY")),
        thinking=str(model_cfg.get("thinking", "low")),
        request_pause_seconds=float(model_cfg.get("request_pause_seconds", 0.8)),
        timeout_seconds=int(model_cfg.get("timeout_seconds", 90)),
    )

    policy_order = [
        "pre_pandemic_baseline",
        "first_lockdown",
        "deconfinement_summer_2020",
        "second_wave_restrictions",
        "curfew_winter_2020_2021",
        "pass_sanitaire",
    ]

    profile_regime_scores: list[dict[str, Any]] = []
    generation_modes: set[str] = set()
    for profile in profiles:
        for regime in policy_order:
            score = agent.generate(profile, regime, force_refresh=bool(model_cfg.get("force_refresh", False)))
            generation_modes.add(score.generation_mode)
            profile_regime_scores.append(
                {
                    "profile_key": profile.key,
                    "profile_label": profile.display_label,
                    "age_range": profile.age_range,
                    "occupation": profile.occupation,
                    "household_type": profile.household_type,
                    "policy_regime": regime,
                    "policy_label": regime_label(regime),
                    "mobility_reduction": score.mobility_reduction,
                    "social_distancing": score.social_distancing,
                    "mask_adherence": score.mask_adherence,
                    "risk_perception": score.risk_perception,
                    "trust_in_measures": score.trust_in_measures,
                    "generation_mode": score.generation_mode,
                }
            )

    by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in profile_regime_scores:
        by_regime[row["policy_regime"]].append(row)

    aggregated_predictions: list[dict[str, Any]] = []
    predicted_mobility_series: list[float] = []
    observed_mobility_series: list[float] = []
    predicted_behavior_series: list[float] = []
    observed_behavior_series: list[float] = []

    mobility_lookup = {item.policy_period: item for item in mobility_rows}

    for regime in policy_order:
        rows = by_regime[regime]
        mobility_pred = weighted_average([(row["mobility_reduction"], _profile_weight(profiles, row["profile_key"])) for row in rows])
        behavior_pred = weighted_average(
            [
                (
                    prevention_index(
                        row["mask_adherence"],
                        row["social_distancing"],
                        row["risk_perception"],
                        row["trust_in_measures"],
                    ),
                    _profile_weight(profiles, row["profile_key"]),
                )
                for row in rows
            ]
        )

        observed_mobility = mobility_lookup.get(regime)
        mobility_value = float(observed_mobility.observed_mobility_reduction) if observed_mobility else math.nan
        matching_waves = []
        if observed_mobility:
            start = date.fromisoformat(observed_mobility.start_date)
            end = date.fromisoformat(observed_mobility.end_date)
            matching_waves = [wave for wave in coviprev if start <= date.fromisoformat(wave.midpoint_date) <= end]
        behavior_value = float(np.mean([wave.observed_prevention_index for wave in matching_waves])) if matching_waves else math.nan

        aggregated_predictions.append(
            {
                "policy_regime": regime,
                "policy_label": regime_label(regime),
                "predicted_mobility_reduction": mobility_pred,
                "observed_mobility_reduction": mobility_value,
                "predicted_prevention_index": behavior_pred,
                "observed_coviprev_prevention_index": behavior_value,
                "coviprev_waves": [wave.wave for wave in matching_waves],
            }
        )
        if not math.isnan(mobility_value):
            predicted_mobility_series.append(mobility_pred)
            observed_mobility_series.append(mobility_value)
        if not math.isnan(behavior_value):
            predicted_behavior_series.append(behavior_pred)
            observed_behavior_series.append(behavior_value)

    overall_behavior_target = float(np.mean(observed_behavior_series)) if observed_behavior_series else 0.0
    indirect_targets = build_indirect_profile_targets(profiles, overall_behavior_target)
    profile_summary: list[dict[str, Any]] = []
    for profile in profiles:
        rows = [row for row in profile_regime_scores if row["profile_key"] == profile.key]
        predicted_profile_behavior = float(
            np.mean(
                [
                    prevention_index(
                        row["mask_adherence"],
                        row["social_distancing"],
                        row["risk_perception"],
                        row["trust_in_measures"],
                    )
                    for row in rows
                    if row["policy_regime"] != "pre_pandemic_baseline"
                ]
            )
        )
        profile_summary.append(
            {
                "profile_key": profile.key,
                "profile_label": profile.display_label,
                "age_range": profile.age_range,
                "occupation": profile.occupation,
                "household_type": profile.household_type,
                "population_weight": profile.population_weight,
                "predicted_behavior_index": predicted_profile_behavior,
                "coviprev_aligned_target": indirect_targets[profile.key],
                "absolute_error": abs(predicted_profile_behavior - indirect_targets[profile.key]),
                "trust_proxy": profile.trust_proxy,
                "mobility_constraint": profile.mobility_constraint,
                "source_summary": profile.source_summary,
                "source_urls": list(profile.source_urls),
            }
        )

    profile_errors = sorted(profile_summary, key=lambda item: item["absolute_error"])
    restrictive_regimes = {"first_lockdown", "second_wave_restrictions", "curfew_winter_2020_2021", "pass_sanitaire"}

    def mean_for(occupations: set[str], field: str) -> float:
        values = [
            row[field]
            for row in profile_regime_scores
            if row["occupation"] in occupations and row["policy_regime"] in restrictive_regimes
        ]
        return float(np.mean(values)) if values else 0.0

    privileged_occupations = {"cadre", "profession_intermediaire"}
    constrained_occupations = {"ouvrier", "employe", "chomeur", "inactive_au_foyer"}
    bias_analysis = {
        "privileged_mean_trust_in_measures": mean_for(privileged_occupations, "trust_in_measures"),
        "constrained_mean_trust_in_measures": mean_for(constrained_occupations, "trust_in_measures"),
        "privileged_mean_mobility_reduction": mean_for(privileged_occupations, "mobility_reduction"),
        "constrained_mean_mobility_reduction": mean_for(constrained_occupations, "mobility_reduction"),
    }
    bias_analysis["trust_gap_privileged_minus_constrained"] = (
        bias_analysis["privileged_mean_trust_in_measures"] - bias_analysis["constrained_mean_trust_in_measures"]
    )
    bias_analysis["mobility_gap_privileged_minus_constrained"] = (
        bias_analysis["privileged_mean_mobility_reduction"] - bias_analysis["constrained_mean_mobility_reduction"]
    )
    bias_analysis["verdict"] = (
        "inequality_reproduced"
        if bias_analysis["trust_gap_privileged_minus_constrained"] > 0.08 and bias_analysis["mobility_gap_privileged_minus_constrained"] > 0.05
        else "inequality_flattened_or_small"
    )

    metrics_payload = {
        "mobility_correlation": pearson_correlation(predicted_mobility_series, observed_mobility_series),
        "mobility_mae": float(metrics.series_mae(np.asarray(predicted_mobility_series), np.asarray(observed_mobility_series))),
        "mobility_directional_agreement": float(metrics.trend_direction_agreement(np.asarray(predicted_mobility_series), np.asarray(observed_mobility_series))),
        "coviprev_behavior_mae": float(metrics.series_mae(np.asarray(predicted_behavior_series), np.asarray(observed_behavior_series))),
        "coviprev_behavior_directional_agreement": float(metrics.trend_direction_agreement(np.asarray(predicted_behavior_series), np.asarray(observed_behavior_series))),
        "profile_target_mae": float(np.mean([item["absolute_error"] for item in profile_summary])),
        "n_profiles": len(profiles),
        "n_profile_regime_pairs": len(profile_regime_scores),
    }

    payload = {
        "experiment_name": str(config.get("experiment_name", "exp006_llm_agents")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "llm_provider": {
            "provider": "external_llm_api",
            "api_base": str(model_cfg.get("base_url", "https://api-provider.example/v1")),
            "api_format": "OpenAI-compatible chat.completions",
            "primary_model": str(model_cfg.get("name", "claude-sonnet-4-6")),
            "fallback_models": list(model_cfg.get("fallback_models", ["claude-sonnet-4-6-20260415", "claude-sonnet-4.5", "claude-sonnet-4"])),
            "api_key_env": str(model_cfg.get("api_key_env", "LLM_API_KEY")),
        },
        "data_sources": {
            "google_mobility": "Official Google Community Mobility Reports regional archive for France national rows.",
            "coviprev": "Public CoviPrev extract already curated in data/interim/coviprev_behavior_france.csv.",
            "profiles": "Approximate INSEE and Dares anchored socio-demographic priors, documented per profile and kept explicit rather than inferred from unavailable joint microdata.",
        },
        "generation_modes": sorted(generation_modes),
        "aggregated_predictions": aggregated_predictions,
        "profile_regime_scores": profile_regime_scores,
        "profile_summary": profile_summary,
        "metrics": metrics_payload,
        "bias_analysis": bias_analysis,
        "assessment": {
            "best_aligned_profiles": [item["profile_key"] for item in profile_errors[:3]],
            "least_aligned_profiles": [item["profile_key"] for item in profile_errors[-3:]],
            "honest_summary": (
                "The experiment now uses real external LLM calls when LLM_API_KEY is available. "
                "Profile targets remain indirect because the public CoviPrev extract used here is national rather than fully stratified by socio-professional category, so the profile-level fit should be read as plausibility calibration rather than identification."
            ),
        },
    }

    save_results(payload, OUTPUT_PATH)
    generate_figures(payload)
    return payload


def _profile_weight(profiles: list[Any], profile_key: str) -> float:
    for profile in profiles:
        if profile.key == profile_key:
            return float(profile.population_weight)
    return 0.0


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def generate_figures(payload: dict[str, Any]) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    aggregated = payload["aggregated_predictions"]
    labels = [item["policy_label"] for item in aggregated]
    x = np.arange(len(labels))

    plt.figure(figsize=(10.5, 4.8))
    plt.plot(x, [item["predicted_mobility_reduction"] for item in aggregated], marker="o", linewidth=2.0, label="LLM agents")
    plt.plot(x, [item["observed_mobility_reduction"] for item in aggregated], marker="s", linewidth=2.0, label="Google Mobility")
    plt.xticks(x, labels, rotation=30, ha="right")
    plt.ylabel("Mobility reduction index")
    plt.title("LLM vs observed mobility by policy period")
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(FIGURE_MOBILITY, dpi=220)
    plt.close()

    profile_summary = payload["profile_summary"]
    labels = [item["profile_label"] for item in profile_summary]
    llm_values = [item["predicted_behavior_index"] for item in profile_summary]
    target_values = [item["coviprev_aligned_target"] for item in profile_summary]
    x = np.arange(len(labels))
    width = 0.38
    plt.figure(figsize=(13.2, 5.2))
    plt.bar(x - width / 2, llm_values, width=width, label="LLM index")
    plt.bar(x + width / 2, target_values, width=width, label="CoviPrev-aligned target")
    plt.xticks(x, labels, rotation=35, ha="right")
    plt.ylabel("Preventive behavior index")
    plt.title("LLM vs CoviPrev-aligned behavior by profile")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(FIGURE_COVIPREV, dpi=220)
    plt.close()

    bias = payload["bias_analysis"]
    categories = ["Trust in measures", "Mobility reduction"]
    privileged = [bias["privileged_mean_trust_in_measures"], bias["privileged_mean_mobility_reduction"]]
    constrained = [bias["constrained_mean_trust_in_measures"], bias["constrained_mean_mobility_reduction"]]
    x = np.arange(len(categories))
    width = 0.34
    plt.figure(figsize=(7.2, 4.8))
    plt.bar(x - width / 2, privileged, width=width, label="Profils favorisés")
    plt.bar(x + width / 2, constrained, width=width, label="Profils contraints")
    plt.xticks(x, categories)
    plt.ylim(0.0, 1.0)
    plt.ylabel("Average score")
    plt.title("Social bias analysis")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(FIGURE_BIAS, dpi=220)
    plt.close()


def render_summary(payload: dict[str, Any]) -> str:
    metrics_payload = payload["metrics"]
    return (
        f"mobility_corr={metrics_payload['mobility_correlation']:.3f}\n"
        f"mobility_mae={metrics_payload['mobility_mae']:.3f}\n"
        f"coviprev_mae={metrics_payload['coviprev_behavior_mae']:.3f}\n"
        f"bias_verdict={payload['bias_analysis']['verdict']}\n"
        f"generation_modes={','.join(payload['generation_modes'])}"
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
