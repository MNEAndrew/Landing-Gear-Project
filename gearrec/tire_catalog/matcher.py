"""
Tire matching logic.

Selects appropriate tires for landing gear concepts based on
load requirements, dimensional constraints, and runway type.

WARNING: This is for CONCEPTUAL SIZING ONLY, NOT certification.
"""

from typing import Optional

from gearrec.tire_catalog.models import TireSpec, ApplicationRow, MatchedTire, TireMatchResult
from gearrec.models.inputs import AircraftInputs, RunwayType
from gearrec.models.outputs import GearConcept


# Conversion constants
LBS_PER_N = 0.224809  # 1 Newton = 0.224809 lbs
N_PER_LBS = 4.44822   # 1 lb = 4.44822 Newtons
KPA_TO_PSI = 0.145038  # 1 kPa = 0.145038 psi


def n_to_lbf(newtons: float) -> float:
    """Convert Newtons to pounds-force."""
    return newtons * LBS_PER_N


def lbf_to_n(lbf: float) -> float:
    """Convert pounds-force to Newtons."""
    return lbf * N_PER_LBS


def kpa_to_psi(kpa: float) -> float:
    """Convert kPa to psi."""
    return kpa * KPA_TO_PSI


def in_to_m(inches: float) -> float:
    """Convert inches to meters."""
    return inches * 0.0254


def m_to_in(meters: float) -> float:
    """Convert meters to inches."""
    return meters / 0.0254


# Safety factors by runway type
SAFETY_FACTORS = {
    RunwayType.PAVED: 1.10,
    RunwayType.GRASS: 1.20,
    RunwayType.GRAVEL: 1.25,
}

# Warning that must be included with PDF-based tire selections
TIRE_SELECTION_WARNING = (
    "Application charts are general reference only; verify with airframe "
    "manufacturer and tire manufacturer before installing. This is conceptual "
    "sizing ONLY, NOT for certification."
)


def _score_tire_for_load(
    tire: TireSpec,
    required_load_lbs: float,
    safety_factor: float,
) -> tuple[float, float, list[str]]:
    """
    Score a tire based on load capacity.
    
    Returns:
        Tuple of (score, margin, reasons)
    """
    required_with_sf = required_load_lbs * safety_factor
    
    if tire.rated_load_lbs < required_with_sf:
        return 0.0, -1.0, ["Insufficient load capacity"]
    
    margin = (tire.rated_load_lbs - required_load_lbs) / required_load_lbs
    
    # Ideal margin is 15-40%. Too much margin means overbuilt/heavy.
    if 0.15 <= margin <= 0.40:
        score = 1.0
    elif 0.10 <= margin < 0.15:
        score = 0.9
    elif 0.40 < margin <= 0.60:
        score = 0.85
    elif margin < 0.10:
        score = 0.7  # Tight margin
    else:
        score = 0.6  # Overbuilt
    
    reasons = [f"Load margin: {margin*100:.0f}%"]
    return score, margin, reasons


def _score_tire_for_pressure(
    tire: TireSpec,
    pressure_limit_psi: Optional[float],
) -> tuple[float, list[str]]:
    """
    Score a tire based on pressure constraints.
    
    Returns:
        Tuple of (score, reasons)
    """
    if pressure_limit_psi is None:
        return 1.0, []
    
    if tire.rated_inflation_psi is None:
        return 0.8, ["Pressure data not available"]
    
    if tire.rated_inflation_psi > pressure_limit_psi:
        return 0.0, [f"Exceeds pressure limit ({tire.rated_inflation_psi} > {pressure_limit_psi} psi)"]
    
    return 1.0, ["Within pressure limits"]


def _score_tire_for_dimensions(
    tire: TireSpec,
    target_diameter_m: Optional[tuple[float, float]],
    target_width_m: Optional[tuple[float, float]],
    runway_type: RunwayType,
) -> tuple[float, list[str]]:
    """
    Score a tire based on dimensional fit.
    
    Args:
        tire: Tire to score
        target_diameter_m: (min, max) diameter range in meters
        target_width_m: (min, max) width range in meters  
        runway_type: Runway surface type
        
    Returns:
        Tuple of (score, reasons)
    """
    score = 1.0
    reasons = []
    
    # Check diameter
    if target_diameter_m and tire.outside_diameter_m is not None:
        diam_min, diam_max = target_diameter_m
        diam = tire.outside_diameter_m
        
        if diam_min <= diam <= diam_max:
            score *= 1.0
            reasons.append("Diameter within range")
        elif diam < diam_min:
            # Undersized - penalty depends on how much
            ratio = diam / diam_min
            score *= max(0.5, ratio)
            reasons.append("Diameter slightly undersized")
        else:
            # Oversized - less penalty for soft field
            if runway_type in (RunwayType.GRASS, RunwayType.GRAVEL):
                score *= 0.95  # Larger is often better for soft field
                reasons.append("Larger diameter good for soft field")
            else:
                ratio = diam_max / diam
                score *= max(0.7, ratio)
                reasons.append("Diameter oversized")
    
    # Check width
    if target_width_m and tire.section_width_m is not None:
        width_min, width_max = target_width_m
        width = tire.section_width_m
        
        if width_min <= width <= width_max:
            score *= 1.0
        elif width < width_min:
            # Narrow - bigger penalty for soft field
            ratio = width / width_min
            if runway_type in (RunwayType.GRASS, RunwayType.GRAVEL):
                score *= max(0.4, ratio * 0.8)
                reasons.append("Width too narrow for soft field")
            else:
                score *= max(0.6, ratio)
        else:
            # Wide - bonus for soft field
            if runway_type in (RunwayType.GRASS, RunwayType.GRAVEL):
                score *= 1.05  # Bonus for wider
                reasons.append("Wider tire good for soft field")
            else:
                score *= 0.9
    
    # Soft field bonus for larger OD and width
    if runway_type in (RunwayType.GRASS, RunwayType.GRAVEL):
        if tire.outside_diameter_in and tire.outside_diameter_in > 15:
            score *= 1.02
        if tire.section_width_in and tire.section_width_in > 6:
            score *= 1.02
    
    return min(1.0, score), reasons


