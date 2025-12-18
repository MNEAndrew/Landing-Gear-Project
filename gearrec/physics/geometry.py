"""
Geometry heuristics and safety checks for landing gear.

Provides estimation functions for:
- Fuselage length from weight
- Track and wheelbase ranges
- Strut length estimates
- CG height estimation
- Tip-back and nose-over safety checks

ASSUMPTIONS:
- Empirical correlations based on GA aircraft data
- Simplified geometry (no detailed structural modeling)
- Conservative safety margins for conceptual design
"""

import math
from dataclasses import dataclass
from gearrec.physics.units import G_STANDARD


@dataclass
class SafetyCheckResult:
    """Result of a safety margin check."""
    passed: bool
    margin_value: float  # Actual margin achieved
    required_margin: float  # Minimum required margin
    description: str


def estimate_fuselage_length(
    mtow_kg: float,
    k_factor: float = 0.85,
) -> float:
    """
    Estimate fuselage length from MTOW.
    
    Uses empirical correlation: L ≈ k * MTOW^(1/3)
    
    Args:
        mtow_kg: Maximum takeoff weight in kg
        k_factor: Scaling factor (0.7-1.0 typical for GA)
                  - 0.7-0.8: Compact designs (Cirrus, DA40)
                  - 0.85-0.95: Traditional GA (Cessna 172, PA-28)
                  - 0.95-1.1: Larger/longer aircraft
                  
    Returns:
        Estimated fuselage length in meters
        
    Typical Results:
        - 1000 kg MTOW → ~8.5 m
        - 1500 kg MTOW → ~9.7 m
        - 2500 kg MTOW → ~11.5 m
        
    Notes:
        - This is a rough estimate for initial sizing
        - Actual length depends heavily on configuration
    """
    return k_factor * (mtow_kg ** (1/3))


def calculate_track_range(
    fuselage_length_m: float,
    runway_type: str = "paved",
    wing_low: bool = False,
) -> tuple[float, float]:
    """
    Calculate recommended track width range.
    
    Track is the lateral distance between main gear wheels.
    
    Args:
        fuselage_length_m: Estimated fuselage length
        runway_type: paved, grass, or gravel
        wing_low: Whether aircraft is low-wing configuration
        
    Returns:
        Tuple of (min_track_m, max_track_m)
        
    Heuristics:
        - Base: 0.18-0.28 * fuselage length
        - Soft field: wider track for stability (+10-20%)
        - Low wing: may need wider for tip clearance (+5-15%)
        - Rollover limit: track ≥ 2 * CG height * tan(rollover_angle)
    """
    # Base ratio from empirical data
    base_min_ratio = 0.18
    base_max_ratio = 0.28
    
    # Runway adjustment
    runway_factors = {
        "paved": 1.0,
        "grass": 1.15,  # Wider for soft-field stability
        "gravel": 1.20,
    }
    runway_factor = runway_factors.get(runway_type, 1.0)
    
    # Low-wing adjustment (more tip clearance concern)
    wing_factor = 1.10 if wing_low else 1.0
    
    min_track = fuselage_length_m * base_min_ratio * runway_factor * wing_factor
    max_track = fuselage_length_m * base_max_ratio * runway_factor * wing_factor
    
    # Clamp to practical limits
    min_track = max(1.5, min_track)  # At least 1.5m for small aircraft
    max_track = min(6.0, max_track)  # Practical limit for GA
    
    return (min_track, max_track)


