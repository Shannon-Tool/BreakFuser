from __future__ import annotations

import math

import pytest

from breakfuser.medical import (
    half_life,
    loading_dose,
    maintenance_dose_rate,
    medical_deterministic_answer,
)


def test_one_compartment_calculations_are_deterministic() -> None:
    assert half_life(volume_of_distribution=40, clearance=4) == pytest.approx(6.93, abs=0.005)
    assert maintenance_dose_rate(clearance=4, target_concentration=2) == 8
    assert loading_dose(volume_of_distribution=40, target_concentration=2) == 80


def test_half_life_uses_natural_logarithm() -> None:
    assert half_life(10, 2) == math.log(2) * 5


def test_fully_specified_calculation_bypasses_model_arithmetic() -> None:
    answer = medical_deterministic_answer(
        "For a synthetic one-compartment IV drug, clearance is 4 L/h, volume of distribution is 40 L, and target steady-state concentration is 2 mg/L. Calculate the half-life, maintenance dose rate, and loading dose."
    )
    assert answer is not None
    assert "6.93 h" in answer
    assert "8 mg/h" in answer
    assert "80 mg" in answer


def test_incomplete_clinical_narrative_does_not_bypass_fusion() -> None:
    assert (
        medical_deterministic_answer("Clearance is 4 L/h and volume of distribution is 40 L")
        is None
    )


@pytest.mark.parametrize(
    ("function", "kwargs"),
    [
        (half_life, {"volume_of_distribution": 0, "clearance": 4}),
        (half_life, {"volume_of_distribution": 40, "clearance": math.inf}),
        (maintenance_dose_rate, {"clearance": 4, "target_concentration": -1}),
        (loading_dose, {"volume_of_distribution": math.nan, "target_concentration": 2}),
    ],
)
def test_invalid_parameters_are_rejected(function, kwargs) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        function(**kwargs)
