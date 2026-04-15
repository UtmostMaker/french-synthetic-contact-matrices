import numpy as np

from contact_matrix_fr.baselines import BaselineBuilder, BaselineInputs, demographic_reweight


def test_demographic_reweight_shape():
    matrix = np.array([[2.0, 1.0], [1.0, 2.0]])
    pop = np.array([10.0, 20.0])
    out = demographic_reweight(matrix, pop)
    assert out.shape == (2, 2)


def test_demographic_scaling_runs_with_components():
    builder = BaselineBuilder()
    inputs = BaselineInputs(
        population_by_age=np.array([10.0, 20.0]),
        home_matrix=np.array([[1.0, 0.5], [0.5, 1.0]]),
        school_matrix=np.array([[0.2, 0.1], [0.1, 0.2]]),
        work_matrix=np.array([[0.3, 0.4], [0.4, 0.3]]),
        other_matrix=np.array([[0.1, 0.2], [0.2, 0.1]]),
    )
    out = builder.demographic_scaling(inputs)
    assert out.name == "demographic_scaling"
    assert out.total_matrix.shape == (2, 2)
