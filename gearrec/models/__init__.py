"""
Pydantic models for landing gear recommender inputs and outputs.
"""

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import (
    GearConcept,
    GearConfig,
    GearType,
    GeometryRange,
    Geometry,
    TireSuggestion,
    CatalogTire,
    Loads,
    CheckResult,
    CGSensitivity,
    Checks,
    ScoreBreakdown,
    RecommendationResult,
    SweepPoint,
    ConceptSweepResult,
    SweepResult,
)

__all__ = [
    "AircraftInputs",
    "RunwayType",
    "DesignPriorities",
    "GearConcept",
    "GearConfig",
    "GearType",
    "GeometryRange",
    "Geometry",
    "TireSuggestion",
    "CatalogTire",
    "Loads",
    "CheckResult",
    "CGSensitivity",
    "Checks",
    "ScoreBreakdown",
    "RecommendationResult",
    "SweepPoint",
    "ConceptSweepResult",
    "SweepResult",
]
