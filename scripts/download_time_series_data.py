"""Download and curate French COVID time-series proxies for exp003.

This script deliberately mixes direct downloads and carefully documented curated
series. CoviPrev is downloaded from data.gouv.fr and parsed from the public XLSX.
SocialCov matrices are downloaded from Zenodo; period dates are represented by
policy-aligned anchors because the matrix repository exposes ordered matrices but
not explicit survey window labels in machine-readable form.
"""

from __future__ import annotations

import csv
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "data" / "raw"
INTERIM_ROOT = REPO_ROOT / "data" / "interim"

COVIPREV_URL = (
    "https://static.data.gouv.fr/resources/"
    "donnees-denquete-relatives-a-levolution-des-comportements-et-de-la-sante-mentale-"
    "pendant-lepidemie-de-covid-19-coviprev/20211029-092731/coviprev-geodes-gb-vac.xlsx"
)
COVIPREV_RAW_PATH = RAW_ROOT / "coviprev" / "coviprev-gestes-barrieres-vague28.xlsx"

SOCIALCOV_BASE_URL = "https://zenodo.org/api/records/13834596/files/{name}/content"
SOCIALCOV_FILES = [f"Mat{idx}_regular.csv" for idx in range(1, 7)]
SOCIALCOV_RAW_DIR = RAW_ROOT / "socialcov"

PREPANDEMIC_CONTACT_REFERENCE = 12.0
XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def download_file(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    urllib.request.urlretrieve(url, path)


def parse_workbook_sheet(path: Path, sheet_name: str) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        target = None
        for sheet in workbook.find("a:sheets", XML_NS):
            if sheet.attrib.get("name") == sheet_name:
                target = relmap[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
                break
        if target is None:
            raise ValueError(f"Sheet '{sheet_name}' not found in {path}")

        root = ET.fromstring(archive.read(f"xl/{target}"))
        rows: list[list[str]] = []
        for row in root.find("a:sheetData", XML_NS):
            cells: dict[int, str] = {}
            for cell in row:
                ref = cell.attrib.get("r", "A1")
                col_idx = _excel_column_to_index(re.match(r"([A-Z]+)", ref).group(1))
                value = _cell_value(cell, shared_strings)
                cells[col_idx] = value
            if not cells:
                continue
            width = max(cells) + 1
            rows.append([cells.get(idx, "") for idx in range(width)])
        return rows


def build_coviprev_csv(raw_path: Path, output_path: Path) -> None:
    rows = parse_workbook_sheet(raw_path, sheet_name="france")
    header = rows[0]
    wave_rows = rows[1:]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "wave",
                "start_date",
                "end_date",
                "midpoint_date",
                "policy_regime",
                "mask_public_pct",
                "handwashing_pct",
                "avoid_gatherings_pct",
                "greeting_avoidance_pct",
                "ventilation_pct",
                "adult_vaccine_intent_pct",
                "adult_vaccinated_pct",
                "observed_prevention_index",
                "source_url",
                "source_note",
            ],
        )
        writer.writeheader()
        for row in wave_rows:
            if len(row) < 2 or not row[1]:
                continue
            wave_label = row[1].strip()
            start_date, end_date = _parse_coviprev_dates(wave_label)
            midpoint = _midpoint_date(start_date, end_date)
            data = dict(zip(header, row))
            preventive_values = [
                _to_float(data.get("Port du masque")),
                _to_float(data.get("Lavage des mains")),
                _to_float(data.get("Eviter les regrupements") or data.get("Eviter les regroupements")),
                _to_float(data.get("Saluer sans serrer la main")),
            ]
            ventilation = _to_optional_float(data.get("Aération du logement"))
            if ventilation is not None:
                preventive_values.append(ventilation)
            observed_prevention_index = float(np.mean([value / 100.0 for value in preventive_values]))
            writer.writerow(
                {
                    "wave": wave_label,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "midpoint_date": midpoint.isoformat(),
                    "policy_regime": policy_regime_for_date(midpoint),
                    "mask_public_pct": _to_float(data.get("Port du masque")),
                    "handwashing_pct": _to_float(data.get("Lavage des mains")),
                    "avoid_gatherings_pct": _to_float(data.get("Eviter les regrupements") or data.get("Eviter les regroupements")),
                    "greeting_avoidance_pct": _to_float(data.get("Saluer sans serrer la main")),
                    "ventilation_pct": "" if ventilation is None else ventilation,
                    "adult_vaccine_intent_pct": "" if _to_optional_float(data.get("Adhésion vaccinale - adultes ")) is None else _to_optional_float(data.get("Adhésion vaccinale - adultes ")),
                    "adult_vaccinated_pct": "" if _to_optional_float(data.get("Vaccinés - adultes")) is None else _to_optional_float(data.get("Vaccinés - adultes")),
                    "observed_prevention_index": observed_prevention_index,
                    "source_url": COVIPREV_URL,
                    "source_note": "National France sheet from the public CoviPrev workbook (waves 17-28).",
                }
            )


