"""Deterministic one-compartment pharmacokinetic calculations."""

from __future__ import annotations

import math
import re


def _positive_finite(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def half_life(volume_of_distribution: float, clearance: float) -> float:
    """Return half-life in the reciprocal of the clearance time unit."""
    volume = _positive_finite("volume_of_distribution", volume_of_distribution)
    clearance = _positive_finite("clearance", clearance)
    return math.log(2) * volume / clearance


def maintenance_dose_rate(clearance: float, target_concentration: float) -> float:
    """Return maintenance dose per clearance time unit at steady state."""
    clearance = _positive_finite("clearance", clearance)
    concentration = _positive_finite("target_concentration", target_concentration)
    return clearance * concentration


def loading_dose(volume_of_distribution: float, target_concentration: float) -> float:
    """Return the one-compartment intravenous loading dose before bioavailability adjustment."""
    volume = _positive_finite("volume_of_distribution", volume_of_distribution)
    concentration = _positive_finite("target_concentration", target_concentration)
    return volume * concentration


def _number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def medical_deterministic_answer(question: str) -> str | None:
    """Calculate a fully specified synthetic one-compartment request in L, L/h, and mg/L."""
    lowered = question.lower()
    clearance_match = re.search(
        r"\bclearance\b\s*(?:is|=|of)?\s*(\d+(?:\.\d+)?)\s*l\s*/\s*h\b", lowered
    )
    volume_match = re.search(
        r"\bvolume of distribution\b\s*(?:is|=|of)?\s*(\d+(?:\.\d+)?)\s*l\b", lowered
    )
    concentration_match = re.search(
        r"\btarget(?: steady-state)? concentration\b\s*(?:is|=|of)?\s*(\d+(?:\.\d+)?)\s*mg\s*/\s*l\b",
        lowered,
    )
    if not (clearance_match and volume_match and concentration_match):
        return None
    clearance = float(clearance_match.group(1))
    volume = float(volume_match.group(1))
    concentration = float(concentration_match.group(1))
    calculations: list[str] = []
    if "half-life" in lowered:
        value = half_life(volume, clearance)
        calculations.append(f"half-life = ln(2) × Vd / CL = {_number(value)} h")
    if "maintenance" in lowered:
        value = maintenance_dose_rate(clearance, concentration)
        calculations.append(f"maintenance dose rate = CL × Css = {_number(value)} mg/h")
    if "loading" in lowered:
        value = loading_dose(volume, concentration)
        calculations.append(f"loading dose = Vd × Css = {_number(value)} mg")
    return "; ".join(calculations) if calculations else None
