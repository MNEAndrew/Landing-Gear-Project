"""
Input models for aircraft parameters.

These models define the aircraft characteristics needed for landing gear
conceptual sizing. This is for CONCEPTUAL SIZING ONLY - not certification.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class RunwayType(str, Enum):
    """Surface type for landing operations."""
    PAVED = "paved"
    GRASS = "grass"
    GRAVEL = "gravel"


class DesignPriorities(BaseModel):
    """
    Weights for design optimization priorities.
    
    All weights should be non-negative. They will be normalized internally.
    Higher weight = more important in the scoring function.
    """
    robustness: float = Field(default=1.0, ge=0.0, description="Weight for robust/reliable design")
    low_drag: float = Field(default=1.0, ge=0.0, description="Weight for aerodynamic efficiency")
    low_mass: float = Field(default=1.0, ge=0.0, description="Weight for lightweight design")
    simplicity: float = Field(default=1.0, ge=0.0, description="Weight for simple/maintainable design")

    def normalized(self) -> dict[str, float]:
        """Return normalized weights that sum to 1.0."""
        total = self.robustness + self.low_drag + self.low_mass + self.simplicity
        if total == 0:
            return {"robustness": 0.25, "low_drag": 0.25, "low_mass": 0.25, "simplicity": 0.25}
        return {
            "robustness": self.robustness / total,
            "low_drag": self.low_drag / total,
            "low_mass": self.low_mass / total,
            "simplicity": self.simplicity / total,
        }


class AircraftInputs(BaseModel):
    """
    Aircraft parameters for landing gear sizing.
    
    All distances are measured from a common datum (typically nose or firewall).
    Positive x is typically aft.
    
    This is for CONCEPTUAL SIZING ONLY - not for certification or detailed design.
    """
    
    # Aircraft identification
    aircraft_name: str = Field(..., description="Aircraft identifier/name")
    
    # Weight parameters
    mtow_kg: float = Field(..., gt=0, description="Maximum takeoff weight in kg")
    mlw_kg: Optional[float] = Field(
        default=None, 
        gt=0, 
        description="Maximum landing weight in kg. If not provided, assumes 0.95*MTOW"
    )
    
    # CG envelope (measured from datum)
    cg_fwd_m: float = Field(..., description="Forward CG limit from datum in meters")
    cg_aft_m: float = Field(..., description="Aft CG limit from datum in meters")
    cg_height_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="CG height above ground in static position (m). If None, estimated from MTOW."
    )
    
    # Geometry estimates (optional)
    fuselage_length_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="Fuselage length in meters. If None, estimated from MTOW."
    )
    
    # Optional gear position guesses (measured from datum)
    main_gear_attach_guess_m: Optional[float] = Field(
        default=None,
        description="Initial guess for main gear attachment point from datum (m)"
    )
    nose_gear_attach_guess_m: Optional[float] = Field(
        default=None,
        description="Initial guess for nose/tail gear attachment point from datum (m)"
    )
    
    # Performance parameters
    landing_speed_mps: float = Field(
        ..., 
        gt=0, 
        description="Landing approach speed in m/s (typically 1.3*Vs0)"
    )
    sink_rate_mps: float = Field(
        default=2.0, 
        gt=0, 
        le=5.0,
        description="Vertical touchdown rate in m/s. Default 2.0 m/s is typical for normal landings"
    )
    
    # Runway and environment
    runway: RunwayType = Field(
        default=RunwayType.PAVED,
        description="Primary runway surface type"
    )
    
    # Configuration flags
    retractable: bool = Field(
        default=False,
        description="Whether retractable gear is required"
    )
    prop_clearance_m: float = Field(
        default=0.0,
        ge=0,
        description="Required propeller ground clearance in m (0 for jets)"
    )
    wing_low: bool = Field(
        default=True,
        description="Low-wing configuration (affects wingtip clearance considerations)"
    )
    
    # Optional constraints
    tire_pressure_limit_kpa: Optional[float] = Field(
        default=None,
        gt=0,
        description="Maximum allowable tire pressure in kPa"
    )
    max_gear_mass_kg: Optional[float] = Field(
        default=None,
        gt=0,
        description="Maximum allowable gear system mass in kg"
    )
    
    # Performance constraints (optional)
    takeoff_distance_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="Required takeoff distance in meters"
    )
    landing_distance_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="Required landing distance in meters"
    )
    
    # Braking parameters
    brake_decel_g: float = Field(
        default=0.4,
        gt=0,
        le=1.0,
        description="Assumed braking deceleration in g's for nose-over check"
    )
    
    # Design optimization weights
    design_priorities: DesignPriorities = Field(
        default_factory=DesignPriorities,
        description="Weights for design optimization priorities"
    )

    @field_validator("cg_aft_m")
    @classmethod
    def validate_cg_range(cls, v: float, info) -> float:
        """Ensure aft CG is behind or at forward CG."""
        if "cg_fwd_m" in info.data and v < info.data["cg_fwd_m"]:
            raise ValueError("cg_aft_m must be >= cg_fwd_m (aft is typically larger x)")
        return v

    @model_validator(mode="after")
    def set_defaults(self) -> "AircraftInputs":
        """Set computed defaults for optional fields."""
        if self.mlw_kg is None:
            object.__setattr__(self, "mlw_kg", 0.95 * self.mtow_kg)
        return self

    @property
    def cg_mid_m(self) -> float:
        """Middle of CG range."""
        return (self.cg_fwd_m + self.cg_aft_m) / 2

    @property
    def cg_range_m(self) -> float:
        """Total CG travel range."""
        return self.cg_aft_m - self.cg_fwd_m

    def get_mlw_kg(self) -> float:
        """Get MLW, with fallback to 95% MTOW."""
        return self.mlw_kg if self.mlw_kg is not None else 0.95 * self.mtow_kg

    def get_fuselage_length_m(self, k_factor: float = 0.85) -> float:
        """
        Get fuselage length, estimating from MTOW if not provided.
        
        Estimation: L = k * MTOW^(1/3), clamped to [5, 25] m
        """
        if self.fuselage_length_m is not None:
            return self.fuselage_length_m
        length_est = k_factor * (self.mtow_kg ** (1/3))
        return max(5.0, min(25.0, length_est))

    def get_cg_height_m(self) -> float:
        """
        Get CG height, estimating from MTOW and wing position if not provided.
        
        Estimation based on typical GA aircraft correlations.
        """
        if self.cg_height_m is not None:
            return self.cg_height_m
        # Base height from weight correlation
        base_height = 0.8 + 0.15 * (self.mtow_kg / 1000) ** 0.5
        # Wing position adjustment
        if self.wing_low:
            base_height *= 1.1
        else:
            base_height *= 0.95
        return max(0.8, min(2.5, base_height))

    model_config = {
        "json_schema_extra": {
            "example": {
                "aircraft_name": "GA-2024",
                "mtow_kg": 1200,
                "mlw_kg": 1140,
                "cg_fwd_m": 2.0,
                "cg_aft_m": 2.4,
                "cg_height_m": 1.1,
                "fuselage_length_m": 8.5,
                "landing_speed_mps": 28,
                "sink_rate_mps": 2.0,
                "runway": "paved",
                "retractable": False,
                "prop_clearance_m": 0.25,
                "wing_low": True,
                "brake_decel_g": 0.4,
                "design_priorities": {
                    "robustness": 1.0,
                    "low_drag": 0.5,
                    "low_mass": 1.0,
                    "simplicity": 1.5
                }
            }
        }
    }
