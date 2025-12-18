"""
Output models for landing gear recommendations.

These models define the structure of gear concept suggestions returned
by the recommender. This is for CONCEPTUAL SIZING ONLY - not certification.
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


class CatalogTire(BaseModel):
    """A tire from the internal catalog."""
    name: str = Field(..., description="Tire designation/name")
    diameter_m: float = Field(..., description="Tire outer diameter in meters")
    width_m: float = Field(..., description="Tire width in meters")
    max_load_N: float = Field(..., description="Maximum rated load in Newtons")
    max_pressure_kpa: Optional[float] = Field(default=None, description="Max inflation pressure in kPa")


class PDFMatchedTire(BaseModel):
    """A tire matched from PDF catalog with scoring details."""
    size: str = Field(..., description="Tire size designation")
    ply_rating: Optional[str] = Field(default=None, description="Ply rating")
    rated_load_lbs: float = Field(..., description="Rated load capacity in lbs")
    rated_inflation_psi: Optional[float] = Field(default=None, description="Rated inflation in psi")
    outside_diameter_in: Optional[float] = Field(default=None, description="Outside diameter in inches")
    section_width_in: Optional[float] = Field(default=None, description="Section width in inches")
    margin_load: float = Field(..., description="Load margin as fraction")
    score: float = Field(..., ge=0, le=1, description="Match score")
    reasons: list[str] = Field(default_factory=list, description="Selection reasons")


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
    recommended_tire_width_range_m: Optional[GeometryRange] = Field(
        default=None,
        description="Suggested tire width range (especially for soft field)"
    )
    matched_catalog_tires: Optional[list[CatalogTire]] = Field(
        default=None,
        description="Matching tires from internal catalog (if available)"
    )
    # PDF-based tire matches (from Goodyear catalog)
    matched_main_tires: Optional[list[PDFMatchedTire]] = Field(
        default=None,
        description="Main wheel tires matched from PDF catalog"
    )
    matched_nose_or_tail_tires: Optional[list[PDFMatchedTire]] = Field(
        default=None,
        description="Nose/tail wheel tires matched from PDF catalog"
    )
    tire_selection_notes: Optional[list[str]] = Field(
        default=None,
        description="Notes about tire selection from PDF catalog"
    )
    tire_selection_warnings: Optional[list[str]] = Field(
        default=None,
        description="Warnings about tire selection (including verification disclaimer)"
    )


class Loads(BaseModel):
    """
    Load calculations for the gear configuration.
    
    All loads in Newtons, energy in Joules.
    """
    weight_N: float = Field(
        ...,
        ge=0,
        description="Aircraft weight at landing (MLW) in Newtons"
    )
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
        description="Kinetic energy to be absorbed at touchdown (0.5*m*v^2)"
    )
    required_avg_force_N: float = Field(
        ..., 
        ge=0,
        description="Average force required during shock absorption (E/stroke)"
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


class CGSensitivity(BaseModel):
    """Summary of CG range sensitivity analysis."""
    pass_rate: float = Field(..., ge=0, le=1, description="Fraction of CG positions passing all checks")
    worst_case_position: str = Field(..., description="CG position with worst margins (fwd/mid/aft)")
    critical_check: Optional[str] = Field(default=None, description="Check most sensitive to CG")


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
    rollover_angle_deg: Optional[float] = Field(
        default=None,
        description="Computed rollover angle in degrees"
    )
    prop_clearance_margin_m: Optional[float] = Field(
        default=None,
        description="Margin above prop clearance requirement"
    )
    cg_range_sensitivity: Optional[CGSensitivity] = Field(
        default=None,
        description="Summary of how checks vary across CG range"
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
    This is for CONCEPTUAL SIZING ONLY - not for certification.
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
    
    # Assumptions used for this concept
    assumptions: list[str] = Field(
        default_factory=list,
        description="Key assumptions used in generating this concept"
    )
    
    # Input summary (normalized key inputs used)
    input_summary: dict[str, float | str] = Field(
        default_factory=dict,
        description="Summary of key input parameters used"
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


class SweepPoint(BaseModel):
    """Result for a single sweep point."""
    sink_rate_mps: float = Field(..., description="Sink rate at this point")
    cg_position_m: float = Field(..., description="CG position at this point")
    cg_label: str = Field(..., description="CG position label (fwd/mid/aft)")
    all_checks_passed: bool = Field(..., description="Whether all checks passed")
    score: float = Field(..., ge=0, le=1, description="Score at this point")
    failed_checks: list[str] = Field(default_factory=list, description="Names of failed checks")


class ConceptSweepResult(BaseModel):
    """Sweep results for a single concept."""
    config: GearConfig = Field(..., description="Gear configuration")
    gear_type: GearType = Field(..., description="Fixed or retractable")
    pass_rate: float = Field(..., ge=0, le=1, description="Fraction of points passing all checks")
    avg_score: float = Field(..., ge=0, le=1, description="Average score across sweep")
    worst_case_score: float = Field(..., ge=0, le=1, description="Worst score in sweep")
    best_case_score: float = Field(..., ge=0, le=1, description="Best score in sweep")
    sweep_points: list[SweepPoint] = Field(..., description="Individual sweep point results")


class SweepResult(BaseModel):
    """Complete sweep analysis result."""
    aircraft_name: str = Field(..., description="Input aircraft name")
    sink_rates_swept: list[float] = Field(..., description="Sink rates evaluated")
    cg_positions_swept: list[float] = Field(..., description="CG positions evaluated")
    concept_results: list[ConceptSweepResult] = Field(..., description="Results per concept")
    most_robust_concept: str = Field(..., description="Concept with highest pass rate")
    warnings: list[str] = Field(default_factory=list, description="Any warnings")
