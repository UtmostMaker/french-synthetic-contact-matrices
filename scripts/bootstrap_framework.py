from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "README.md": '''# French Synthetic Contact Matrices

A long-running, reproducible research project on synthetic contact matrix generation from French demographic and population data for epidemiological modeling.

## Current phase
Phase 0, research framework bootstrap.

## Core principles
- Scientific rigor over hype
- Reproducibility over convenience
- Modest, defensible contributions over cosmetic novelty
- Local-first compute, with escalation only when justified
- Parallel paper writing and experimentation, both grounded in evidence

## Project goals
1. Map the literature on contact matrices, synthetic populations, and French demographic data.
2. Identify a realistic scientific gap.
3. Select one main paper idea and one backup idea.
4. Build and evaluate a reproducible pipeline.
5. Produce a GitHub-ready and arXiv-ready package in English.

## Repository map
- `docs/` research planning, logs, literature, risks, and methodology notes
- `data/` dataset registry and data access instructions
- `experiments/` experiment registry, configs, and run outputs metadata
- `artifacts/` figures, tables, logs, intermediate publication assets
- `src/` implementation code
- `tests/` unit and smoke tests
- `scripts/` lightweight operational utilities
- `manuscript/` paper drafts and submission assets
- `status/` machine-readable project status and checkpoints

## Reproducibility stance
This project aims to make every major result traceable to:
- a dataset entry,
- a code revision,
- a configuration file,
- a registered experiment,
- a versioned artifact,
- and a written interpretation.
''',
    ".gitignore": '''# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/

# Data and artifacts
artifacts/generated/
artifacts/logs/
artifacts/checkpoints/
data/raw/
data/interim/
data/processed/

# OS/editor
.DS_Store
.vscode/
.idea/

# Local env
.env
''',
    "pyproject.toml": '''[project]
name = "french-synthetic-contact-matrices"
version = "0.1.0"
description = "Reproducible epidemiology research on synthetic contact matrix generation from French population data"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "pandas>=2.2",
    "scipy>=1.12",
    "matplotlib>=3.8",
    "pyyaml>=6.0",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
''',
    "status/project_status.json": '''{
  "project_name": "French Synthetic Contact Matrices",
  "phase": "Phase 0 - Bootstrap",
  "current_objective": "Create the durable research framework and start literature mapping.",
  "main_idea": null,
  "backup_idea": null,
  "last_updated": "2026-04-15T09:42:00+02:00",
  "next_milestone": "Initial literature map and candidate idea backlog",
  "blocking_items": [],
  "active_risks": [
    "Scientific novelty may be incremental rather than fundamental.",
    "French data availability and licensing constraints may limit granularity.",
    "Benchmark comparability may be difficult across heterogeneous contact-matrix papers."
  ]
}
''',
    "PROJECT_STATUS.md": '''# Project Status

## Snapshot
- Phase: Phase 0, Bootstrap
- Current objective: Create the durable research framework and start literature mapping.
- Main idea: not selected yet
- Backup idea: not selected yet
- Next milestone: initial literature map and candidate idea backlog

## Immediate priorities
1. Build the durable project framework.
2. Map the literature and datasets.
3. Identify the most defensible research gap.
4. Generate and score candidate paper ideas.

## Success criteria for the next milestone
- Annotated bibliography started
- Comparative literature matrix created
- Dataset registry started
- Baseline registry started
- Decision, hypothesis, risk, and failure logs initialized
''',
    "docs/operations/task_system.md": '''# Task System

## Status labels
- backlog
- active
- blocked
- done
- dropped

## Priority labels
- P0 critical
- P1 high
- P2 normal
- P3 low

## Operating rule
Every meaningful task should have:
- a clear owner,
- a concrete output,
- a dependency note if relevant,
- and a definition of done.

## Active task board
| ID | Status | Priority | Task | Output | Dependencies |
|---|---|---|---|---|---|
| T0001 | active | P0 | Bootstrap repository structure | Initial framework files | None |
| T0002 | active | P0 | Start broad literature mapping | Source index + annotated notes | T0001 |
| T0003 | backlog | P1 | Build candidate idea backlog | Scored idea list | T0002 |
| T0004 | backlog | P1 | Select main and backup idea | Decision entry | T0003 |
''',
    "docs/operations/decision_log.md": '''# Decision Log

## D0001
- Date: 2026-04-15
- Status: accepted
- Decision: Start with a durable local-first research framework before selecting a final paper idea.
- Rationale: The project is intended to run over days or weeks and must survive interruptions without losing context, reproducibility, or experimental traceability.
- Consequences:
  - More upfront structure.
  - Lower risk of chaos during experimentation and drafting.
  - Easier final packaging for GitHub and arXiv.
''',
    "docs/operations/hypothesis_log.md": '''# Hypothesis Log

## H0001
- Date: 2026-04-15
- Status: open
- Hypothesis: French demographic, household, regional, and mobility-related public data can support a synthetic contact matrix generation pipeline that is useful for epidemiological modeling even without proprietary contact survey data.
- Why it matters: If true, the project could offer a reproducible, accessible alternative for scenario analysis and public-health modeling.
- Key risks: weak external validity, lack of suitable benchmarks, and overfitting to demographic proxies.
- Planned evidence:
  - literature review,
  - dataset audit,
  - baseline comparison,
  - robustness checks.
''',
    "docs/operations/risk_register.md": '''# Risk Register

| ID | Risk | Severity | Likelihood | Mitigation | Status |
|---|---|---:|---:|---|---|
| R0001 | No strong novelty after literature review | High | Medium | Prefer modest but defensible contribution; keep a backup idea | active |
| R0002 | French data too coarse or fragmented | High | Medium | Design methods compatible with partial or heterogeneous inputs | active |
| R0003 | Evaluation benchmarks are weak or inconsistent | High | Medium | Use multiple validation axes and explicit threats to validity | active |
| R0004 | Heavy methods exceed local compute budget | Medium | Medium | Local-first profiling, frugal baselines, checkpointing | active |
| R0005 | Reproducibility degrades as scope grows | High | Low | Mandatory experiment registry and artifact conventions | active |
''',
    "docs/operations/failure_log.md": '''# Failure Log

Record failed experiments, dead ends, broken assumptions, and negative results.

## Entry template
- Date:
- ID:
- Short name:
- What failed:
- Likely cause:
- Evidence:
- What we learned:
- Follow-up action:
''',
    "docs/operations/reproducibility_checklist.md": '''# Reproducibility Checklist

## Before a result is considered paper-ready
- [ ] Data source recorded in dataset registry
- [ ] Data access path documented
- [ ] Preprocessing steps documented
- [ ] Configuration file saved
- [ ] Random seed recorded
- [ ] Runtime environment noted
- [ ] Experiment registered
- [ ] Outputs versioned
- [ ] Figures reproducible from scripts
- [ ] Interpretation written in plain scientific English
- [ ] Limitations and threats to validity documented
''',
    "docs/literature/README.md": '''# Literature Mapping

This directory stores the evolving literature review.

## Files
- `source_index.csv`: bibliographic inventory and triage status
- `annotated_bibliography.md`: concise paper notes
- `taxonomy.md`: structured map of method families
- `gap_analysis.md`: synthesis of opportunities and weaknesses
- `comparative_matrix.csv`: method-level comparison table
''',
    "docs/literature/annotated_bibliography.md": '''# Annotated Bibliography

This file will store concise notes for each relevant paper or resource.

## Entry template
### Citation key
- Research question:
- Data used:
- Method:
- Assumptions:
- Evaluation:
- Strengths:
- Weaknesses:
- Compute burden:
- Reproducibility:
- Extension opportunities:
''',
    "docs/literature/taxonomy.md": '''# Taxonomy of Approaches

## Candidate buckets
- Survey-derived empirical contact matrices
- Demography-scaled contact matrix transfer methods
- Synthetic population and agent-based contact generation
- Mobility-informed contact structure models
- Matrix inference, completion, or factorization approaches
- Probabilistic or uncertainty-aware contact modeling
- Hybrid mechanistic-statistical approaches
''',
    "docs/literature/gap_analysis.md": '''# Gap Analysis

Pending literature review.

## Initial candidate gaps to test, not claim yet
1. French-specific synthetic contact matrix generation may be underexplored relative to broader European or global transfer methods.
2. Uncertainty-aware generation may be less common than point-estimate matrix production.
3. Region-aware or territorial heterogeneity for France may be inadequately benchmarked in open, reproducible pipelines.
4. Public-data-only pipelines may still be scientifically useful if framed modestly and evaluated honestly.
''',
    "docs/literature/source_index.csv": "id,title,year,venue_or_source,url,domain,topic_bucket,status,priority,notes\n",
    "docs/literature/comparative_matrix.csv": "id,method_family,geography,data_type,granularity,uncertainty_support,benchmark_type,compute_burden,reproducibility_level,main_limitations\n",
    "docs/datasets/dataset_registry.md": '''# Dataset Registry

## Entry template
- Dataset ID:
- Name:
- Source:
- URL:
- Geography:
- Temporal coverage:
- Variables:
- Access method:
- License:
- Expected role in project:
- Risks or caveats:
''',
    "docs/baselines/baseline_registry.md": '''# Baseline Registry

## Candidate baseline families
1. Simple demographic scaling baseline
2. Household-structure-aware rule-based baseline
3. POLYMOD-style transfer or adaptation baseline, if legally and methodologically appropriate
4. Mobility-augmented baseline
5. Lightweight probabilistic baseline with uncertainty intervals
''',
    "docs/ideas/candidate_ideas.md": '''# Candidate Paper Ideas

This file will store at least 20 candidate ideas, each with a structured scorecard.

## Scoring dimensions
- Novelty
- Scientific value
- Feasibility
- Reproducibility
- Computational efficiency
- Robustness potential
- Community usefulness
''',
    "docs/reports/report_template.md": '''# Progress Report Template

[REPORT HH:MM]
- Phase:
- Current objective:
- Done:
- Evidence produced:
- Risks:
- Next actions:
- Need from user:
- ETA next milestone:
''',
    "experiments/registry.csv": "experiment_id,date,status,objective,config_path,seed,runtime_env,outputs,notes\n",
    "experiments/configs/README.md": '''# Experiment Configs

Store versioned experiment configuration files here.
''',
    "manuscript/README.md": '''# Manuscript Workspace

All scientific writing in this directory must remain in English.
''',
    "manuscript/outline.md": '''# Working Manuscript Outline

## Title
Pending idea selection.

## Abstract
Pending.

## 1. Introduction
Pending.

## 2. Related Work
Pending.

## 3. Problem Formulation
Pending.

## 4. Data and Preprocessing
Pending.

## 5. Methodology
Pending.

## 6. Experimental Setup
Pending.

## 7. Results
Pending.

## 8. Discussion and Limitations
Pending.

## 9. Conclusion
Pending.

## Appendix
Pending.
''',
    "scripts/update_status.py": '''from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
status_path = ROOT / "status" / "project_status.json"
status = json.loads(status_path.read_text())
status["last_updated"] = datetime.now(timezone.utc).isoformat()
status_path.write_text(json.dumps(status, indent=2) + "\\n")
print(f"Updated {status_path}")
''',
    "scripts/register_experiment.py": '''from __future__ import annotations
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
registry = ROOT / "experiments" / "registry.csv"

if len(sys.argv) < 3:
    raise SystemExit("Usage: python scripts/register_experiment.py <experiment_id> <objective>")

experiment_id = sys.argv[1]
objective = " ".join(sys.argv[2:])
row = {
    "experiment_id": experiment_id,
    "date": datetime.now().isoformat(timespec="seconds"),
    "status": "planned",
    "objective": objective,
    "config_path": "",
    "seed": "",
    "runtime_env": "local",
    "outputs": "",
    "notes": "",
}
with registry.open("a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=row.keys())
    writer.writerow(row)
print(f"Registered {experiment_id}")
''',
    "scripts/smoke_test.py": '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "docs" / "literature" / "source_index.csv",
    ROOT / "docs" / "datasets" / "dataset_registry.md",
    ROOT / "experiments" / "registry.csv",
    ROOT / "status" / "project_status.json",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\\n" + "\\n".join(missing))
