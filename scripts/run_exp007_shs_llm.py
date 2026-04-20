"""Run exp007: SHS-centered LLM mediation layer for epidemic diffusion."""

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

import numpy as np
import yaml

import contact_matrix_fr.metrics as metrics  # noqa: E402
from contact_matrix_fr.agent_profiles import SocioDemographicProfile, load_profiles  # noqa: E402
from contact_matrix_fr.behavioral_layer import BehavioralLayer, BehavioralState  # noqa: E402
from contact_matrix_fr.llm_behavioral_agent import POLICY_REGIMES  # noqa: E402
from contact_matrix_fr.llm_shs_agent import SHSBehavioralScore, SHSLLMBehavioralAgent  # noqa: E402
from contact_matrix_fr.mobility_loader import ensure_google_france_mobility_csv, load_google_france_mobility  # noqa: E402
from contact_matrix_fr.time_series_loader import load_coviprev_waves  # noqa: E402
from run_exp005 import load_optimized_base_matrix  # noqa: E402


CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "exp007_shs_llm.yaml"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "outputs" / "exp007_shs_llm_results.json"


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


def prevention_index(score: SHSBehavioralScore, weights: dict[str, float]) -> float:
    return float(
        np.clip(
            weights["mask"] * score.mask_adherence
            + weights["adherence"] * score.adherence_level
            + weights["risk"] * score.risk_perception
            + weights["trust"] * score.trust_in_authorities
            + weights["isolation"] * score.isolation_propensity,
            0.0,
            1.0,
        )
    )


def build_behavioral_state(score: SHSBehavioralScore) -> BehavioralState:
    return BehavioralState(
        adherence_level=float(score.adherence_level),
        risk_perception=float(score.risk_perception),
        trust_in_authorities=float(score.trust_in_authorities),
        policy_regime=str(score.policy_regime),
    )


def contact_multiplier(score: SHSBehavioralScore, layer: BehavioralLayer, participant_counts: np.ndarray, base_contact_level: float) -> float:
    state = build_behavioral_state(score)
    return float(layer.contact_ratio(state, participant_counts, base_contact_level))


def transmission_pressure(score: SHSBehavioralScore, layer: BehavioralLayer, participant_counts: np.ndarray, base_contact_level: float, weights: dict[str, float]) -> float:
    contact_ratio_value = contact_multiplier(score, layer, participant_counts, base_contact_level)
    prevention = prevention_index(score, weights)
    social_rebound = 0.10 * score.social_pressure + 0.08 * score.household_pressure + 0.10 * score.economic_constraint
    fatigue_penalty = 0.08 * score.policy_fatigue
    return float(np.clip(contact_ratio_value * (1.0 - 0.55 * prevention + social_rebound + fatigue_penalty), 0.0, 2.5))


def projected_diffusion_control(score: SHSBehavioralScore, layer: BehavioralLayer, participant_counts: np.ndarray, base_contact_level: float, weights: dict[str, float]) -> dict[str, float]:
    prevention = prevention_index(score, weights)
    contact_ratio_value = contact_multiplier(score, layer, participant_counts, base_contact_level)
    pressure = transmission_pressure(score, layer, participant_counts, base_contact_level, weights)
    return {
        "prevention_index": prevention,
        "contact_ratio": contact_ratio_value,
        "transmission_pressure": pressure,
    }


def _profile_weight(profiles: list[SocioDemographicProfile], profile_key: str) -> float:
    for profile in profiles:
        if profile.key == profile_key:
            return float(profile.population_weight)
    return 0.0


def summarize_records(records: list[dict[str, Any]], profiles: list[SocioDemographicProfile], metric_key: str, regime: str) -> float:
    subset = [row for row in records if row["policy_regime"] == regime]
    return weighted_average([(float(row[metric_key]), _profile_weight(profiles, str(row["profile_key"]))) for row in subset])


