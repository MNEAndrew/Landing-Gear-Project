"""
Unit registry and helpers for dimensional calculations.

Uses pint library to ensure dimensional correctness throughout
all physics calculations.
"""

import pint

# Create a shared unit registry for the entire application
ureg = pint.UnitRegistry()

# Shorthand for creating quantities
Q_ = ureg.Quantity

# Common unit definitions for convenience
meter = ureg.meter
kilogram = ureg.kilogram
newton = ureg.newton
joule = ureg.joule
second = ureg.second
pascal = ureg.pascal
kPa = ureg.kilopascal

# Gravitational acceleration (standard sea level)
G_STANDARD = Q_(9.80665, "m/s^2")


def to_base_units(quantity: pint.Quantity) -> pint.Quantity:
    """Convert a quantity to SI base units."""
    return quantity.to_base_units()


def magnitude_in(quantity: pint.Quantity, unit: str) -> float:
    """Get the magnitude of a quantity in specified units."""
    return quantity.to(unit).magnitude


def kg_to_N(mass_kg: float) -> float:
    """Convert mass in kg to weight in Newtons at standard gravity."""
    return mass_kg * G_STANDARD.magnitude


def N_to_kg(force_N: float) -> float:
    """Convert weight in Newtons to equivalent mass in kg."""
    return force_N / G_STANDARD.magnitude

