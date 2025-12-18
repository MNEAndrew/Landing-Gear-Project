"""
Pydantic models for tire catalog data.

Models for storing parsed tire specifications from Goodyear PDFs
and matched tire results.
"""

from typing import Optional
from pydantic import BaseModel, Field


class TireSpec(BaseModel):
    """
    Tire specification from Goodyear Data Section PDF.
    
    Contains rated load, inflation, dimensions, and other specifications
    parsed from the Three-Part Tire Specifications table.
    """
    source: str = Field(default="goodyear_2022", description="Data source identifier")
    size: str = Field(..., description="Tire size designation, e.g. '24x7.25-10'")
    ply_rating: Optional[str] = Field(default=None, description="Ply rating, e.g. '6', '8', '10'")
    tt_tl: Optional[str] = Field(default=None, description="Tube type: 'TT' (tube) or 'TL' (tubeless)")
    rated_speed_mph: Optional[float] = Field(default=None, description="Rated speed in mph")
    rated_load_lbs: float = Field(..., description="Rated load capacity in lbs")
    rated_inflation_psi: Optional[float] = Field(default=None, description="Rated inflation pressure in psi")
    max_braking_load_lbs: Optional[float] = Field(default=None, description="Maximum braking load in lbs")
    max_bottoming_load_lbs: Optional[float] = Field(default=None, description="Maximum bottoming load in lbs")
    outside_diameter_in: Optional[float] = Field(default=None, description="Outside diameter in inches")
    section_width_in: Optional[float] = Field(default=None, description="Section width in inches")
    static_loaded_radius_in: Optional[float] = Field(default=None, description="Static loaded radius in inches")
    rim_size: Optional[str] = Field(default=None, description="Rim size designation")
    part_number: Optional[str] = Field(default=None, description="Goodyear part number")
    tread_design: Optional[str] = Field(default=None, description="Tread design name")
    raw_line: Optional[str] = Field(default=None, description="Original parsed line for traceability")
    page: Optional[int] = Field(default=None, description="PDF page number")
    
    @property
    def rated_load_N(self) -> float:
        """Rated load converted to Newtons."""
        return self.rated_load_lbs * 4.44822
    
    @property
    def outside_diameter_m(self) -> Optional[float]:
        """Outside diameter converted to meters."""
        if self.outside_diameter_in is not None:
            return self.outside_diameter_in * 0.0254
        return None
    
    @property
    def section_width_m(self) -> Optional[float]:
        """Section width converted to meters."""
        if self.section_width_in is not None:
            return self.section_width_in * 0.0254
        return None


class ApplicationRow(BaseModel):
    """
    Application chart row from Goodyear Application Charts PDF.
    
    Maps aircraft models to their recommended tire sizes.
    """
    manufacturer: Optional[str] = Field(default=None, description="Aircraft manufacturer")
    model: str = Field(..., description="Aircraft model designation")
    main_tire_size: Optional[str] = Field(default=None, description="Main gear tire size")
    aux_tire_size: Optional[str] = Field(default=None, description="Nose/tail wheel tire size")
    main_ply: Optional[str] = Field(default=None, description="Main tire ply rating")
    aux_ply: Optional[str] = Field(default=None, description="Auxiliary tire ply rating")
    code: Optional[str] = Field(default=None, description="TT/TL codes or other notes")
    page: Optional[int] = Field(default=None, description="PDF page number")
    raw_line: Optional[str] = Field(default=None, description="Original parsed line for traceability")


class MatchedTire(BaseModel):
    """
    A tire matched to a gear concept with scoring details.
    
    Contains the tire specification, load margins, and reasons for selection.
    """
    tire: TireSpec = Field(..., description="The matched tire specification")
    margin_load: float = Field(
        ..., 
        description="Load margin: (rated_load - required_load) / required_load"
    )
    required_dynamic_load_lbs: float = Field(
        ..., 
        description="Required dynamic load for this wheel position (lbs)"
    )
    required_static_load_lbs: float = Field(
        ..., 
        description="Required static load for this wheel position (lbs)"
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for this tire selection"
    )
    score: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Overall match score (0-1, higher is better)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "tire": {
                    "source": "goodyear_2022",
                    "size": "6.00-6",
                    "ply_rating": "6",
                    "rated_load_lbs": 1800,
                    "rated_inflation_psi": 55,
                },
                "margin_load": 0.25,
                "required_dynamic_load_lbs": 1440,
                "required_static_load_lbs": 1100,
                "reasons": ["Load capacity adequate", "Common GA size"],
                "score": 0.85,
            }
        }
    }


class TireMatchResult(BaseModel):
    """
    Complete tire matching result for a gear concept.
    
    Contains matched tires for both main and nose/tail positions,
    plus notes and warnings.
    """
    main: list[MatchedTire] = Field(
        default_factory=list,
        description="Top matched tires for main wheels"
    )
    nose_or_tail: list[MatchedTire] = Field(
        default_factory=list,
        description="Top matched tires for nose/tail wheel"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Informational notes about tire selection"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about tire selection"
    )

