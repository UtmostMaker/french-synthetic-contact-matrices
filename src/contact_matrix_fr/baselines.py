from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


Array = np.ndarray
_MAX_AGE = 85.0


@dataclass
class BaselineInputs:
    """Container for baseline matrix-generation inputs.

    This intentionally starts small. It can be extended once the data schema
    is frozen.
    """

    population_by_age: Array
    home_matrix: Array | None = None
    school_matrix: Array | None = None
    work_matrix: Array | None = None
    other_matrix: Array | None = None
    metadata: Dict[str, str] | None = None


@dataclass
class BaselineOutput:
    name: str
    total_matrix: Array
    components: Dict[str, Array]
    notes: Dict[str, str]


class BaselineBuilder:
    """Non-agentic baseline family for the ROIA study.

    Phase 1 scope:
    - demographic scaling baseline
    - household-aware rule-based baseline
    - mobility augmentation placeholder
    """

    def demographic_scaling(self, inputs: BaselineInputs) -> BaselineOutput:
        if inputs.home_matrix is None:
            raise ValueError("home_matrix is required for demographic scaling")

        total = _sum_components(
            {
                "home": _safe_component(inputs.home_matrix),
                "school": _safe_component(inputs.school_matrix),
                "work": _safe_component(inputs.work_matrix),
                "other": _safe_component(inputs.other_matrix),
            }
        )
        scaled = demographic_reweight(total, inputs.population_by_age)
        return BaselineOutput(
            name="demographic_scaling",
            total_matrix=scaled,
            components={"total": scaled},
            notes={
                "status": "implemented-minimal",
                "assumption": "reweights an existing contact template by target population age structure",
            },
        )

    def household_rule_based(self, inputs: BaselineInputs) -> BaselineOutput:
        """Build a lightweight French household-aware synthetic contact matrix.

        Assumptions:
        - age bins span roughly 0 to 85 years and are evenly spaced,
        - household contacts are driven by parent-child, partner-like, and
          grandparent-child cohabitation patterns,
        - school contacts concentrate among school-age bins with a strong
          near-diagonal structure,
        - work contacts concentrate among working-age bins with a broader
          age band than school,
        - a low-intensity background component captures other-community mixing.

        The method is intentionally frugal: it only uses the target population
        age structure plus fixed French-style priors on household size and
        life-stage participation. It is meant as a plausible baseline, not a
        calibrated demographic simulator.
        """

        pop = _validate_population_vector(inputs.population_by_age)
        age_axis = _age_axis(pop.shape[0])
        child = _window(age_axis, 0.0, 17.0)
        school_age = _window(age_axis, 5.0, 18.0)
        young_adult = _window(age_axis, 18.0, 29.0)
        working_age = _window(age_axis, 18.0, 64.0)
        senior = _window(age_axis, 65.0, _MAX_AGE)
        grandparent = _window(age_axis, 70.0, _MAX_AGE)

        household_size_distribution = np.array([0.36, 0.33, 0.13, 0.11, 0.07])
        household_sizes = np.arange(1, 6, dtype=float)
        household_intensity = float(
            np.dot(household_size_distribution, household_sizes - 1.0)
        )

        household_density = pop / np.clip(pop.sum(), a_min=1.0, a_max=None)
        adult_household_role = np.clip(0.65 * working_age + 0.35 * young_adult, 0.0, 1.0)
        partner_profile = np.clip(0.75 * working_age + 0.55 * senior, 0.0, 1.0)

        same_age_home = np.diag(0.55 + 0.35 * household_density)
        parent_child_home = 1.75 * np.outer(adult_household_role, child)
        partner_home = 0.75 * _band_matrix(partner_profile, width=1.75)
        grandparent_home = 0.55 * (
            np.outer(grandparent, child) + np.outer(child, grandparent)
        )
        home = household_intensity * (
            same_age_home + parent_child_home + parent_child_home.T + partner_home + grandparent_home
        )
        home = _apply_population_weights(home, pop)

        school_band = _band_matrix(school_age, width=1.25)
        school_cross_age = 0.20 * (
            np.outer(school_age, adult_household_role) + np.outer(adult_household_role, school_age)
        )
        school = _apply_population_weights(3.25 * school_band + school_cross_age, pop)

        work_band = _band_matrix(working_age, width=2.75)
        intergenerational_work = 0.18 * (
            np.outer(working_age, senior) + np.outer(senior, working_age)
        )
        work = _apply_population_weights(2.10 * work_band + intergenerational_work, pop)

        community_profile = np.clip(0.35 + 0.45 * working_age + 0.20 * senior, 0.0, 1.0)
        other = _apply_population_weights(
            0.35 * np.outer(community_profile, community_profile)
            + 0.10 * _band_matrix(np.ones_like(age_axis), width=4.0),
            pop,
        )

        total = home + school + work + other
        return BaselineOutput(
            name="household_rule_based",
            total_matrix=total,
            components={
                "home": home,
                "school": school,
                "work": work,
                "other": other,
                "total": total,
            },
            notes={
                "status": "implemented-rule-based",
                "assumption": (
                    "Uses fixed French-style household size priors plus heuristic "
                    "school/work participation curves over evenly spaced age bins."
                ),
                "todo": (
                    "TODO: replace generic household priors with directly harmonized "
                    "INSEE distributions once the target age-bin schema is fixed."
                ),
            },
        )

    def mobility_augmented(self, inputs: BaselineInputs) -> BaselineOutput:
        raise NotImplementedError(
            "Mobility augmentation is deferred until the rule-based core is stable."
        )


