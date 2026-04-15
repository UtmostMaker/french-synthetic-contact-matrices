from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "docs" / "literature" / "source_index.csv",
    ROOT / "docs" / "datasets" / "dataset_registry.md",
    ROOT / "experiments" / "registry.csv",
    ROOT / "status" / "project_status.json",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))
print("Smoke test passed")
