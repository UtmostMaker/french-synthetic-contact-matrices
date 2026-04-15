from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen


GOOGLE_MOBILITY_ZIP_URL = "https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip"
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
DEFAULT_RAW_DIR = DEFAULT_DATA_ROOT / "raw" / "google"
DEFAULT_INTERIM_PATH = DEFAULT_DATA_ROOT / "interim" / "google_mobility_france.csv"
FRANCE_YEARLY_FILES = [
    "2020_FR_Region_Mobility_Report.csv",
    "2021_FR_Region_Mobility_Report.csv",
    "2022_FR_Region_Mobility_Report.csv",
]

POLICY_PERIODS = [
    ("pre_pandemic_baseline", date(2020, 1, 3), date(2020, 3, 16)),
    ("first_lockdown", date(2020, 3, 17), date(2020, 5, 10)),
    ("deconfinement_summer_2020", date(2020, 5, 11), date(2020, 9, 30)),
    ("second_wave_restrictions", date(2020, 10, 17), date(2020, 12, 14)),
    ("curfew_winter_2020_2021", date(2020, 12, 15), date(2021, 4, 2)),
    ("pass_sanitaire", date(2021, 8, 9), date(2021, 10, 15)),
]


@dataclass(frozen=True, slots=True)
class GoogleMobilitySummary:
    policy_period: str
    start_date: str
    end_date: str
    retail_and_recreation_change: float
    grocery_and_pharmacy_change: float
    parks_change: float
    transit_change: float
    workplaces_change: float
    residential_change: float
    observed_mobility_reduction: float
    n_days: int
    source_url: str


MOBILITY_FIELDS = [
    "retail_and_recreation_percent_change_from_baseline",
    "grocery_and_pharmacy_percent_change_from_baseline",
    "parks_percent_change_from_baseline",
    "transit_stations_percent_change_from_baseline",
    "workplaces_percent_change_from_baseline",
    "residential_percent_change_from_baseline",
]


def ensure_google_france_mobility_csv(
    output_path: str | Path = DEFAULT_INTERIM_PATH,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    force_download: bool = False,
) -> Path:
    output = Path(output_path)
    if output.exists() and not force_download:
        with output.open("r", encoding="utf-8") as handle:
            existing_lines = sum(1 for _ in handle)
        if existing_lines > 1:
            return output

    raw_root = Path(raw_dir)
    raw_root.mkdir(parents=True, exist_ok=True)
    archive_path = raw_root / "Region_Mobility_Report_CSVs.zip"
    if force_download or not archive_path.exists():
        _download_file(GOOGLE_MOBILITY_ZIP_URL, archive_path)

    rows = load_france_national_rows_from_zip(archive_path)
    summaries = summarize_france_policy_periods(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "policy_period",
                "start_date",
                "end_date",
                "retail_and_recreation_change",
                "grocery_and_pharmacy_change",
                "parks_change",
                "transit_change",
                "workplaces_change",
                "residential_change",
                "observed_mobility_reduction",
                "n_days",
                "source_url",
            ],
        )
        writer.writeheader()
        for item in summaries:
            writer.writerow(asdict(item))
    return output


def load_google_france_mobility(path: str | Path = DEFAULT_INTERIM_PATH) -> list[GoogleMobilitySummary]:
    file_path = Path(path)
    if not file_path.exists():
        ensure_google_france_mobility_csv(file_path)
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            GoogleMobilitySummary(
                policy_period=str(row["policy_period"]),
                start_date=str(row["start_date"]),
                end_date=str(row["end_date"]),
                retail_and_recreation_change=float(row["retail_and_recreation_change"]),
                grocery_and_pharmacy_change=float(row["grocery_and_pharmacy_change"]),
                parks_change=float(row["parks_change"]),
                transit_change=float(row["transit_change"]),
                workplaces_change=float(row["workplaces_change"]),
                residential_change=float(row["residential_change"]),
                observed_mobility_reduction=float(row["observed_mobility_reduction"]),
                n_days=int(row["n_days"]),
                source_url=str(row["source_url"]),
            )
            for row in reader
            if row
        ]


def load_france_national_rows_from_zip(zip_path: str | Path) -> list[dict[str, str]]:
    archive = Path(zip_path)
    if not archive.exists():
        raise FileNotFoundError(f"Google mobility archive not found: {archive}")
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(archive) as zf:
        for name in FRANCE_YEARLY_FILES:
            with zf.open(name, "r") as handle:
                text = io.TextIOWrapper(handle, encoding="utf-8", newline="")
                reader = csv.DictReader(text)
                for row in reader:
                    if row.get("country_region_code") != "FR":
                        continue
                    if any(row.get(key) for key in ("sub_region_1", "sub_region_2", "metro_area", "iso_3166_2_code", "census_fips_code")):
                        continue
                    rows.append(dict(row))
    rows.sort(key=lambda item: str(item["date"]))
    return rows


def summarize_france_policy_periods(rows: Iterable[dict[str, str]]) -> list[GoogleMobilitySummary]:
    cached = list(rows)
    summaries: list[GoogleMobilitySummary] = []
    for policy_period, start, end in POLICY_PERIODS:
        selected = [row for row in cached if start.isoformat() <= str(row["date"]) <= end.isoformat()]
        if not selected:
            continue
        means = {field: _mean(_parse_float(row.get(field)) for row in selected) for field in MOBILITY_FIELDS}
        reduction = _observed_mobility_reduction(means)
        summaries.append(
            GoogleMobilitySummary(
                policy_period=policy_period,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                retail_and_recreation_change=means["retail_and_recreation_percent_change_from_baseline"],
                grocery_and_pharmacy_change=means["grocery_and_pharmacy_percent_change_from_baseline"],
                parks_change=means["parks_percent_change_from_baseline"],
                transit_change=means["transit_stations_percent_change_from_baseline"],
                workplaces_change=means["workplaces_percent_change_from_baseline"],
                residential_change=means["residential_percent_change_from_baseline"],
                observed_mobility_reduction=reduction,
                n_days=len(selected),
                source_url=GOOGLE_MOBILITY_ZIP_URL,
            )
        )
    return summaries


def _observed_mobility_reduction(means: dict[str, float]) -> float:
    raw = (
        -means["retail_and_recreation_percent_change_from_baseline"]
        -means["transit_stations_percent_change_from_baseline"]
        -means["workplaces_percent_change_from_baseline"]
        + means["residential_percent_change_from_baseline"]
    ) / 400.0
    return max(0.0, min(1.0, raw))


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def _parse_float(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _mean(values: Iterable[float]) -> float:
    data = list(values)
    if not data:
        return 0.0
    return float(sum(data) / len(data))
