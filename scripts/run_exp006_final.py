#!/usr/bin/env python3
"""Validate and summarize the archived exp006 results artifact.

This helper avoids schema drift with older experimental drafts. The current
source of truth is `artifacts/outputs/exp006_llm_agents_results.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "outputs" / "exp006_llm_agents_results.json"


def main() -> int:
    if not OUTPUT.exists():
        print("Missing archived exp006 artifact. Run `python3 scripts/run_exp006.py` first.", file=sys.stderr)
        return 1

    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    print(f"experiment_name={data.get('experiment_name', 'unknown')}")
    print(f"generation_modes={','.join(data.get('generation_modes', []))}")
    print(f"n_profiles={metrics.get('n_profiles', 'unknown')}")
    print(f"n_profile_regime_pairs={metrics.get('n_profile_regime_pairs', 'unknown')}")
    print(f"mobility_correlation={metrics.get('mobility_correlation', float('nan')):.3f}")
    print(f"mobility_mae={metrics.get('mobility_mae', float('nan')):.3f}")
    print(f"coviprev_behavior_mae={metrics.get('coviprev_behavior_mae', float('nan')):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
