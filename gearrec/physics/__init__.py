"""
Physics calculations for landing gear sizing.

This module provides unit-aware calculations using pint for:
- Touchdown energy and shock absorption
- Static and dynamic load distribution
- Geometry heuristics and constraints
- Tire catalog and matching

All calculations use simplified models appropriate for conceptual design.
NOT for certification or detailed structural analysis.
"""

from gearrec.physics.units import ureg, Q_, kg_to_N, N_to_kg, G_STANDARD
from gearrec.physics.energy import (
    calculate_touchdown_energy,
    calculate_required_shock_force,
    calculate_stroke_range,
    recommend_stroke_range_for_aircraft,
    calculate_load_factor_from_sink,
)
from gearrec.physics.loads import (
    calculate_static_load_split_tricycle,
    calculate_static_load_split_taildragger,
    calculate_dynamic_load_factor,
    calculate_tire_load_requirements,
    estimate_gear_positions_tricycle,
    estimate_gear_positions_taildragger,
    calculate_main_load_per_wheel,
    LoadSplit,
)
from gearrec.physics.geometry import (
    estimate_fuselage_length,
    calculate_track_range,
    calculate_wheelbase_range,
    calculate_strut_length_range,
    estimate_cg_height,
    check_tip_back_margin,
    check_nose_over_margin,
    check_ground_clearance,
    check_lateral_rollover,
    estimate_tire_diameter,
    SafetyCheckResult,
)
from gearrec.physics.tire_catalog import (
    find_matching_tires,
    estimate_tire_dimensions,
    TIRE_CATALOG,
)

__all__ = [
    # Units
    "ureg",
    "Q_",
    "kg_to_N",
    "N_to_kg",
    "G_STANDARD",
    # Energy
    "calculate_touchdown_energy",
    "calculate_required_shock_force",
    "calculate_stroke_range",
    "recommend_stroke_range_for_aircraft",
    "calculate_load_factor_from_sink",
    # Loads
    "calculate_static_load_split_tricycle",
    "calculate_static_load_split_taildragger",
    "calculate_dynamic_load_factor",
    "calculate_tire_load_requirements",
    "estimate_gear_positions_tricycle",
    "estimate_gear_positions_taildragger",
    "calculate_main_load_per_wheel",
    "LoadSplit",
    # Geometry
    "estimate_fuselage_length",
    "calculate_track_range",
    "calculate_wheelbase_range",
    "calculate_strut_length_range",
    "estimate_cg_height",
    "check_tip_back_margin",
    "check_nose_over_margin",
    "check_ground_clearance",
    "check_lateral_rollover",
    "estimate_tire_diameter",
    "SafetyCheckResult",
    # Tire catalog
    "find_matching_tires",
    "estimate_tire_dimensions",
    "TIRE_CATALOG",
]