def calculate_wheelbase_range(
    fuselage_length_m: float,
    config: str = "tricycle",
) -> tuple[float, float]:
    """
    Calculate recommended wheelbase range.
    
    Wheelbase is the longitudinal distance between nose/tail and main gear.
    
    Args:
        fuselage_length_m: Estimated fuselage length
        config: "tricycle" or "taildragger"
        
    Returns:
        Tuple of (min_wheelbase_m, max_wheelbase_m)
        
    Heuristics:
        - Tricycle: 0.25-0.35 * fuselage length
        - Taildragger: 0.55-0.75 * fuselage length (longer due to tail position)
    """
    if config == "taildragger":
        # Taildraggers have main gear forward, long distance to tail
        min_ratio = 0.55
        max_ratio = 0.75
    else:
        # Tricycle has more compact wheelbase
        min_ratio = 0.25
        max_ratio = 0.38
    
    min_wheelbase = fuselage_length_m * min_ratio
    max_wheelbase = fuselage_length_m * max_ratio
    
    # Clamp to practical limits
    if config == "taildragger":
        min_wheelbase = max(4.0, min_wheelbase)
        max_wheelbase = min(10.0, max_wheelbase)
    else:
        min_wheelbase = max(2.0, min_wheelbase)
        max_wheelbase = min(6.0, max_wheelbase)
    
    return (min_wheelbase, max_wheelbase)


def calculate_strut_length_range(
    mtow_kg: float,
    prop_clearance_m: float = 0.0,
    is_main_gear: bool = True,
) -> tuple[float, float]:
    """
    Calculate strut length range (attachment to axle).
    
    Args:
        mtow_kg: Maximum takeoff weight
        prop_clearance_m: Required propeller clearance
        is_main_gear: True for main gear, False for nose/tail
        
    Returns:
        Tuple of (min_strut_m, max_strut_m)
        
    Heuristics:
        - Light GA (<1500 kg): 0.35-0.55 m main strut
        - Medium GA (1500-3000 kg): 0.45-0.70 m
        - Nose/tail struts typically 70-90% of main strut
        - Add prop clearance requirement
    """
    # Base strut length from weight correlation
    if mtow_kg < 1000:
        base_min, base_max = 0.30, 0.45
    elif mtow_kg < 1500:
        base_min, base_max = 0.35, 0.55
    elif mtow_kg < 2500:
        base_min, base_max = 0.45, 0.65
    elif mtow_kg < 4000:
        base_min, base_max = 0.50, 0.75
    else:
        base_min, base_max = 0.60, 0.90
    
    # Adjust for gear type
    if not is_main_gear:
        base_min *= 0.75
        base_max *= 0.85
    
    # Add propeller clearance (main gear determines ground height)
    if is_main_gear and prop_clearance_m > 0:
        base_min = max(base_min, prop_clearance_m + 0.15)
        base_max = max(base_max, prop_clearance_m + 0.30)
    
    return (base_min, base_max)


def estimate_cg_height(
    mtow_kg: float,
    wing_low: bool = False,
) -> float:
    """
    Estimate CG height above ground in static position.
    
    Args:
        mtow_kg: Maximum takeoff weight
        wing_low: Whether aircraft is low-wing configuration
        
    Returns:
        Estimated CG height in meters
        
    Heuristics:
        - CG height scales roughly with aircraft size
        - Low-wing: CG higher relative to gear (engine/fuselage above wing)
        - High-wing: CG lower (closer to gear)
    """
    # Base height from weight correlation
    # Light aircraft: ~1.0-1.3m, heavier: ~1.2-1.8m
    base_height = 0.8 + 0.15 * (mtow_kg / 1000) ** 0.5
    
    # Wing position adjustment
    if wing_low:
        base_height *= 1.1  # CG higher relative to ground
    else:
        base_height *= 0.95  # High wing lowers CG
    
    # Clamp to reasonable range
    return max(0.8, min(2.5, base_height))