def build_socialcov_csv(raw_dir: Path, output_path: Path) -> None:
    anchors = [
        ("socialcov_period_1", 1, date(2020, 6, 15), "risk_relaxation", "Policy-aligned reopening anchor; exact survey window not exposed in the Zenodo CSV metadata."),
        ("socialcov_period_2", 2, date(2020, 9, 15), "mask_mandate", "Policy-aligned back-to-school anchor; exact survey window not exposed in the Zenodo CSV metadata."),
        ("socialcov_period_3", 3, date(2020, 10, 20), "mask_mandate", "Policy-aligned autumn restriction anchor; exact survey window not exposed in the Zenodo CSV metadata."),
        ("socialcov_period_4", 4, date(2020, 11, 10), "confinement", "Policy-aligned second-lockdown anchor; exact survey window not exposed in the Zenodo CSV metadata."),
        ("socialcov_period_5", 5, date(2021, 6, 25), "risk_relaxation", "Policy-aligned reopening with vaccination anchor; exact survey window not exposed in the Zenodo CSV metadata."),
        ("socialcov_period_6", 6, date(2021, 10, 1), "risk_relaxation", "Policy-aligned late-2021 normalization anchor; exact survey window not exposed in the Zenodo CSV metadata."),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "period_id",
                "order_index",
                "representative_date",
                "policy_regime",
                "observed_mean_contacts",
                "observed_relative_contacts",
                "source_matrix_file",
                "source_url",
                "note",
            ],
        )
        writer.writeheader()
        for anchor, matrix_name in zip(anchors, SOCIALCOV_FILES, strict=True):
            period_id, order_index, representative_date, policy_regime, note = anchor
            matrix = np.loadtxt(raw_dir / matrix_name, delimiter=",", skiprows=1, usecols=range(1, 9))
            observed_mean_contacts = float(matrix.sum(axis=1).mean())
            writer.writerow(
                {
                    "period_id": period_id,
                    "order_index": order_index,
                    "representative_date": representative_date.isoformat(),
                    "policy_regime": policy_regime,
                    "observed_mean_contacts": observed_mean_contacts,
                    "observed_relative_contacts": observed_mean_contacts / PREPANDEMIC_CONTACT_REFERENCE,
                    "source_matrix_file": matrix_name,
                    "source_url": SOCIALCOV_BASE_URL.format(name=matrix_name),
                    "note": note,
                }
            )


def build_policy_timeline_csv(output_path: Path) -> None:
    periods = [
        (date(2020, 3, 17), date(2020, 5, 10), "Premier confinement national", "confinement"),
        (date(2020, 5, 11), date(2020, 10, 16), "Déconfinement progressif et été 2020", "risk_relaxation"),
        (date(2020, 10, 17), date(2020, 10, 29), "Couvre-feu d'automne", "mask_mandate"),
        (date(2020, 10, 30), date(2020, 12, 14), "Deuxième confinement national", "confinement"),
        (date(2020, 12, 15), date(2021, 4, 2), "Couvre-feu renforcé et restrictions hivernales", "mask_mandate"),
        (date(2021, 4, 3), date(2021, 5, 2), "Troisième confinement national", "confinement"),
        (date(2021, 5, 3), date(2021, 8, 8), "Réouverture progressive du printemps 2021", "risk_relaxation"),
        (date(2021, 8, 9), date(2022, 3, 13), "Passe sanitaire puis vaccinal", "mask_mandate"),
        (date(2022, 3, 14), date(2022, 12, 31), "Levée de la plupart des restrictions", "baseline"),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["start_date", "end_date", "policy_label", "policy_regime", "source"],
        )
        writer.writeheader()
        for start, end, label, regime in periods:
            writer.writerow(
                {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "policy_label": label,
                    "policy_regime": regime,
                    "source": "Vie publique, Chronologie des mesures sanitaires liées à la Covid-19.",
                }
            )


