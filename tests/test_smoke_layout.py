from pathlib import Path


def test_project_layout():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "literature" / "source_index.csv").exists()
    assert (root / "experiments" / "registry.csv").exists()
    assert (root / "status" / "project_status.json").exists()
