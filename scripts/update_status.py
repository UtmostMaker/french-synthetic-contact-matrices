from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
status_path = ROOT / "status" / "project_status.json"
status = json.loads(status_path.read_text())
status["last_updated"] = datetime.now(timezone.utc).isoformat()
status_path.write_text(json.dumps(status, indent=2) + "\n")
print(f"Updated {status_path}")
