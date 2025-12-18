"""
Physics calculations for landing gear sizing.

This module provides unit-aware calculations using pint for:
- Touchdown energy and shock absorption
- Static and dynamic load distribution
- Geometry heuristics and constraints

All calculations use simplified models appropriate for conceptual design.
NOT for certification or detailed structural analysis.
"""

from gearrec.physics.units import ureg, Q_
from gearrec.physics.energy import (
    calculate_touchdown_energy,
    calculate_required_shock_force,
    calculate_stroke_range,
)
from gearrec.physics.loads import (
    calculate_static_load_split_tricycle,
    calculate_static_load_split_taildragger,
    calculate_dynamic_load_factor,
    calculate_tire_load_requirements,
)
from gearrec.physics.geometry import (
    estimate_fuselage_length,
    calculate_track_range,
    calculate_wheelbase_range,
    calculate_strut_length_range,
    estimate_cg_height,
    check_tip_back_margin,
    check_nose_over_margin,
)

__all__ = [
    "ureg",
    "Q_",
    "calculate_touchdown_energy",
    "calculate_required_shock_force",
    "calculate_stroke_range",
    "calculate_static_load_split_tricycle",
    "calculate_static_load_split_taildragger",
    "calculate_dynamic_load_factor",
    "calculate_tire_load_requirements",
    "estimate_fuselage_length",
    "calculate_track_range",
    "calculate_wheelbase_range",
    "calculate_strut_length_range",
    "estimate_cg_height",
    "check_tip_back_margin",
    "check_nose_over_margin",
]