def _score_tire_for_application(
    tire: TireSpec,
    aircraft_name: str,
    mtow_kg: float,
    applications: list[ApplicationRow],
    is_main: bool,
) -> tuple[float, list[str]]:
    """
    Score a tire based on application chart matches.
    
    Returns:
        Tuple of (score_bonus, reasons)
    """
    bonus = 0.0
    reasons = []
    
    if not applications:
        return 0.0, []
    
    aircraft_upper = aircraft_name.upper()
    tire_size = tire.size.upper()
    
    # Look for direct model match
    for app in applications:
        model_match = app.model.upper() in aircraft_upper or aircraft_upper in app.model.upper()
        
        if model_match:
            if is_main and app.main_tire_size:
                if app.main_tire_size.upper() == tire_size:
                    bonus = 0.15
                    reasons.append(f"Matches application chart for {app.model}")
                    return bonus, reasons
            elif not is_main and app.aux_tire_size:
                if app.aux_tire_size.upper() == tire_size:
                    bonus = 0.15
                    reasons.append(f"Matches application chart for {app.model}")
                    return bonus, reasons
    
    # Class-based heuristic for light GA
    if mtow_kg < 2000:
        common_ga_sizes = {'6.00-6', '5.00-5', '6.50-8', '7.00-6', '8.00-6'}
        if tire_size.replace('X', 'x') in common_ga_sizes or tire_size in common_ga_sizes:
            bonus = 0.03
            reasons.append("Common light GA size")
    
    return bonus, reasons


def match_tires(
    required_dynamic_load_lbs: float,
    required_static_load_lbs: float,
    tire_specs: list[TireSpec],
    runway_type: RunwayType,
    pressure_limit_psi: Optional[float] = None,
    target_diameter_m: Optional[tuple[float, float]] = None,
    target_width_m: Optional[tuple[float, float]] = None,
    aircraft_name: str = "",
    mtow_kg: float = 0,
    applications: Optional[list[ApplicationRow]] = None,
    is_main: bool = True,
    max_results: int = 5,
) -> list[MatchedTire]:
    """
    Match tires from catalog to requirements.
    
    Args:
        required_dynamic_load_lbs: Required dynamic load per wheel
        required_static_load_lbs: Required static load per wheel
        tire_specs: Available tire specifications
        runway_type: Primary runway surface
        pressure_limit_psi: Maximum tire pressure (optional)
        target_diameter_m: Target diameter range (min, max) in meters
        target_width_m: Target width range (min, max) in meters
        aircraft_name: Aircraft name for application matching
        mtow_kg: MTOW for class-based heuristics
        applications: Application chart data (optional)
        is_main: True for main wheels, False for nose/tail
        max_results: Maximum number of matches to return
        
    Returns:
        List of MatchedTire objects, sorted by score
    """
    safety_factor = SAFETY_FACTORS.get(runway_type, 1.10)
    matches = []
    
    for tire in tire_specs:
        # Score for load capacity
        load_score, margin, load_reasons = _score_tire_for_load(
            tire, required_dynamic_load_lbs, safety_factor
        )
        
        if load_score == 0:
            continue  # Skip tires that don't meet load requirements
        
        # Score for pressure
        pressure_score, pressure_reasons = _score_tire_for_pressure(
            tire, pressure_limit_psi
        )
        
        if pressure_score == 0:
            continue  # Skip tires that exceed pressure limit
        
        # Score for dimensions
        dim_score, dim_reasons = _score_tire_for_dimensions(
            tire, target_diameter_m, target_width_m, runway_type
        )
        
        # Application chart bonus
        app_bonus, app_reasons = _score_tire_for_application(
            tire, aircraft_name, mtow_kg, applications or [], is_main
        )
        
        # Combined score
        base_score = load_score * pressure_score * dim_score
        final_score = min(1.0, base_score + app_bonus)
        
        # Collect all reasons
        all_reasons = load_reasons + pressure_reasons + dim_reasons + app_reasons
        
        matches.append(MatchedTire(
            tire=tire,
            margin_load=margin,
            required_dynamic_load_lbs=required_dynamic_load_lbs,
            required_static_load_lbs=required_static_load_lbs,
            reasons=all_reasons,
            score=final_score,
        ))
    
    # Sort by score descending
    matches.sort(key=lambda m: m.score, reverse=True)
    
    return matches[:max_results]


