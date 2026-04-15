from __future__ import annotations

from typing import Dict

import numpy as np


Array = np.ndarray


def matrix_mae(predicted: Array, reference: Array) -> float:
    """Return the mean absolute cell-wise error between two matrices.

    Both inputs must be numeric arrays with identical shapes. Empty arrays are
    rejected because the average absolute error would be undefined.
    """

    pred, ref = _validate_matching_arrays(predicted, reference)
    if pred.size == 0:
        raise ValueError("predicted and reference matrices cannot be empty")
    return float(np.mean(np.abs(pred - ref)))


def matrix_frobenius_distance(predicted: Array, reference: Array) -> float:
    """Return the Frobenius norm of the difference between two matrices."""

    pred, ref = _validate_matching_arrays(predicted, reference)
    return float(np.linalg.norm(pred - ref, ord="fro"))


def age_assortativity(matrix: Array) -> Dict[str, float]:
    """Summarize how much contact mass stays on or near the age diagonal.

    Returns a dictionary with:
    - diagonal_share: mass on the main diagonal divided by total mass
    - near_diagonal_share: mass on the main diagonal and first off-diagonals
      divided by total mass

    If the matrix has zero total mass, both shares are returned as 0.0.
    """

    arr = _validate_square_matrix(matrix)
    total_mass = float(arr.sum())
    if total_mass <= 0.0:
        return {"diagonal_share": 0.0, "near_diagonal_share": 0.0}

    diagonal_mass = float(np.trace(arr))
    distance = np.abs(np.subtract.outer(np.arange(arr.shape[0]), np.arange(arr.shape[1])))
    near_diagonal_mass = float(arr[distance <= 1].sum())
    return {
        "diagonal_share": diagonal_mass / total_mass,
        "near_diagonal_share": near_diagonal_mass / total_mass,
    }


def reciprocity_gap(matrix: Array) -> float:
    """Return the mean absolute asymmetry between mirrored matrix cells.

    A perfectly reciprocal matrix has a gap of 0.0. The function accepts any
    square numeric matrix and averages the absolute difference between the
    matrix and its transpose over all cells.
    """

    arr = _validate_square_matrix(matrix)
    return float(np.mean(np.abs(arr - arr.T)))


def series_mae(predicted: Array, reference: Array) -> float:
    """Return the mean absolute error between two one-dimensional series."""

    pred, ref = _validate_matching_series(predicted, reference)
    return float(np.mean(np.abs(pred - ref)))


def trend_direction_agreement(predicted: Array, reference: Array, tolerance: float = 1e-9) -> float:
    """Return the share of consecutive changes with matching direction."""

    pred, ref = _validate_matching_series(predicted, reference)
    if pred.size < 2:
        return 1.0

    pred_diff = np.diff(pred)
    ref_diff = np.diff(ref)

    def _sign(values: Array) -> Array:
        out = np.zeros_like(values, dtype=int)
        out[values > tolerance] = 1
        out[values < -tolerance] = -1
        return out

    return float(np.mean(_sign(pred_diff) == _sign(ref_diff)))


def peak_timing_error(predicted: Array, reference: Array) -> int:
    """Return the absolute index gap between predicted and observed peaks."""

    pred, ref = _validate_matching_series(predicted, reference)
    return int(abs(int(np.argmax(pred)) - int(np.argmax(ref))))


def peak_timing_accuracy(predicted: Array, reference: Array) -> float:
    """Map peak timing error to a bounded accuracy score in ``(0, 1]``."""

    return float(1.0 / (1.0 + peak_timing_error(predicted, reference)))


def _validate_matching_arrays(predicted: Array, reference: Array) -> tuple[Array, Array]:
    pred = np.asarray(predicted, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if pred.shape != ref.shape:
        raise ValueError("predicted and reference must have identical shapes")
    return pred, ref


def _validate_matching_series(predicted: Array, reference: Array) -> tuple[Array, Array]:
    pred = np.asarray(predicted, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if pred.ndim != 1 or ref.ndim != 1:
        raise ValueError("predicted and reference must be one-dimensional series")
    if pred.shape != ref.shape:
        raise ValueError("predicted and reference series must have identical shapes")
    if pred.size == 0:
        raise ValueError("predicted and reference series cannot be empty")
    return pred, ref


def _validate_square_matrix(matrix: Array) -> Array:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("matrix must be a square two-dimensional array")
    return arr