def compute_mae(observed: list[float], predicted: list[float]) -> float:
    return float(metrics.series_mae(np.asarray(predicted, dtype=float), np.asarray(observed, dtype=float)))


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    ensure_google_france_mobility_csv()
    mobility_rows = load_google_france_mobility()
    coviprev = load_coviprev_waves(REPO_ROOT / "data" / "interim" / "coviprev_behavior_france.csv")
    profiles = list(load_profiles())

    base_matrix, participant_counts, _, reference_payload = load_optimized_base_matrix()
    base_contact_level = float(np.dot(np.asarray(base_matrix.sum(axis=1), dtype=float), participant_counts / participant_counts.sum()))

    calibrated_parameters = dict(config.get("calibrated_behavioral_parameters", {}))
    layer = BehavioralLayer(base_matrix, [BehavioralState(0.5, 0.5, 0.5, "pre_pandemic_baseline")], parameters=calibrated_parameters)

    model_cfg = dict(config.get("model", {}))
    agent = SHSLLMBehavioralAgent(
        cache_dir=REPO_ROOT / str(model_cfg.get("cache_dir", "artifacts/cache/llm_shs_agent")),
        audit_dir=REPO_ROOT / str(model_cfg.get("audit_dir", "artifacts/audits/exp007_shs_llm")),
        protocol_path=REPO_ROOT / str(model_cfg.get("protocol_path", "experiments/protocols/exp007_shs_llm_protocol_v2.yaml")),
        backend=str(model_cfg.get("backend", "openai_compatible")),
        model=str(model_cfg.get("name", "openai/gpt-5.4-mini")),
        fallback_models=tuple(model_cfg.get("fallback_models", ["openai/gpt-5-mini"])),
        base_url=str(model_cfg.get("base_url", "https://openrouter.ai/api/v1")),
        api_key_env=str(model_cfg.get("api_key_env", "OPENROUTER_API_KEY")),
        provider_label=str(model_cfg.get("provider_label", "OpenRouter")),
        temperature=float(model_cfg.get("temperature", 0.2)),
        max_tokens=int(model_cfg.get("max_tokens", 280)),
        request_pause_seconds=float(model_cfg.get("request_pause_seconds", 0.8)),
        timeout_seconds=int(model_cfg.get("timeout_seconds", 90)),
        abort_on_fallback=bool(model_cfg.get("abort_on_fallback", False)),
        abort_on_auth_error=bool(model_cfg.get("abort_on_auth_error", True)),
        cli_command=str(model_cfg.get("cli_command", "claude")),
        cli_max_budget_usd=(None if model_cfg.get("cli_max_budget_usd") is None else float(model_cfg.get("cli_max_budget_usd"))),
        cli_permission_mode=str(model_cfg.get("cli_permission_mode", "bypassPermissions")),
        cli_output_format=str(model_cfg.get("cli_output_format", "json")),
        cli_tools=model_cfg.get("cli_tools", ""),
        auto_wait_on_rate_limit=bool(model_cfg.get("auto_wait_on_rate_limit", True)),
        rate_limit_reset_buffer_seconds=int(model_cfg.get("rate_limit_reset_buffer_seconds", 20)),
        rate_limit_poll_seconds=int(model_cfg.get("rate_limit_poll_seconds", 30)),
        rate_limit_max_wait_seconds=int(model_cfg.get("rate_limit_max_wait_seconds", 21600)),
    )

    mediation_weights = {
        "mask": float(config.get("mediation", {}).get("mask_weight", 0.25)),
        "adherence": float(config.get("mediation", {}).get("adherence_weight", 0.25)),
        "risk": float(config.get("mediation", {}).get("risk_weight", 0.18)),
        "trust": float(config.get("mediation", {}).get("trust_weight", 0.12)),
        "isolation": float(config.get("mediation", {}).get("isolation_weight", 0.20)),
    }

    policy_order = list(config.get("policy_order", [
        "pre_pandemic_baseline",
        "first_lockdown",
        "deconfinement_summer_2020",
        "second_wave_restrictions",
        "curfew_winter_2020_2021",
        "pass_sanitaire",
    ]))

    llm_profile_records: list[dict[str, Any]] = []
    heuristic_profile_records: list[dict[str, Any]] = []
    generation_modes: set[str] = set()
    total_pairs = len(profiles) * len(policy_order)
    pair_index = 0

    for profile in profiles:
        for regime in policy_order:
            pair_index += 1
            print(f"[exp007] pair {pair_index}/{total_pairs} | profile={profile.key} | regime={regime}", flush=True)
            llm_score = agent.generate(profile, regime, force_refresh=bool(model_cfg.get("force_refresh", False)))
            generation_modes.add(llm_score.generation_mode)
            print(f"[exp007] pair {pair_index}/{total_pairs} done | mode={llm_score.generation_mode}", flush=True)
            heuristic_score = agent.generate_heuristic(profile, regime)

            llm_projection = projected_diffusion_control(llm_score, layer, participant_counts, base_contact_level, mediation_weights)
            heuristic_projection = projected_diffusion_control(heuristic_score, layer, participant_counts, base_contact_level, mediation_weights)

            common = {
                "profile_key": profile.key,
                "profile_label": profile.display_label,
                "age_range": profile.age_range,
                "occupation": profile.occupation,
                "household_type": profile.household_type,
                "population_weight": profile.population_weight,
                "policy_regime": regime,
                "policy_label": regime_label(regime),
            }
            llm_profile_records.append(
                {
                    **common,
                    "generation_mode": llm_score.generation_mode,
                    "protocol_id": llm_score.protocol_id,
                    "prompt_version": llm_score.prompt_version,
                    "prompt_hash": llm_score.prompt_hash,
                    "audit_path": llm_score.audit_path,
                    "adherence_level": llm_score.adherence_level,
                    "risk_perception": llm_score.risk_perception,
                    "trust_in_authorities": llm_score.trust_in_authorities,
                    "mobility_reduction": llm_score.mobility_reduction,
                    "compliance_capacity": llm_score.compliance_capacity,
                    "economic_constraint": llm_score.economic_constraint,
                    "social_pressure": llm_score.social_pressure,
                    "household_pressure": llm_score.household_pressure,
                    "policy_fatigue": llm_score.policy_fatigue,
                    "mask_adherence": llm_score.mask_adherence,
                    "isolation_propensity": llm_score.isolation_propensity,
                    **llm_projection,
                }
            )
            heuristic_profile_records.append(
                {
                    **common,
                    "generation_mode": heuristic_score.generation_mode,
                    "adherence_level": heuristic_score.adherence_level,
                    "risk_perception": heuristic_score.risk_perception,
                    "trust_in_authorities": heuristic_score.trust_in_authorities,
                    "mobility_reduction": heuristic_score.mobility_reduction,
                    "compliance_capacity": heuristic_score.compliance_capacity,
                    "economic_constraint": heuristic_score.economic_constraint,
                    "social_pressure": heuristic_score.social_pressure,
                    "household_pressure": heuristic_score.household_pressure,
                    "policy_fatigue": heuristic_score.policy_fatigue,
                    "mask_adherence": heuristic_score.mask_adherence,
                    "isolation_propensity": heuristic_score.isolation_propensity,
                    **heuristic_projection,
                }
            )

    mobility_lookup = {item.policy_period: item for item in mobility_rows}
    aggregated: list[dict[str, Any]] = []
    observed_mobility_series: list[float] = []
    llm_mobility_series: list[float] = []
    heuristic_mobility_series: list[float] = []
    observed_prevention_series: list[float] = []
    llm_prevention_series: list[float] = []
    heuristic_prevention_series: list[float] = []

    for regime in policy_order:
        llm_mobility = summarize_records(llm_profile_records, profiles, "mobility_reduction", regime)
        heuristic_mobility = summarize_records(heuristic_profile_records, profiles, "mobility_reduction", regime)
        llm_prevention = summarize_records(llm_profile_records, profiles, "prevention_index", regime)
        heuristic_prevention = summarize_records(heuristic_profile_records, profiles, "prevention_index", regime)
        llm_contact_ratio = summarize_records(llm_profile_records, profiles, "contact_ratio", regime)
        heuristic_contact_ratio = summarize_records(heuristic_profile_records, profiles, "contact_ratio", regime)
        llm_pressure = summarize_records(llm_profile_records, profiles, "transmission_pressure", regime)
        heuristic_pressure = summarize_records(heuristic_profile_records, profiles, "transmission_pressure", regime)

        observed_mobility = mobility_lookup.get(regime)
        mobility_value = float(observed_mobility.observed_mobility_reduction) if observed_mobility else math.nan

        matching_waves = []
        if observed_mobility:
            start = date.fromisoformat(observed_mobility.start_date)
            end = date.fromisoformat(observed_mobility.end_date)
            matching_waves = [wave for wave in coviprev if start <= date.fromisoformat(wave.midpoint_date) <= end]
        behavior_value = float(np.mean([wave.observed_prevention_index for wave in matching_waves])) if matching_waves else math.nan

        aggregated.append(
            {
                "policy_regime": regime,
                "policy_label": regime_label(regime),
                "llm_predicted_mobility_reduction": llm_mobility,
                "heuristic_predicted_mobility_reduction": heuristic_mobility,
                "observed_mobility_reduction": mobility_value,
                "llm_predicted_prevention_index": llm_prevention,
                "heuristic_predicted_prevention_index": heuristic_prevention,
                "observed_coviprev_prevention_index": behavior_value,
                "llm_contact_ratio": llm_contact_ratio,
                "heuristic_contact_ratio": heuristic_contact_ratio,
                "llm_transmission_pressure": llm_pressure,
                "heuristic_transmission_pressure": heuristic_pressure,
                "coviprev_waves": [wave.wave for wave in matching_waves],
            }
        )
        if not math.isnan(mobility_value):
            observed_mobility_series.append(mobility_value)
            llm_mobility_series.append(llm_mobility)
            heuristic_mobility_series.append(heuristic_mobility)
        if not math.isnan(behavior_value):
            observed_prevention_series.append(behavior_value)
            llm_prevention_series.append(llm_prevention)
            heuristic_prevention_series.append(heuristic_prevention)

    restrictive_regimes = {"first_lockdown", "second_wave_restrictions", "curfew_winter_2020_2021", "pass_sanitaire"}
    profile_summary: list[dict[str, Any]] = []
    for profile in profiles:
        llm_rows = [row for row in llm_profile_records if row["profile_key"] == profile.key and row["policy_regime"] in restrictive_regimes]
        heuristic_rows = [row for row in heuristic_profile_records if row["profile_key"] == profile.key and row["policy_regime"] in restrictive_regimes]
        profile_summary.append(
            {
                "profile_key": profile.key,
                "profile_label": profile.display_label,
                "occupation": profile.occupation,
                "population_weight": profile.population_weight,
                "llm_mean_prevention": float(np.mean([row["prevention_index"] for row in llm_rows])),
                "heuristic_mean_prevention": float(np.mean([row["prevention_index"] for row in heuristic_rows])),
                "llm_mean_pressure": float(np.mean([row["transmission_pressure"] for row in llm_rows])),
                "heuristic_mean_pressure": float(np.mean([row["transmission_pressure"] for row in heuristic_rows])),
                "llm_mean_economic_constraint": float(np.mean([row["economic_constraint"] for row in llm_rows])),
                "llm_mean_social_pressure": float(np.mean([row["social_pressure"] for row in llm_rows])),
                "llm_mean_household_pressure": float(np.mean([row["household_pressure"] for row in llm_rows])),
                "llm_minus_heuristic_prevention": float(np.mean([row["prevention_index"] for row in llm_rows]) - np.mean([row["prevention_index"] for row in heuristic_rows])),
                "llm_minus_heuristic_pressure": float(np.mean([row["transmission_pressure"] for row in llm_rows]) - np.mean([row["transmission_pressure"] for row in heuristic_rows])),
            }
        )

    def occupation_gap(records: list[dict[str, Any]], metric_key: str) -> float:
        privileged = [row[metric_key] for row in records if row["occupation"] in {"cadre", "profession_intermediaire"} and row["policy_regime"] in restrictive_regimes]
        constrained = [row[metric_key] for row in records if row["occupation"] in {"ouvrier", "employe", "chomeur", "inactive_au_foyer"} and row["policy_regime"] in restrictive_regimes]
        return float(np.mean(privileged) - np.mean(constrained)) if privileged and constrained else 0.0

    metrics_payload = {
        "n_profiles": len(profiles),
        "n_profile_regime_pairs": len(llm_profile_records),
        "llm_mobility_mae": compute_mae(observed_mobility_series, llm_mobility_series),
        "heuristic_mobility_mae": compute_mae(observed_mobility_series, heuristic_mobility_series),
        "llm_mobility_correlation": pearson_correlation(llm_mobility_series, observed_mobility_series),
        "heuristic_mobility_correlation": pearson_correlation(heuristic_mobility_series, observed_mobility_series),
        "llm_prevention_mae": compute_mae(observed_prevention_series, llm_prevention_series),
        "heuristic_prevention_mae": compute_mae(observed_prevention_series, heuristic_prevention_series),
        "llm_prevention_directional_agreement": float(metrics.trend_direction_agreement(np.asarray(llm_prevention_series), np.asarray(observed_prevention_series))),
        "heuristic_prevention_directional_agreement": float(metrics.trend_direction_agreement(np.asarray(heuristic_prevention_series), np.asarray(observed_prevention_series))),
        "llm_minus_heuristic_mobility_mae": compute_mae(observed_mobility_series, llm_mobility_series) - compute_mae(observed_mobility_series, heuristic_mobility_series),
        "llm_minus_heuristic_prevention_mae": compute_mae(observed_prevention_series, llm_prevention_series) - compute_mae(observed_prevention_series, heuristic_prevention_series),
        "llm_trust_gap_privileged_minus_constrained": occupation_gap(llm_profile_records, "trust_in_authorities"),
        "llm_pressure_gap_privileged_minus_constrained": occupation_gap(llm_profile_records, "transmission_pressure"),
        "heuristic_pressure_gap_privileged_minus_constrained": occupation_gap(heuristic_profile_records, "transmission_pressure"),
    }

    payload = {
        "experiment_name": str(config.get("experiment_name", "exp007_shs_llm")),
        "config_path": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "reference": reference_payload["metadata"],
        "llm_provider": {
            "provider": str(model_cfg.get("provider_label", "OpenRouter")),
            "backend": str(model_cfg.get("backend", "openai_compatible")),
            "api_base": str(model_cfg.get("base_url", "https://openrouter.ai/api/v1")),
            "api_format": (
                "structured JSON output"
                if str(model_cfg.get("backend", "openai_compatible")) == "claude_cli"
                else "OpenAI-compatible chat.completions"
            ),
            "primary_model": str(model_cfg.get("name", "openai/gpt-5.4-mini")),
            "fallback_models": list(model_cfg.get("fallback_models", ["openai/gpt-5-mini"])),
            "api_key_env": str(model_cfg.get("api_key_env", "OPENROUTER_API_KEY")),
            "cli_command": str(model_cfg.get("cli_command", "claude")),
            "cli_tools": model_cfg.get("cli_tools", ""),
            "cli_max_budget_usd": model_cfg.get("cli_max_budget_usd"),
            "auto_wait_on_rate_limit": bool(model_cfg.get("auto_wait_on_rate_limit", True)),
            "rate_limit_reset_buffer_seconds": int(model_cfg.get("rate_limit_reset_buffer_seconds", 20)),
            "rate_limit_poll_seconds": int(model_cfg.get("rate_limit_poll_seconds", 30)),
            "rate_limit_max_wait_seconds": int(model_cfg.get("rate_limit_max_wait_seconds", 21600)),
            "abort_on_fallback": bool(model_cfg.get("abort_on_fallback", False)),
            "abort_on_auth_error": bool(model_cfg.get("abort_on_auth_error", True)),
        },
        "generation_modes": sorted(generation_modes),
        "data_sources": {
            "google_mobility": "Official Google Community Mobility Reports regional archive for France national rows.",
            "coviprev": "Public CoviPrev extract curated in data/interim/coviprev_behavior_france.csv.",
            "profiles": "Synthetic French socio-demographic profiles anchored to INSEE, Dares, and CoviPrev proxies.",
            "behavioral_layer": "Calibrated behavioral contact layer inherited from exp005 to connect SHS scores to diffusion-relevant contact ratios.",
        },
        "prompt_protocol": agent.protocol_metadata(),
        "mediation_weights": mediation_weights,
        "aggregated_predictions": aggregated,
        "llm_profile_records": llm_profile_records,
        "heuristic_profile_records": heuristic_profile_records,
        "profile_summary": profile_summary,
        "metrics": metrics_payload,
        "assessment": {
            "honest_summary": (
                "This experiment makes the LLM block more central by using it as a social-behavioral mediator rather than only a direct score generator. "
                "The LLM outputs latent SHS variables, which are then projected through the calibrated behavioral layer into diffusion-relevant contact and transmission modifiers. "
                "Claims should still remain bounded: this is a structured scenario instrument, not identification of true individual behavior."
            ),
            "novelty_claim": (
                "The novelty lies in treating the LLM as a structured SHS mediation layer between socio-demographic profiles, public policy regimes, and epidemic diffusion controls, with explicit baselines and fallback auditing."
            ),
        },
    }
    return payload


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_summary(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    return (
        "metric                             llm        heuristic\n"
        f"mobility_mae                        {m['llm_mobility_mae']:.4f}     {m['heuristic_mobility_mae']:.4f}\n"
        f"mobility_correlation                {m['llm_mobility_correlation']:.3f}      {m['heuristic_mobility_correlation']:.3f}\n"
        f"prevention_mae                      {m['llm_prevention_mae']:.4f}     {m['heuristic_prevention_mae']:.4f}\n"
        f"prevention_directional_agreement    {m['llm_prevention_directional_agreement']:.3f}      {m['heuristic_prevention_directional_agreement']:.3f}"
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
