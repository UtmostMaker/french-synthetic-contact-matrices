from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .comes_f_parser import load_comes_f_workbook


Array = np.ndarray
DEFAULT_AGE_LABELS = [
    "0-4",
    "5-9",
    "10-14",
    "15-19",
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65-69",
    "70-74",
    "75-79",
    "80+",
]


def load_comes_f(path: str | Path, dry_run: bool = False, seed: int = 2026) -> dict[str, Any]:
    """Load a COMES-F-like contact matrix and minimal metadata.

    Parameters
    ----------
    path:
        Path to the source file. Supported formats include the public COMES-F
        ``.xlsx`` workbook plus the older ``.json`` and ``.npy`` placeholders.
    dry_run:
        If ``True``, ignore the file on disk and return plausible synthetic data
        following the expected schema.
    seed:
        Random seed used only in ``dry_run`` mode.

    Returns
    -------
    dict
        Dictionary containing at least ``matrix`` (square ``numpy.ndarray``),
        ``age_labels`` (list of strings), and ``metadata`` (dictionary).

    Notes
    -----
    The preferred real-data path is the public Figshare workbook released by the
    COMES-F authors. JSON and NPY remain supported for frozen intermediate files.
    """

    if dry_run:
        return _synthetic_comes_f(seed=seed)

    file_path = _validate_existing_path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".xlsx":
        return load_comes_f_workbook(file_path)

    if suffix == ".npy":
        matrix = np.load(file_path)
        matrix = _validate_square_numeric_matrix(matrix, source=str(file_path))
        return {
            "matrix": matrix,
            "age_labels": _default_age_labels(matrix.shape[0]),
            "metadata": {
                "source": str(file_path),
                "format": "npy-placeholder",
                "survey": "COMES-F",
                "todo": "TODO: attach official survey metadata and weighting fields.",
            },
        }

    if suffix == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("COMES-F JSON payload must be a dictionary")
        if "matrix" not in payload:
            raise ValueError("COMES-F JSON payload must contain a 'matrix' field")

        matrix = _validate_square_numeric_matrix(payload["matrix"], source=str(file_path))
        age_labels = payload.get("age_labels") or _default_age_labels(matrix.shape[0])
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "source": str(file_path),
            "format": "json-placeholder",
            "todo": metadata.get(
                "todo",
                "TODO: align JSON keys with the final harmonized COMES-F export schema.",
            ),
        }
        return {"matrix": matrix, "age_labels": list(age_labels), "metadata": metadata}

    raise ValueError(
        f"Unsupported COMES-F format: {suffix}. Expected .xlsx, .json, or .npy."
    )


def load_insee_population(path: str | Path, dry_run: bool = False, seed: int = 2026) -> Array:
    """Load a one-dimensional INSEE-like population vector by age group.

    Parameters
    ----------
    path:
        Path to a ``.npy``, ``.csv``, or ``.json`` file containing age-group
        population counts.
    dry_run:
        If ``True``, return a plausible synthetic French age distribution.
    seed:
        Random seed used only in ``dry_run`` mode.

    Returns
    -------
    numpy.ndarray
        One-dimensional array of non-negative population counts.

    Notes
    -----
    TODO: replace the placeholder loaders with the exact INSEE extraction logic
    once the target table identifier and harmonized age-bin aggregation are fixed.
    """

    if dry_run:
        return _synthetic_population(seed=seed)

    file_path = _validate_existing_path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".npy":
        values = np.load(file_path)
        return _validate_population_vector(values, source=str(file_path))

    if suffix == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            if "population" in payload:
                values = payload["population"]
            elif "values" in payload:
                values = payload["values"]
            else:
                raise ValueError("INSEE JSON must contain 'population' or 'values'")
        elif isinstance(payload, list):
            values = payload
        else:
            raise ValueError("INSEE JSON payload must be a list or a dictionary")
        return _validate_population_vector(values, source=str(file_path))

    if suffix == ".csv":
        values = _read_numeric_column_from_csv(file_path)
        return _validate_population_vector(values, source=str(file_path))

    raise ValueError(
        f"Unsupported INSEE population format: {suffix}. Expected .npy, .json, or .csv."
    )


