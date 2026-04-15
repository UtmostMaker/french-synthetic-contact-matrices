from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class CoviPrevWave:
    wave: str
    start_date: str
    end_date: str
    midpoint_date: str
    policy_regime: str
    mask_public_pct: float
    handwashing_pct: float
    avoid_gatherings_pct: float
    greeting_avoidance_pct: float
    ventilation_pct: float | None
    adult_vaccine_intent_pct: float | None
    adult_vaccinated_pct: float | None
    observed_prevention_index: float


@dataclass(frozen=True, slots=True)
class SocialCovPeriod:
    period_id: str
    order_index: int
    start_date: str
    end_date: str
    representative_date: str
    policy_regime: str
    observed_mean_contacts: float
    observed_relative_contacts: float
    source_matrix_file: str
    note: str


@dataclass(frozen=True, slots=True)
class PolicyPeriod:
    start_date: str
    end_date: str
    policy_label: str
    policy_regime: str
    source: str


DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "interim"


def load_coviprev_waves(path: str | Path = DEFAULT_DATA_ROOT / "coviprev_behavior_france.csv") -> list[CoviPrevWave]:
    rows = _read_csv_dicts(path)
    waves: list[CoviPrevWave] = []
    for row in rows:
        waves.append(
            CoviPrevWave(
                wave=str(row["wave"]),
                start_date=str(row["start_date"]),
                end_date=str(row["end_date"]),
                midpoint_date=str(row["midpoint_date"]),
                policy_regime=str(row["policy_regime"]),
                mask_public_pct=float(row["mask_public_pct"]),
                handwashing_pct=float(row["handwashing_pct"]),
                avoid_gatherings_pct=float(row["avoid_gatherings_pct"]),
                greeting_avoidance_pct=float(row["greeting_avoidance_pct"]),
                ventilation_pct=_optional_float(row.get("ventilation_pct")),
                adult_vaccine_intent_pct=_optional_float(row.get("adult_vaccine_intent_pct")),
                adult_vaccinated_pct=_optional_float(row.get("adult_vaccinated_pct")),
                observed_prevention_index=float(row["observed_prevention_index"]),
            )
        )
    return waves


def load_socialcov_periods(path: str | Path = DEFAULT_DATA_ROOT / "socialcov_contacts_periods.csv") -> list[SocialCovPeriod]:
    rows = _read_csv_dicts(path)
    periods: list[SocialCovPeriod] = []
    for row in rows:
        periods.append(
            SocialCovPeriod(
                period_id=str(row["period_id"]),
                order_index=int(row["order_index"]),
                start_date=str(row.get("start_date", row["representative_date"])),
                end_date=str(row.get("end_date", row["representative_date"])),
                representative_date=str(row["representative_date"]),
                policy_regime=str(row["policy_regime"]),
                observed_mean_contacts=float(row["observed_mean_contacts"]),
                observed_relative_contacts=float(row["observed_relative_contacts"]),
                source_matrix_file=str(row["source_matrix_file"]),
                note=str(row["note"]),
            )
        )
    return periods


def load_policy_timeline(path: str | Path = DEFAULT_DATA_ROOT / "policy_timeline_france.csv") -> list[PolicyPeriod]:
    rows = _read_csv_dicts(path)
    timeline: list[PolicyPeriod] = []
    for row in rows:
        timeline.append(
            PolicyPeriod(
                start_date=str(row["start_date"]),
                end_date=str(row["end_date"]),
                policy_label=str(row["policy_label"]),
                policy_regime=str(row["policy_regime"]),
                source=str(row["source"]),
            )
        )
    return timeline


def load_time_series_bundle(data_root: str | Path = DEFAULT_DATA_ROOT) -> dict[str, Any]:
    root = Path(data_root)
    coviprev = load_coviprev_waves(root / "coviprev_behavior_france.csv")
    socialcov = load_socialcov_periods(root / "socialcov_contacts_periods.csv")
    policy = load_policy_timeline(root / "policy_timeline_france.csv")

    return {
        "coviprev": coviprev,
        "socialcov": socialcov,
        "policy_timeline": policy,
        "coviprev_dates": np.array([wave.midpoint_date for wave in coviprev], dtype=object),
        "coviprev_observed_prevention": np.array([wave.observed_prevention_index for wave in coviprev], dtype=float),
        "socialcov_dates": np.array([period.representative_date for period in socialcov], dtype=object),
        "socialcov_observed_relative_contacts": np.array(
            [period.observed_relative_contacts for period in socialcov], dtype=float
        ),
    }


def _read_csv_dicts(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Time-series file not found: {file_path}")
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader if row]


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
