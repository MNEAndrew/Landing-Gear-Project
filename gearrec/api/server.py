"""
FastAPI server for landing gear recommender.

Provides REST API endpoints for:
- POST /recommend - Generate gear recommendations
- GET /example - Get example input
- GET /health - Health check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import RecommendationResult
from gearrec.generator.candidates import GearGenerator

# Create FastAPI app
app = FastAPI(
    title="Landing Gear Recommender API",
    description="""
    Conceptual sizing tool for aircraft landing gear.
    
    **WARNING**: This tool provides rough conceptual estimates only.
    Not for certification or detailed design purposes.
    
    ## Features
    
    - Generates 3-6 candidate gear configurations
    - Supports tricycle and taildragger layouts
    - Fixed and retractable gear options
    - Considers runway type (paved, grass, gravel)
    - Configurable design priorities
    
    ## Usage
    
    1. POST your aircraft parameters to `/recommend`
    2. Receive JSON with ranked gear concepts
    3. Review geometry ranges, loads, and safety checks
    """,
    version="0.1.0",
    contact={
        "name": "Landing Gear Project",
    },
    license_info={
        "name": "MIT",
    },
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to docs."""
    return {"message": "Landing Gear Recommender API", "docs": "/docs"}


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check endpoint",
)
async def health_check():
    """
    Check if the API is running and healthy.
    
    Returns:
        Health status and version information
    """
    return HealthResponse(status="healthy", version="0.1.0")


@app.get(
    "/example",
    response_model=AircraftInputs,
    tags=["Reference"],
    summary="Get example input parameters",
)
async def get_example():
    """
    Get an example input configuration.
    
    Returns a sample AircraftInputs object with typical GA aircraft
    parameters that can be modified and used with /recommend.
    
    Returns:
        Example AircraftInputs with all fields populated
    """
    return AircraftInputs(
        aircraft_name="GA-2024 Trainer",
        mtow_kg=1200.0,
        mlw_kg=1140.0,
        cg_fwd_m=2.10,
        cg_aft_m=2.45,
        main_gear_attach_guess_m=2.55,
        nose_gear_attach_guess_m=0.80,
        landing_speed_mps=28.0,
        sink_rate_mps=2.0,
        runway=RunwayType.PAVED,
        retractable=False,
        prop_clearance_m=0.25,
        wing_low=True,
        tire_pressure_limit_kpa=None,
        max_gear_mass_kg=None,
        design_priorities=DesignPriorities(
            robustness=1.0,
            low_drag=0.5,
            low_mass=1.0,
            simplicity=1.5,
        ),
    )


@app.post(
    "/recommend",
    response_model=RecommendationResult,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["Recommendations"],
    summary="Generate landing gear recommendations",
)
async def recommend(inputs: AircraftInputs):
    """
    Generate landing gear recommendations for the given aircraft.
    
    Takes aircraft parameters and returns 3-6 candidate gear configurations
    ranked by score. Each concept includes:
    
    - Configuration (tricycle/taildragger) and type (fixed/retractable)
    - Geometry ranges (track, wheelbase, strut lengths, stroke)
    - Tire sizing suggestions
    - Load calculations (static and dynamic)
    - Safety check results
    - Score breakdown and explanation
    
    **Input Parameters:**
    
    - `aircraft_name`: Identifier for the aircraft
    - `mtow_kg`: Maximum takeoff weight in kg
    - `mlw_kg`: Maximum landing weight (defaults to 0.95*MTOW)
    - `cg_fwd_m`, `cg_aft_m`: CG envelope limits from datum
    - `landing_speed_mps`: Landing approach speed
    - `sink_rate_mps`: Vertical touchdown rate (default 2.0 m/s)
    - `runway`: Primary runway type (paved/grass/gravel)
    - `retractable`: Whether retractable gear is required
    - `prop_clearance_m`: Required propeller clearance
    - `design_priorities`: Weights for robustness/drag/mass/simplicity
    
    **Returns:**
    
    RecommendationResult containing:
    - List of 3-6 GearConcept objects
    - Key assumptions used
    - Any warnings about the configuration
    """
    try:
        generator = GearGenerator(inputs)
        result = generator.generate_result()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get(
    "/runway-types",
    tags=["Reference"],
    summary="List available runway types",
)
async def list_runway_types():
    """
    Get list of supported runway types.
    
    Returns:
        List of runway type enum values
    """
    return {
        "runway_types": [rt.value for rt in RunwayType],
        "descriptions": {
            "paved": "Hard-surfaced runway (asphalt, concrete)",
            "grass": "Natural grass surface, requires larger tires",
            "gravel": "Gravel or dirt surface, needs robust gear",
        }
    }


# Include schema examples in OpenAPI
app.openapi_tags = [
    {
        "name": "Recommendations",
        "description": "Generate landing gear recommendations",
    },
    {
        "name": "Reference",
        "description": "Reference data and examples",
    },
    {
        "name": "System",
        "description": "System health and status",
    },
]