def choose_tires_for_concept(
    concept: GearConcept,
    aircraft_input: AircraftInputs,
    tire_specs: list[TireSpec],
    applications: Optional[list[ApplicationRow]] = None,
) -> TireMatchResult:
    """
    Choose tires for a gear concept.
    
    Args:
        concept: The gear concept to match tires for
        aircraft_input: Aircraft input parameters
        tire_specs: Available tire specifications
        applications: Application chart data (optional)
        
    Returns:
        TireMatchResult with matched tires for main and nose/tail positions
    """
    notes = []
    warnings = [TIRE_SELECTION_WARNING]
    
    runway_type = aircraft_input.runway
    
    # Convert pressure limit if provided
    pressure_limit_psi = None
    if aircraft_input.tire_pressure_limit_kpa is not None:
        pressure_limit_psi = kpa_to_psi(aircraft_input.tire_pressure_limit_kpa)
        notes.append(f"Pressure limit: {pressure_limit_psi:.0f} psi")
    
    # Get dimensional targets from concept
    target_diam_m = None
    target_width_m = None
    
    if concept.tire_suggestion.recommended_tire_diameter_range_m:
        diam_range = concept.tire_suggestion.recommended_tire_diameter_range_m
        target_diam_m = (diam_range.min, diam_range.max)
    
    if concept.tire_suggestion.recommended_tire_width_range_m:
        width_range = concept.tire_suggestion.recommended_tire_width_range_m
        target_width_m = (width_range.min, width_range.max)
    
    # === Main wheel matching ===
    # Get required loads from concept
    static_main_per_wheel_N = concept.loads.static_main_load_per_wheel_N
    dynamic_main_per_wheel_N = concept.tire_suggestion.required_dynamic_load_per_wheel_N
    
    static_main_lbs = n_to_lbf(static_main_per_wheel_N)
    dynamic_main_lbs = n_to_lbf(dynamic_main_per_wheel_N)
    
    main_matches = match_tires(
        required_dynamic_load_lbs=dynamic_main_lbs,
        required_static_load_lbs=static_main_lbs,
        tire_specs=tire_specs,
        runway_type=runway_type,
        pressure_limit_psi=pressure_limit_psi,
        target_diameter_m=target_diam_m,
        target_width_m=target_width_m,
        aircraft_name=aircraft_input.aircraft_name,
        mtow_kg=aircraft_input.mtow_kg,
        applications=applications,
        is_main=True,
    )
    
    if not main_matches:
        warnings.append("No suitable main wheel tires found in catalog")
    else:
        notes.append(f"Found {len(main_matches)} main wheel tire options")
    
    # === Nose/tail wheel matching ===
    static_nose_N = concept.loads.static_nose_or_tail_load_N
    static_nose_lbs = n_to_lbf(static_nose_N)
    
    # Estimate dynamic nose load (conservative)
    # Use max of 1.5x static or static + 20% of main dynamic
    dynamic_nose_N = max(
        static_nose_N * 1.5,
        static_nose_N + 0.2 * dynamic_main_per_wheel_N
    )
    dynamic_nose_lbs = n_to_lbf(dynamic_nose_N)
    
    # Nose/tail tires are typically smaller
    nose_diam_target = None
    nose_width_target = None
    if target_diam_m:
        # Nose tires typically 60-80% of main diameter
        nose_diam_target = (target_diam_m[0] * 0.6, target_diam_m[1] * 0.85)
    if target_width_m:
        nose_width_target = (target_width_m[0] * 0.6, target_width_m[1] * 0.85)
    
    nose_matches = match_tires(
        required_dynamic_load_lbs=dynamic_nose_lbs,
        required_static_load_lbs=static_nose_lbs,
        tire_specs=tire_specs,
        runway_type=runway_type,
        pressure_limit_psi=pressure_limit_psi,
        target_diameter_m=nose_diam_target,
        target_width_m=nose_width_target,
        aircraft_name=aircraft_input.aircraft_name,
        mtow_kg=aircraft_input.mtow_kg,
        applications=applications,
        is_main=False,
    )
    
    if not nose_matches:
        warnings.append("No suitable nose/tail wheel tires found in catalog")
    else:
        notes.append(f"Found {len(nose_matches)} nose/tail wheel tire options")
    
    # Add runway-specific notes
    if runway_type == RunwayType.GRASS:
        notes.append("Grass runway: prefer wider tires with lower pressure")
    elif runway_type == RunwayType.GRAVEL:
        notes.append("Gravel runway: prefer robust tires with good FOD resistance")
    
    return TireMatchResult(
        main=main_matches,
        nose_or_tail=nose_matches,
        notes=notes,
        warnings=warnings,
    )

