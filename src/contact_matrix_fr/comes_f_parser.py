from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import numpy as np


Array = np.ndarray
_SPREADSHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_DEFAULT_AGE_BOUNDS = tuple(range(0, 85, 5)) + (float("inf"),)


@dataclass(frozen=True, slots=True)
class ContactRecord:
    participant_age: float
    day_index: int
    contact_age: float


@dataclass(frozen=True, slots=True)
class DiaryRow:
    participant_age: float
    observation_days: int
    contacts: tuple[ContactRecord, ...]


def load_comes_f_workbook(
    path: str | Path,
    *,
    symmetrize: bool = True,
    age_bounds: Iterable[float] | None = None,
) -> dict[str, Any]:
    """Parse the public COMES-F raw workbook into an analysis-ready matrix.

    The public Figshare workbook is a single-sheet XLSX export with 2033 diary
    rows and up to 40 listed contacts per diary day. The parser rebuilds a daily
    age-by-age contact matrix directly from the workbook XML, avoiding optional
    Excel dependencies such as openpyxl.

    Important limitation
    --------------------
    The workbook contains *listed* diary contacts, but only coarse supplementary
    metadata for participants with many professional contacts. Those additional
    professional contacts are therefore not reconstructed here. The resulting
    matrix is a transparent re-aggregation of the explicitly listed contacts, not
    a full reproduction of the weighted analysis pipeline from Béraud et al.
    """

    workbook_path = Path(path)
    rows = _parse_workbook_rows(workbook_path)
    bounds = _normalize_age_bounds(age_bounds)
    age_labels = _age_labels_from_bounds(bounds)
    result = _aggregate_rows(rows, age_bounds=bounds, symmetrize=symmetrize)
    metadata = {
        "source": str(workbook_path),
        "survey": "COMES-F",
        "format": "xlsx-raw",
        "doi": "10.6084/m9.figshare.1466917.v2",
        "figshare_url": "https://figshare.com/articles/dataset/Data_file_for_Comes_F/1466917",
        "license": "CC BY 4.0",
        "participants": int(result["participants"]),
        "observation_days": int(result["observation_days"]),
        "listed_contacts": int(result["listed_contacts"]),
        "matrix_variant": "symmetrized" if symmetrize else "raw_daily_mean",
        "limitations": [
            "Supplementary professional contacts (>20/day) are not fully reconstructed from the public workbook.",
            "No survey re-weighting is applied in the current parser.",
            "Symmetrization is arithmetic and does not reproduce the original population-weighted reciprocity correction.",
        ],
        "participant_age_counts": result["participant_age_counts"],
        "row_observation_days": result["row_observation_days"],
    }
    return {
        "matrix": result["matrix"],
        "raw_matrix": result["raw_matrix"],
        "age_labels": age_labels,
        "metadata": metadata,
    }