def load_coviprev_behavioral_proxy(
    path: str | Path,
    dry_run: bool = False,
    seed: int = 2026,
) -> dict[str, Any]:
    """Load a CoviPrev-like behavioral time series proxy.

    Parameters
    ----------
    path:
        Path to a ``.json`` or ``.csv`` file containing a date-indexed behavioral
        proxy such as masking, mobility reduction, or risk-avoidance indicators.
    dry_run:
        If ``True``, return a plausible synthetic weekly time series.
    seed:
        Random seed used only in ``dry_run`` mode.

    Returns
    -------
    dict
        Dictionary with ``dates``, ``proxy``, and ``metadata`` fields.

    Notes
    -----
    TODO: confirm the exact CoviPrev variables, naming conventions, and date
    alignment strategy once the curated download step is in place.
    """

    if dry_run:
        return _synthetic_coviprev(seed=seed)

    file_path = _validate_existing_path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("CoviPrev JSON payload must be a dictionary")
        dates = payload.get("dates")
        proxy = payload.get("proxy") or payload.get("values")
        if dates is None or proxy is None:
            raise ValueError("CoviPrev JSON must contain 'dates' and 'proxy' or 'values'")
        series = _validate_proxy_series(dates=dates, proxy=proxy, source=str(file_path))
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "source": str(file_path),
            "format": "json-placeholder",
            "todo": metadata.get(
                "todo",
                "TODO: map the final CoviPrev indicator names to project conventions.",
            ),
        }
        return {**series, "metadata": metadata}

    if suffix == ".csv":
        dates: list[str] = []
        proxy: list[float] = []
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CoviPrev CSV must contain a header row")
            date_key = "date" if "date" in reader.fieldnames else reader.fieldnames[0]
            value_candidates = [
                key for key in reader.fieldnames if key.lower() in {"proxy", "value", "values", "score"}
            ]
            value_key = value_candidates[0] if value_candidates else reader.fieldnames[-1]
            for row in reader:
                if not row:
                    continue
                if row.get(date_key) in (None, ""):
                    continue
                dates.append(str(row[date_key]))
                try:
                    proxy.append(float(row[value_key]))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid numeric value in CoviPrev CSV column '{value_key}'"
                    ) from exc
        series = _validate_proxy_series(dates=dates, proxy=proxy, source=str(file_path))
        series["metadata"] = {
            "source": str(file_path),
            "format": "csv-placeholder",
            "todo": "TODO: replace CSV heuristics with the definitive curated extract format.",
        }
        return series

    raise ValueError(
        f"Unsupported CoviPrev proxy format: {suffix}. Expected .json or .csv."
    )


