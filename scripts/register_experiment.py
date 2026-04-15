from __future__ import annotations
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
