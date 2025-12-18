"""
Output models for landing gear recommendations.

These models define the structure of gear concept suggestions returned
by the recommender.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class GearConfig(str, Enum):
    """Landing gear configuration type."""
    TRICYCLE = "tricycle"
    TAILDRAGGER = "taildragger"


class GearType(str, Enum):
    """Landing gear retraction type."""
    FIXED = "fixed"
    RETRACTABLE = "retractable"


class GeometryRange(BaseModel):
    """A range of values for a geometry parameter."""
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")

    @property
    def mid(self) -> float:
        """Midpoint of the range."""
        return (self.min + self.max) / 2

    @property
    def span(self) -> float:
        """Size of the range."""
        return self.max - self.min


class Geometry(BaseModel):
    """
    Geometric parameters for landing gear layout.
    
    All dimensions in meters.
    """
    track_m: GeometryRange = Field(
        ..., 
        description="Distance between main gear wheels (left to right)"
    )
    wheelbase_m: GeometryRange = Field(
        ..., 
        description="Distance between nose/tail wheel and main gear"
    )
    main_strut_length_m: GeometryRange = Field(
        ..., 
        description="Length of main gear strut (attachment to axle)"
    )
    nose_or_tail_strut_length_m: GeometryRange = Field(
        ..., 
        description="Length of nose or tail wheel strut"
    )
    stroke_m: GeometryRange = Field(
        ..., 
        description="Shock absorber stroke (travel distance)"
    )


class TireSuggestion(BaseModel):
    """
    Tire sizing suggestions based on load requirements.
    
    These are rough estimates for initial tire selection.
    """
    required_static_load_per_wheel_N: float = Field(
        ..., 
        ge=0,
        description="Required static load capacity per main wheel (N)"
    )
    required_dynamic_load_per_wheel_N: float = Field(
        ..., 
        ge=0,
        description="Required dynamic load capacity per main wheel at touchdown (N)"
    )
    recommended_tire_diameter_range_m: GeometryRange = Field(
        ..., 
        description="Suggested tire diameter range based on load and runway"
    )
    suggested_tire_width_m: Optional[float] = Field(
        default=None,
        description="Suggested tire width for soft-field operations"
    )


class Loads(BaseModel):
    """
    Load calculations for the gear configuration.
    
    All loads in Newtons, energy in Joules.
    """
    static_nose_or_tail_load_N: float = Field(
        ..., 
        description="Static load on nose/tail wheel(s)"
    )
    static_main_load_total_N: float = Field(
        ..., 
        description="Total static load on main gear (both sides)"
    )
    static_main_load_per_wheel_N: float = Field(
        ..., 
        description="Static load per main wheel"
    )
    landing_energy_J: float = Field(
        ..., 
        ge=0,
        description="Kinetic energy to be absorbed at touchdown"
    )
    required_avg_force_N: float = Field(
        ..., 
        ge=0,
        description="Average force required during shock absorption"
    )
    nose_load_fraction: float = Field(
        ..., 
        ge=0,
        le=1,
        description="Fraction of weight on nose/tail wheel (should be ~0.08-0.15 for tricycle)"
    )


class CheckResult(BaseModel):
    """Result of a safety/stability check."""
    passed: bool = Field(..., description="Whether the check passed")
    value: float = Field(..., description="Computed margin or ratio")
    limit: float = Field(..., description="Required threshold")
    description: str = Field(default="", description="Explanation of the check")


class Checks(BaseModel):
    """
    Safety and stability checks for the gear configuration.
    """
    tip_back_margin: CheckResult = Field(
        ..., 
        description="Margin against tipping backward on tail (tricycle)"
    )
    nose_over_margin: CheckResult = Field(
        ..., 
        description="Margin against nosing over under braking"
    )
    ground_clearance_ok: bool = Field(
        ..., 
        description="Whether minimum ground clearances are met"
    )
    lateral_stability_ok: bool = Field(
        default=True,
        description="Whether track provides adequate rollover resistance"
    )
    prop_clearance_ok: bool = Field(
        default=True,
        description="Whether propeller clearance requirement is met"
    )


class ScoreBreakdown(BaseModel):
    """
    Breakdown of scoring components.
    
    Each score is 0.0 to 1.0, with 1.0 being best.
    """
    robustness: float = Field(..., ge=0, le=1, description="Score for robustness/reliability")
    low_drag: float = Field(..., ge=0, le=1, description="Score for aerodynamic efficiency")
    low_mass: float = Field(..., ge=0, le=1, description="Score for weight efficiency")
    simplicity: float = Field(..., ge=0, le=1, description="Score for design simplicity")
    checks_penalty: float = Field(
        default=0.0, 
        ge=0, 
        le=1, 
        description="Penalty applied for failed checks"
    )


class GearConcept(BaseModel):
    """
    A complete landing gear concept recommendation.
    
    Includes configuration, geometry, loads, safety checks, and scoring.
    """
    # Configuration
    config: GearConfig = Field(..., description="Tricycle or taildragger")
    gear_type: GearType = Field(..., description="Fixed or retractable")
    wheel_count_main: int = Field(
        ..., 
        ge=1, 
        le=4,
        description="Number of wheels per main gear leg (1=single, 2=dual)"
    )
    wheel_count_nose_or_tail: int = Field(
        ..., 
        ge=1, 
        le=2,
        description="Number of wheels on nose/tail gear"
    )
    
    # Geometry
    geometry: Geometry = Field(..., description="Geometric parameters")
    
    # Tire sizing
    tire_suggestion: TireSuggestion = Field(..., description="Tire sizing recommendations")
    
    # Loads
    loads: Loads = Field(..., description="Load calculations")
    
    # Safety checks
    checks: Checks = Field(..., description="Safety and stability checks")
    
    # Explanation
    explanation: list[str] = Field(
        ..., 
        description="Bullet points explaining design choices and fit"
    )
    
    # Scoring
    score: float = Field(..., ge=0, le=1, description="Overall weighted score (0-1)")
    score_breakdown: ScoreBreakdown = Field(..., description="Component scores")

    @property
    def all_checks_passed(self) -> bool:
        """Whether all safety checks passed."""
        return (
            self.checks.tip_back_margin.passed
            and self.checks.nose_over_margin.passed
            and self.checks.ground_clearance_ok
            and self.checks.lateral_stability_ok
            and self.checks.prop_clearance_ok
        )


class RecommendationResult(BaseModel):
    """
    Complete output of the gear recommendation process.
    """
    aircraft_name: str = Field(..., description="Input aircraft name")
    input_summary: dict = Field(..., description="Summary of key input parameters")
    concepts: list[GearConcept] = Field(
        ..., 
        min_length=1,
        max_length=10,
        description="List of recommended gear concepts (3-6 typical)"
    )
    assumptions: list[str] = Field(
        ..., 
        description="Key assumptions used in the analysis"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about inputs or results"
    )

    @property
    def best_concept(self) -> GearConcept:
        """Return the highest-scoring concept."""
        return max(self.concepts, key=lambda c: c.score)

    @property
    def passing_concepts(self) -> list[GearConcept]:
        """Return only concepts that pass all checks."""
        return [c for c in self.concepts if c.all_checks_passed]