def policy_regime_for_date(value: date) -> str:
    for start, end, _, regime in [
        (date(2020, 3, 17), date(2020, 5, 10), None, "confinement"),
        (date(2020, 5, 11), date(2020, 10, 16), None, "risk_relaxation"),
        (date(2020, 10, 17), date(2020, 10, 29), None, "mask_mandate"),
        (date(2020, 10, 30), date(2020, 12, 14), None, "confinement"),
        (date(2020, 12, 15), date(2021, 4, 2), None, "mask_mandate"),
        (date(2021, 4, 3), date(2021, 5, 2), None, "confinement"),
        (date(2021, 5, 3), date(2021, 8, 8), None, "risk_relaxation"),
        (date(2021, 8, 9), date(2022, 3, 13), None, "mask_mandate"),
    ]:
        if start <= value <= end:
            return regime
    return "baseline"


def main() -> int:
    download_file(COVIPREV_URL, COVIPREV_RAW_PATH)
    for name in SOCIALCOV_FILES:
        download_file(SOCIALCOV_BASE_URL.format(name=name), SOCIALCOV_RAW_DIR / name)
    build_coviprev_csv(COVIPREV_RAW_PATH, INTERIM_ROOT / "coviprev_behavior_france.csv")
    build_socialcov_csv(SOCIALCOV_RAW_DIR, INTERIM_ROOT / "socialcov_contacts_periods.csv")
    build_policy_timeline_csv(INTERIM_ROOT / "policy_timeline_france.csv")
    print("Saved curated time-series files to data/interim/")
    return 0


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root:
        values.append("".join(text.text or "" for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    return values


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find("a:v", XML_NS)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value)]
    return value


def _excel_column_to_index(label: str) -> int:
    value = 0
    for char in label:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _parse_coviprev_dates(wave_label: str) -> tuple[date, date]:
    month_map = {
        "janvier": 1,
        "février": 2,
        "fevrier": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "août": 8,
        "aout": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "décembre": 12,
        "decembre": 12,
    }
    year_by_wave = {
        17: 2020,
        18: 2020,
        19: 2020,
        20: 2021,
        21: 2021,
        22: 2021,
        23: 2021,
        24: 2021,
        25: 2021,
        26: 2021,
        27: 2021,
        28: 2021,
    }
    match = re.search(r"vague\s+(\d+)\s*:\s*(.+)", wave_label, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse CoviPrev wave label: {wave_label}")
    wave_num = int(match.group(1))
    payload = match.group(2).strip().lower().replace("  ", " ")
    year = year_by_wave[wave_num]
    month_name = next(name for name in month_map if name in payload)
    month = month_map[month_name]
    numbers = [int(item) for item in re.findall(r"\d+", payload)]
    if len(numbers) < 2:
        raise ValueError(f"Could not parse date span in CoviPrev label: {wave_label}")
    start_day, end_day = numbers[0], numbers[1]
    end_month = month
    if start_day > end_day and month_name in {"août", "aout", "septembre"}:
        # not needed for the current workbook but kept for robustness
        end_month = month + 1
    return date(year, month, start_day), date(year, end_month, end_day)


def _midpoint_date(start: date, end: date) -> date:
    return start + (end - start) / 2


def _to_float(value: str | None) -> float:
    if value in (None, ""):
        raise ValueError("Expected numeric value, found empty cell")
    return float(value)


def _to_optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