def check_tip_back_margin(
    x_cg_aft: float,
    x_main: float,
    wheelbase: float,
    cg_height: float,
    min_margin_ratio: float = 0.15,
) -> SafetyCheckResult:
    """
    Check tip-back margin for tricycle gear.
    
    Aircraft should not tip backward onto tail when at aft CG.
    
    Args:
        x_cg_aft: Aft CG position (most critical)
        x_main: Main gear position
        wheelbase: Distance from nose to main gear
        cg_height: CG height above ground
        min_margin_ratio: Minimum margin as fraction of wheelbase
        
    Returns:
        SafetyCheckResult with pass/fail and margin
        
    Check:
        - CG must be forward of main gear by at least margin
        - margin = (x_main - x_cg) / wheelbase
        - Should be > 0.15 (15% of wheelbase) typically
        
    Physics:
        - If CG is at or behind main gear, aircraft tips back
        - Margin provides stability against tail strikes
    """
    # Distance from aft CG to main gear (positive = CG forward of main)
    cg_to_main = x_main - x_cg_aft
    
    # Margin as fraction of wheelbase
    margin = cg_to_main / wheelbase if wheelbase > 0 else 0
    
    passed = margin >= min_margin_ratio
    
    description = (
        f"CG is {cg_to_main:.3f}m forward of main gear "
        f"({margin*100:.1f}% of wheelbase). "
        f"Minimum: {min_margin_ratio*100:.1f}%"
    )
    
    return SafetyCheckResult(
        passed=passed,
        margin_value=margin,
        required_margin=min_margin_ratio,
        description=description,
    )


def check_nose_over_margin(
    x_cg_fwd: float,
    x_main: float,
    x_nose: float,
    cg_height: float,
    braking_decel_g: float = 0.4,
    min_margin_ratio: float = 0.08,
) -> SafetyCheckResult:
    """
    Check nose-over margin under braking.
    
    Aircraft should not flip forward over nose gear during hard braking.
    
    Args:
        x_cg_fwd: Forward CG position (most critical for nose-over)
        x_main: Main gear position  
        x_nose: Nose gear position
        cg_height: CG height above ground
        braking_decel_g: Assumed braking deceleration in g's
        min_margin_ratio: Minimum acceptable margin ratio
        
    Returns:
        SafetyCheckResult with pass/fail and margin
        
    Physics:
        - Braking creates forward inertia force at CG
        - This creates nose-down moment
        - If moment exceeds stability, aircraft noses over
        
    Check:
        Moment balance about nose gear:
        - Stabilizing: W * (x_nose - x_cg)
        - Destabilizing: braking_force * cg_height = W * a/g * h
        
        For no nose-over:
        (x_cg - x_nose) > a/g * h
        margin = (x_cg - x_nose) - a/g * h
    """
    g = G_STANDARD.magnitude
    
    # Distance from nose gear to forward CG (positive = CG aft of nose)
    cg_to_nose = x_cg_fwd - x_nose
    
    # Critical distance: braking decel creates forward pitching moment
    # Need CG far enough aft that moment arm overcomes this
    critical_distance = braking_decel_g * cg_height
    
    # Available margin
    available = cg_to_nose
    required = critical_distance * (1 + min_margin_ratio)  # Add safety margin
    
    # Margin ratio
    margin_ratio = (available - critical_distance) / cg_to_nose if cg_to_nose > 0 else 0
    
    passed = available >= required
    
    description = (
        f"CG is {cg_to_nose:.3f}m aft of nose gear. "
        f"Under {braking_decel_g}g braking with CG at {cg_height:.2f}m height, "
        f"critical arm is {critical_distance:.3f}m. "
        f"Margin: {margin_ratio*100:.1f}%"
    )
    
    return SafetyCheckResult(
        passed=passed,
        margin_value=margin_ratio,
        required_margin=min_margin_ratio,
        description=description,
    )