def export_comes_f_summary(payload: dict[str, Any], output_path: str | Path) -> None:
    """Persist a JSON summary without duplicating the full matrix twice."""

    serializable = {
        "age_labels": list(payload["age_labels"]),
        "matrix": np.asarray(payload["matrix"], dtype=float).tolist(),
        "metadata": payload["metadata"],
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")


def _aggregate_rows(
    rows: list[DiaryRow],
    *,
    age_bounds: tuple[float, ...],
    symmetrize: bool,
) -> dict[str, Any]:
    n_bins = len(age_bounds) - 1
    contact_totals = np.zeros((n_bins, n_bins), dtype=float)
    row_observation_days = np.zeros(n_bins, dtype=float)
    participant_age_counts = np.zeros(n_bins, dtype=int)
    listed_contacts = 0

    for row in rows:
        participant_bin = _digitize_age(row.participant_age, age_bounds)
        participant_age_counts[participant_bin] += 1
        row_observation_days[participant_bin] += row.observation_days
        for contact in row.contacts:
            contact_bin = _digitize_age(contact.contact_age, age_bounds)
            contact_totals[participant_bin, contact_bin] += 1.0
            listed_contacts += 1

    raw_matrix = np.zeros_like(contact_totals)
    nonzero = row_observation_days > 0
    raw_matrix[nonzero] = contact_totals[nonzero] / row_observation_days[nonzero, None]
    matrix = 0.5 * (raw_matrix + raw_matrix.T) if symmetrize else raw_matrix.copy()

    return {
        "matrix": matrix,
        "raw_matrix": raw_matrix,
        "participants": len(rows),
        "observation_days": int(sum(row.observation_days for row in rows)),
        "listed_contacts": listed_contacts,
        "participant_age_counts": participant_age_counts.astype(int).tolist(),
        "row_observation_days": row_observation_days.astype(int).tolist(),
    }


def _parse_workbook_rows(path: Path) -> list[DiaryRow]:
    shared_strings: list[str] = []
    rows: list[DiaryRow] = []

    with ZipFile(path) as archive:
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in shared_root:
                shared_strings.append(
                    "".join(
                        node.text or ""
                        for node in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )

        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        sheet_rows = list(sheet_root.find("a:sheetData", _SPREADSHEET_NS) or [])

        for row in sheet_rows[3:]:
            sparse = _extract_sparse_row(row, shared_strings)
            if not sparse:
                continue

            participant_age = _to_float(sparse.get("E"))
            if participant_age is None:
                continue

            contacts: list[ContactRecord] = []
            observation_days = 0
            for day_index, base_col in enumerate(("BH", "XA"), start=1):
                day_contacts = _extract_day_contacts(sparse, participant_age=participant_age, day_index=day_index, base_col=base_col)
                if day_contacts:
                    contacts.extend(day_contacts)
                    observation_days += 1
                elif sparse.get("BG" if day_index == 1 else "WZ") not in (None, ""):
                    observation_days += 1

            if observation_days == 0:
                continue
            rows.append(DiaryRow(participant_age=participant_age, observation_days=observation_days, contacts=tuple(contacts)))

    if not rows:
        raise ValueError(f"No diary rows were parsed from {path}")
    return rows


def _extract_day_contacts(
    sparse_row: dict[str, str],
    *,
    participant_age: float,
    day_index: int,
    base_col: str,
) -> list[ContactRecord]:
    base_index = _column_to_int(base_col)
    contacts: list[ContactRecord] = []

    for block in range(40):
        start = base_index + 14 * block
        contact_age = _resolve_contact_age(
            sparse_row.get(_int_to_column(start)),
            sparse_row.get(_int_to_column(start + 1)),
            sparse_row.get(_int_to_column(start + 2)),
        )
        sex_value = sparse_row.get(_int_to_column(start + 3))
        if contact_age is None and sex_value in (None, ""):
            continue
        if contact_age is None:
            continue
        contacts.append(ContactRecord(participant_age=participant_age, day_index=day_index, contact_age=contact_age))

    return contacts


def _resolve_contact_age(min_value: str | None, max_value: str | None, mean_value: str | None) -> float | None:
    age_mean = _to_float(mean_value)
    age_min = _to_float(min_value)
    age_max = _to_float(max_value)

    if age_mean is not None:
        return age_mean
    if age_min is not None and age_max is not None:
        return 0.5 * (age_min + age_max)
    if age_min is not None:
        return age_min
    if age_max is not None:
        return age_max
    return None


def _extract_sparse_row(row: ET.Element, shared_strings: list[str]) -> dict[str, str]:
    sparse: dict[str, str] = {}
    for cell in row:
        ref = cell.attrib.get("r", "")
        col = "".join(ch for ch in ref if ch.isalpha())
        if not col:
            continue

        inline = cell.find("a:is", _SPREADSHEET_NS)
        if inline is not None:
            value = "".join(
                node.text or ""
                for node in inline.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
            )
            sparse[col] = value
            continue

        raw = cell.find("a:v", _SPREADSHEET_NS)
        if raw is None:
            continue

        text = raw.text or ""
        if cell.attrib.get("t") == "s" and text.isdigit():
            sparse[col] = shared_strings[int(text)]
        else:
            sparse[col] = text
    return sparse


def _normalize_age_bounds(age_bounds: Iterable[float] | None) -> tuple[float, ...]:
    bounds = tuple(float(value) for value in (age_bounds or _DEFAULT_AGE_BOUNDS))
    if len(bounds) < 2:
        raise ValueError("age_bounds must contain at least two edges")
    if any(right <= left for left, right in zip(bounds, bounds[1:])):
        raise ValueError("age_bounds must be strictly increasing")
    if not np.isinf(bounds[-1]):
        raise ValueError("the last age bound must be infinity")
    return bounds


def _age_labels_from_bounds(bounds: tuple[float, ...]) -> list[str]:
    labels: list[str] = []
    for left, right in zip(bounds[:-1], bounds[1:]):
        if np.isinf(right):
            labels.append(f"{int(left)}+")
        else:
            labels.append(f"{int(left)}-{int(right) - 1}")
    return labels


def _digitize_age(age: float, bounds: tuple[float, ...]) -> int:
    clipped = max(float(age), bounds[0])
    idx = int(np.searchsorted(np.asarray(bounds[1:], dtype=float), clipped, side="right"))
    return min(max(idx, 0), len(bounds) - 2)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _column_to_int(column: str) -> int:
    total = 0
    for char in column.upper():
        total = total * 26 + (ord(char) - 64)
    return total


def _int_to_column(index: int) -> str:
    letters = ""
    value = index
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