def demographic_reweight(matrix: Array, population_by_age: Array) -> Array:
    """Simple demographic reweighting placeholder.

    Current version applies row normalization and rescales by target age mass.
    This is intentionally conservative and should be replaced by the exact
    study-specific formula once data harmonization is complete.
    """

    matrix = np.asarray(matrix, dtype=float)
    pop = np.asarray(population_by_age, dtype=float)

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    if matrix.shape[0] != pop.shape[0]:
        raise ValueError("population vector must match matrix size")

    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    normalized = matrix / row_sums
    return normalized * pop.reshape(-1, 1)


def _safe_component(component: Array | None) -> Array:
    if component is None:
        raise ValueError("all required baseline components must be provided")
    return np.asarray(component, dtype=float)


def _sum_components(components: Dict[str, Array]) -> Array:
    values = list(components.values())
    if not values:
        raise ValueError("at least one matrix component is required")
    total = np.zeros_like(values[0], dtype=float)
    for value in values:
        total = total + value
    return total


def _validate_population_vector(population_by_age: Array) -> Array:
    pop = np.asarray(population_by_age, dtype=float)
    if pop.ndim != 1:
        raise ValueError("population_by_age must be a one-dimensional vector")
    if pop.size == 0:
        raise ValueError("population_by_age cannot be empty")
    if np.any(pop < 0):
        raise ValueError("population_by_age cannot contain negative values")
    if np.all(pop == 0):
        raise ValueError("population_by_age must contain at least one positive value")
    return pop


def _age_axis(size: int) -> Array:
    if size <= 0:
        raise ValueError("age axis size must be positive")
    if size == 1:
        return np.array([0.0], dtype=float)
    return np.linspace(0.0, _MAX_AGE, num=size, dtype=float)


def _window(age_axis: Array, lower: float, upper: float) -> Array:
    window = np.zeros_like(age_axis, dtype=float)
    mask = (age_axis >= lower) & (age_axis <= upper)
    window[mask] = 1.0
    return _soften(window)


def _soften(profile: Array) -> Array:
    softened = np.asarray(profile, dtype=float).copy()
    if softened.size <= 2:
        return np.clip(softened, 0.0, 1.0)
    kernel = np.array([0.25, 0.5, 0.25], dtype=float)
    padded = np.pad(softened, pad_width=1, mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return np.clip(smoothed, 0.0, 1.0)


def _band_matrix(profile: Array, width: float) -> Array:
    profile = np.asarray(profile, dtype=float)
    idx = np.arange(profile.size, dtype=float)
    distance = np.abs(idx[:, None] - idx[None, :])
    width = max(width, 1e-6)
    band = np.exp(-(distance**2) / (2.0 * width**2))
    return np.outer(profile, profile) * band


def _apply_population_weights(matrix: Array, population_by_age: Array) -> Array:
    matrix = np.asarray(matrix, dtype=float)
    pop = np.asarray(population_by_age, dtype=float)
    exposure = np.sqrt(np.outer(pop, pop))
    if exposure.max() > 0:
        exposure = exposure / exposure.max()
    return matrix * exposure