def _synthetic_comes_f(seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n = len(DEFAULT_AGE_LABELS)
    age_axis = np.linspace(0.0, 1.0, num=n)
    distance = np.abs(age_axis[:, None] - age_axis[None, :])
    base = 3.2 * np.exp(-(distance**2) / (2.0 * 0.09**2)) + 0.12
    parent_child = 0.65 * (
        np.outer(np.exp(-((age_axis - 0.18) ** 2) / 0.01), np.exp(-((age_axis - 0.52) ** 2) / 0.02))
        + np.outer(np.exp(-((age_axis - 0.52) ** 2) / 0.02), np.exp(-((age_axis - 0.18) ** 2) / 0.01))
    )
    senior_child = 0.18 * (
        np.outer(np.exp(-((age_axis - 0.10) ** 2) / 0.02), np.exp(-((age_axis - 0.88) ** 2) / 0.01))
        + np.outer(np.exp(-((age_axis - 0.88) ** 2) / 0.01), np.exp(-((age_axis - 0.10) ** 2) / 0.02))
    )
    noise = rng.normal(0.0, 0.03, size=(n, n))
    matrix = np.clip(base + parent_child + senior_child + 0.5 * (noise + noise.T), a_min=0.0, a_max=None)
    return {
        "matrix": matrix,
        "age_labels": list(DEFAULT_AGE_LABELS),
        "metadata": {
            "source": "synthetic-dry-run",
            "survey": "COMES-F",
            "format": "in-memory",
            "seed": seed,
            "todo": "TODO: substitute the harmonized empirical COMES-F matrix once available.",
        },
    }


def _synthetic_population(seed: int) -> Array:
    rng = np.random.default_rng(seed)
    n = len(DEFAULT_AGE_LABELS)
    age_axis = np.linspace(0.0, 1.0, num=n)
    population = 1050.0 * np.exp(-2.1 * age_axis) + 240.0
    population += 110.0 * np.exp(-((age_axis - 0.72) ** 2) / 0.03)
    population += rng.normal(0.0, 18.0, size=n)
    return _validate_population_vector(np.clip(population, a_min=25.0, a_max=None), source="dry_run")


def _synthetic_coviprev(seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n_weeks = 16
    dates = np.arange(np.datetime64("2021-01-03"), np.datetime64("2021-01-03") + n_weeks * 7, 7)
    baseline = np.linspace(0.72, 0.48, num=n_weeks)
    seasonal = 0.07 * np.sin(np.linspace(0.0, 2.5 * np.pi, num=n_weeks))
    noise = rng.normal(0.0, 0.025, size=n_weeks)
    proxy = np.clip(baseline + seasonal + noise, a_min=0.0, a_max=1.0)
    return {
        "dates": [str(date) for date in dates],
        "proxy": proxy.astype(float),
        "metadata": {
            "source": "synthetic-dry-run",
            "indicator": "behavioral_proxy",
            "frequency": "weekly",
            "seed": seed,
            "todo": "TODO: map this placeholder proxy to real CoviPrev behavioral indicators.",
        },
    }


def _validate_existing_path(path: str | Path) -> Path:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Expected a file path, got: {file_path}")
    return file_path


def _validate_square_numeric_matrix(matrix: Any, source: str) -> Array:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"Expected a square matrix in {source}")
    if arr.size == 0:
        raise ValueError(f"Matrix cannot be empty in {source}")
    if np.any(arr < 0):
        raise ValueError(f"Matrix cannot contain negative entries in {source}")
    return arr


def _validate_population_vector(values: Any, source: str) -> Array:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"Population data must be one-dimensional in {source}")
    if arr.size == 0:
        raise ValueError(f"Population vector cannot be empty in {source}")
    if np.any(arr < 0):
        raise ValueError(f"Population vector cannot contain negative counts in {source}")
    return arr


def _validate_proxy_series(dates: Any, proxy: Any, source: str) -> dict[str, Any]:
    date_list = [str(item) for item in dates]
    proxy_array = np.asarray(proxy, dtype=float)
    if proxy_array.ndim != 1:
        raise ValueError(f"Proxy values must be one-dimensional in {source}")
    if len(date_list) != proxy_array.size:
        raise ValueError(f"Dates and proxy values must have the same length in {source}")
    if proxy_array.size == 0:
        raise ValueError(f"Proxy series cannot be empty in {source}")
    return {"dates": date_list, "proxy": proxy_array}


def _read_numeric_column_from_csv(file_path: Path) -> list[float]:
    values: list[float] = []
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file must contain a header row")
        numeric_key = None
        for candidate in reader.fieldnames:
            if candidate.lower() in {"population", "value", "values", "count", "counts"}:
                numeric_key = candidate
                break
        numeric_key = numeric_key or reader.fieldnames[-1]
        for row in reader:
            if not row:
                continue
            raw_value = row.get(numeric_key)
            if raw_value in (None, ""):
                continue
            try:
                values.append(float(raw_value))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid numeric value '{raw_value}' in CSV column '{numeric_key}'"
                ) from exc
    if not values:
        raise ValueError(f"No numeric values found in CSV file: {file_path}")
    return values


def _default_age_labels(size: int) -> list[str]:
    if size == len(DEFAULT_AGE_LABELS):
        return list(DEFAULT_AGE_LABELS)
    return [f"bin_{idx}" for idx in range(size)]