def check_ground_clearance(
    strut_length_m: float,
    stroke_m: float,
    tire_radius_m: float,
    prop_clearance_required_m: float,
    static_deflection_fraction: float = 0.3,
) -> SafetyCheckResult:
    """
    Check propeller/structure ground clearance.
    
    Args:
        strut_length_m: Main gear strut length
        stroke_m: Shock absorber stroke
        tire_radius_m: Tire radius (half of diameter)
        prop_clearance_required_m: Required propeller clearance
        static_deflection_fraction: Fraction of stroke used statically
        
    Returns:
        SafetyCheckResult with pass/fail
        
    Calculation:
        - Ground height = strut + tire_radius - static_deflection
        - Must exceed prop_clearance requirement
    """
    # Static gear position (some stroke used under weight)
    static_deflection = stroke_m * static_deflection_fraction
    
    # Height of attachment point above ground
    ground_height = strut_length_m + tire_radius_m - static_deflection
    
    margin = ground_height - prop_clearance_required_m
    margin_ratio = margin / ground_height if ground_height > 0 else 0
    
    passed = margin >= 0
    
    description = (
        f"Ground clearance: {ground_height:.3f}m. "
        f"Required prop clearance: {prop_clearance_required_m:.3f}m. "
        f"Margin: {margin:.3f}m ({margin_ratio*100:.1f}%)"
    )
    
    return SafetyCheckResult(
        passed=passed,
        margin_value=margin_ratio,
        required_margin=0.0,
        description=description,
    )


def check_lateral_rollover(
    track_m: float,
    cg_height_m: float,
    min_rollover_angle_deg: float = 25.0,
) -> SafetyCheckResult:
    """
    Check lateral rollover resistance.
    
    Args:
        track_m: Track width (distance between main gear wheels)
        cg_height_m: CG height above ground
        min_rollover_angle_deg: Minimum required rollover angle
        
    Returns:
        SafetyCheckResult with pass/fail
        
    Physics:
        - Rollover angle = atan(track/2 / cg_height)
        - Higher angle = more stable
        - Military: >25°, GA: >20° typically
    """
    half_track = track_m / 2
    
    # Rollover angle
    rollover_angle_rad = math.atan2(half_track, cg_height_m)
    rollover_angle_deg = math.degrees(rollover_angle_rad)
    
    passed = rollover_angle_deg >= min_rollover_angle_deg
    
    description = (
        f"Rollover angle: {rollover_angle_deg:.1f}°. "
        f"Minimum required: {min_rollover_angle_deg:.1f}°. "
        f"Track: {track_m:.2f}m, CG height: {cg_height_m:.2f}m"
    )
    
    return SafetyCheckResult(
        passed=passed,
        margin_value=rollover_angle_deg,
        required_margin=min_rollover_angle_deg,
        description=description,
    )


def estimate_tire_diameter(
    load_per_tire_N: float,
    runway_type: str = "paved",
    tire_pressure_limit_kpa: float | None = None,
) -> tuple[float, float]:
    """
    Estimate tire diameter range based on load and conditions.
    
    Args:
        load_per_tire_N: Static load per tire in Newtons
        runway_type: paved, grass, or gravel
        tire_pressure_limit_kpa: Maximum tire pressure constraint
        
    Returns:
        Tuple of (min_diameter_m, max_diameter_m)
        
    Heuristics:
        - Light loads (<5000N): 0.30-0.40m diameter
        - Medium loads (5000-15000N): 0.35-0.50m
        - Heavy loads (>15000N): 0.45-0.65m
        - Soft field: larger tires (lower pressure)
    """
    # Base diameter from load
    if load_per_tire_N < 3000:
        base_min, base_max = 0.25, 0.35
    elif load_per_tire_N < 5000:
        base_min, base_max = 0.30, 0.40
    elif load_per_tire_N < 10000:
        base_min, base_max = 0.35, 0.50
    elif load_per_tire_N < 20000:
        base_min, base_max = 0.45, 0.60
    else:
        base_min, base_max = 0.55, 0.75
    
    # Runway adjustment (soft field = larger tires)
    runway_factors = {
        "paved": 1.0,
        "grass": 1.20,
        "gravel": 1.15,
    }
    factor = runway_factors.get(runway_type, 1.0)
    
    # Pressure limit adjustment
    # Lower pressure = need larger contact patch = larger tire
    if tire_pressure_limit_kpa is not None:
        if tire_pressure_limit_kpa < 200:  # Very low pressure
            factor *= 1.25
        elif tire_pressure_limit_kpa < 350:  # Low pressure
            factor *= 1.10
    
    return (base_min * factor, base_max * factor)

