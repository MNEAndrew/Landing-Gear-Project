"""
Landing Gear Recommender (gearrec)

A conceptual sizing tool for aircraft landing gear that generates candidate
configurations based on aircraft parameters.

WARNING: This tool provides rough conceptual estimates only. Not for certification
or detailed design purposes.

Usage:
    python -m gearrec make-example
    python -m gearrec recommend --input example_input.json
    python -m gearrec sweep --input example_input.json
    python -m gearrec serve --port 8000
"""

__version__ = "0.1.0"
__author__ = "Landing Gear Project"

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import (
    GearConcept,
    GearConfig,
    GearType,
    RecommendationResult,
    SweepResult,
)
from gearrec.generator.candidates import GearGenerator

__all__ = [
    "AircraftInputs",
    "RunwayType",
    "DesignPriorities",
    "GearConcept",
    "GearConfig",
    "GearType",
    "RecommendationResult",
    "SweepResult",
    "GearGenerator",
]