print("Smoke test passed")
''',
    "src/contact_matrix_fr/__init__.py": '''"""Core package for French synthetic contact matrix research."""
''',
    "tests/test_smoke_layout.py": '''from pathlib import Path


def test_project_layout():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "literature" / "source_index.csv").exists()
    assert (root / "experiments" / "registry.csv").exists()
    assert (root / "status" / "project_status.json").exists()
''',
    "artifacts/README.md": '''# Artifacts

This directory stores generated figures, tables, checkpoints, and logs.
''',
    "data/README.md": '''# Data Layout

- `raw/`: original downloaded files, not tracked by default
- `interim/`: cleaned intermediate files
- `processed/`: analysis-ready data products
- `external/`: metadata or manually curated references

Use the dataset registry for every source before large-scale use.
'''
}

DIRS = [
    "artifacts/generated",
    "artifacts/logs",
    "artifacts/checkpoints",
    "data/raw",
    "data/interim",
    "data/processed",
    "data/external",
    "docs/methods",
    "docs/benchmarks",
    "docs/templates",
    "status/checkpoints",
]


def main() -> None:
    for rel in DIRS:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)
    for rel, content in FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    print(f"Bootstrapped {ROOT}")
    print(f"Created {len(FILES)} files")


if __name__ == "__main__":
    main()
