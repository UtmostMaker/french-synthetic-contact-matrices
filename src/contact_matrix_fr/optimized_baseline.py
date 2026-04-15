from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize

from .baselines import (
    BaselineInputs,
    BaselineOutput,
    _age_axis,
    _apply_population_weights,
    _band_matrix,
    _validate_population_vector,
    _window,
)
from .metrics import matrix_mae, matrix_frobenius_distance


Array = np.ndarray


@dataclass(slots=True)
class OptimizedBaselineFit:
    weights: dict[str, float]
    objective_name: str
    objective_value: float
    success: bool
    optimizer_message: str
    iterations: int
    heuristic_mae: float
    optimized_mae: float
    heuristic_frobenius: float
    optimized_frobenius: float


class OptimizedBaselineBuilder:
    """Fit setting-specific weights for the structured baseline on COMES-F."""

    setting_names = ("home", "school", "work", "other")

    def build_components(self, inputs: BaselineInputs) -> dict[str, Array]:
        pop = _validate_population_vector(inputs.population_by_age)
        age_axis = _age_axis(pop.shape[0])
        child = _window(age_axis, 0.0, 17.0)
        school_age = _window(age_axis, 5.0, 18.0)
        young_adult = _window(age_axis, 18.0, 29.0)
        working_age = _window(age_axis, 18.0, 64.0)
        senior = _window(age_axis, 65.0, 85.0)
        grandparent = _window(age_axis, 70.0, 85.0)

        household_density = pop / np.clip(pop.sum(), a_min=1.0, a_max=None)
        adult_household_role = np.clip(0.65 * working_age + 0.35 * young_adult, 0.0, 1.0)
        partner_profile = np.clip(0.75 * working_age + 0.55 * senior, 0.0, 1.0)

        same_age_home = np.diag(0.55 + 0.35 * household_density)
        parent_child_home = np.outer(adult_household_role, child)
        partner_home = _band_matrix(partner_profile, width=1.75)
        grandparent_home = np.outer(grandparent, child) + np.outer(child, grandparent)
        home = _apply_population_weights(
            same_age_home + 1.75 * (parent_child_home + parent_child_home.T) + 0.75 * partner_home + 0.55 * grandparent_home,
            pop,
        )

        school_band = _band_matrix(school_age, width=1.25)
        school_cross_age = np.outer(school_age, adult_household_role) + np.outer(adult_household_role, school_age)
        school = _apply_population_weights(3.25 * school_band + 0.20 * school_cross_age, pop)

        work_band = _band_matrix(working_age, width=2.75)
        intergenerational_work = np.outer(working_age, senior) + np.outer(senior, working_age)
        work = _apply_population_weights(2.10 * work_band + 0.18 * intergenerational_work, pop)

        community_profile = np.clip(0.35 + 0.45 * working_age + 0.20 * senior, 0.0, 1.0)
        other = _apply_population_weights(
            0.35 * np.outer(community_profile, community_profile)
            + 0.10 * _band_matrix(np.ones_like(age_axis), width=4.0),
            pop,
        )
        return {"home": home, "school": school, "work": work, "other": other}

    def combine_components(self, components: dict[str, Array], weights: dict[str, float]) -> Array:
        total = np.zeros_like(next(iter(components.values())))
        for name in self.setting_names:
            total = total + float(weights[name]) * np.asarray(components[name], dtype=float)
        return 0.5 * (total + total.T)

    def fit(
        self,
        inputs: BaselineInputs,
        reference: Array,
        *,
        initial_weights: dict[str, float] | None = None,
        bounds: dict[str, tuple[float, float]] | None = None,
        penalty_strength: float = 0.01,
        maxiter: int = 2000,
    ) -> tuple[BaselineOutput, OptimizedBaselineFit]:
        components = self.build_components(inputs)
        reference = np.asarray(reference, dtype=float)
        if reference.shape != next(iter(components.values())).shape:
            raise ValueError("reference matrix shape does not match optimized baseline components")

        initial_weights = initial_weights or {name: 1.0 for name in self.setting_names}
        x0 = np.array([float(initial_weights[name]) for name in self.setting_names], dtype=float)
        bound_values = [bounds.get(name, (0.05, 4.0)) if bounds else (0.05, 4.0) for name in self.setting_names]

        heuristic_matrix = self.combine_components(components, {name: 1.0 for name in self.setting_names})
        heuristic_mae = float(matrix_mae(heuristic_matrix, reference))
        heuristic_frobenius = float(matrix_frobenius_distance(heuristic_matrix, reference))

        def objective(x: Array) -> float:
            weight_dict = {name: float(value) for name, value in zip(self.setting_names, x, strict=True)}
            predicted = self.combine_components(components, weight_dict)
            residual = predicted - reference
            regularization = penalty_strength * float(np.mean((x - 1.0) ** 2))
            return float(np.mean(residual**2) + regularization)

        result = minimize(
            objective,
            x0=x0,
            method="Powell",
            bounds=bound_values,
            options={"maxiter": int(maxiter), "xtol": 1e-5, "ftol": 1e-8},
        )

        fitted_weights = {name: float(value) for name, value in zip(self.setting_names, result.x, strict=True)}
        optimized_matrix = self.combine_components(components, fitted_weights)
        optimized_mae = float(matrix_mae(optimized_matrix, reference))
        optimized_frobenius = float(matrix_frobenius_distance(optimized_matrix, reference))

        output = BaselineOutput(
            name="optimized_household_rule_based",
            total_matrix=optimized_matrix,
            components={
                **{name: np.asarray(components[name], dtype=float) * fitted_weights[name] for name in self.setting_names},
                "total": optimized_matrix,
            },
            notes={
                "status": "implemented-optimized",
                "optimization_target": "regularized_mean_squared_error_vs_COMES-F",
                "weights": ", ".join(f"{name}={fitted_weights[name]:.4f}" for name in self.setting_names),
            },
        )
        fit = OptimizedBaselineFit(
            weights=fitted_weights,
            objective_name="regularized_mse",
            objective_value=float(result.fun),
            success=bool(result.success),
            optimizer_message=str(result.message),
            iterations=int(getattr(result, "nit", 0) or 0),
            heuristic_mae=heuristic_mae,
            optimized_mae=optimized_mae,
            heuristic_frobenius=heuristic_frobenius,
            optimized_frobenius=optimized_frobenius,
        )
        return output, fit


def fit_optimized_baseline(
    inputs: BaselineInputs,
    reference: Array,
    **kwargs: Any,
) -> tuple[BaselineOutput, OptimizedBaselineFit]:
    builder = OptimizedBaselineBuilder()
    return builder.fit(inputs, reference, **kwargs)
