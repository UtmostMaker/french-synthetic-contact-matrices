"""Run exp009: mobility-calibrated prompt variant of exp007."""

from __future__ import annotations

import run_exp007_shs_llm as base


base.CONFIG_PATH = base.REPO_ROOT / "experiments" / "configs" / "exp009_shs_llm_mobility.yaml"
base.OUTPUT_PATH = base.REPO_ROOT / "artifacts" / "outputs" / "exp009_shs_llm_mobility_results.json"


if __name__ == "__main__":
    raise SystemExit(base.main())
