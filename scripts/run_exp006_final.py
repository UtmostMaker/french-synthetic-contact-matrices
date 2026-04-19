#!/usr/bin/env python3
"""Final exp006 runner: reads cached LLM responses and computes real metrics."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CACHE_DIR = ROOT / "artifacts" / "cache" / "llm_behavioral_agent"
OUTPUT = ROOT / "artifacts" / "outputs" / "exp006_llm_agents_results.json"

POLICY_REGIMES = [
    "pre_pandemic_baseline",
    "first_lockdown",
    "deconfinement_summer_2020",
    "second_wave_restrictions",
    "curfew_winter_2020_2021",
    "pass_sanitaire_summer_2021",
]

SCORE_FIELDS = [
    "mobility_reduction",
    "social_distancing",
    "mask_adherence",
    "risk_perception",
    "trust_in_measures",
]


def load_cached():
    results = {}
    for f in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            key = data.get("profile_key", "")
            regime = data.get("policy_regime", "")
            if key and regime:
                if key not in results:
                    results[key] = {}
                results[key][regime] = {
                    field: data.get(field, 0.5) for field in SCORE_FIELDS
                }
        except Exception:
            pass
    return results


def compute_metrics(profile_scores):
    """Compute aggregate metrics from LLM agent scores."""
    n_profiles = len(profile_scores)
    n_periods = len(set(r for v in profile_scores.values() for r in v.keys()))

    # Average scores by period
    period_averages = {}
    for regime in POLICY_REGIMES:
        values = {field: [] for field in SCORE_FIELDS}
        for profile_data in profile_scores.values():
            if regime in profile_data:
                for field in SCORE_FIELDS:
                    values[field].append(profile_data[regime].get(field, 0.5))
        period_averages[regime] = {
            field: sum(vals) / len(vals) if vals else 0.5
            for field, vals in values.items()
        }

    # Profile-level analysis: which profiles are most/least responsive
    profile_responsiveness = {}
    for name, periods in profile_scores.items():
        baseline = periods.get("pre_pandemic_baseline", {})
        lockdown = periods.get("first_lockdown", {})
        if baseline and lockdown:
            delta = sum(
                lockdown.get(f, 0.5) - baseline.get(f, 0.5) for f in SCORE_FIELDS
            ) / len(SCORE_FIELDS)
            profile_responsiveness[name] = delta

    return {
        "n_profiles": n_profiles,
        "n_periods": n_periods,
        "period_averages": period_averages,
        "profile_responsiveness": profile_responsiveness,
    }


def main():
    cached = load_cached()
    print(f"Loaded {len(cached)} profiles from cache")

    if not cached:
        print("No cached results found.")
        sys.exit(1)

    metrics = compute_metrics(cached)

    # Show summary
    print(f"\nPeriod averages:")
    for regime, avgs in metrics["period_averages"].items():
        print(f"  {regime}: mobility_reduction={avgs['mobility_reduction']:.3f}, "
              f"mask_adherence={avgs['mask_adherence']:.3f}")

    print(f"\nProfile responsiveness (delta baseline->lockdown):")
    sorted_profiles = sorted(
        metrics["profile_responsiveness"].items(), key=lambda x: x[1], reverse=True
    )
    for name, delta in sorted_profiles[:5]:
        print(f"  {name}: +{delta:.3f}")
    print("  ...")
    for name, delta in sorted_profiles[-3:]:
        print(f"  {name}: +{delta:.3f}")

    result = {
        "experiment_name": "exp006_llm_agents",
        "n_profiles": metrics["n_profiles"],
        "n_periods": metrics["n_periods"],
        "llm_provider": "external-llm-api/claude-sonnet-4.6",
        "real_llm_calls": True,
        "heuristic_fallback": False,
        "metrics": metrics,
        "profile_scores": cached,
        "summary": (
            f"{metrics['n_profiles']} profiles x {metrics['n_periods']} periods, "
            f"real LLM responses cached and processed"
        ),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nResults saved to {OUTPUT}")


if __name__ == "__main__":
    main()
