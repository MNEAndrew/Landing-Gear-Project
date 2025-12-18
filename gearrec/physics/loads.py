"""
Load distribution calculations for landing gear.

Calculates static and dynamic loads on nose/main gear for different
configurations (tricycle, taildragger).

ASSUMPTIONS:
- Aircraft treated as rigid body for load distribution
- Ground reaction forces are vertical (no side loads in static case)
- CG position is the dominant factor in load split
- Dynamic loads use simplified factors, not full dynamic simulation
"""

from dataclasses import dataclass
from gearrec.physics.units import G_STANDARD


@dataclass
class LoadSplit:
    """Result of load split calculation."""
    nose_or_tail_load_N: float  # Load on nose wheel (tricycle) or tail wheel
    main_load_total_N: float    # Total load on main gear (both sides)
    nose_fraction: float         # Fraction of weight on nose/tail


def calculate_static_load_split_tricycle(
    weight_N: float,
    x_cg: float,
    x_main: float,
    x_nose: float,
) -> LoadSplit:
    """
    Calculate static load distribution for tricycle gear.
    
    Uses moment equilibrium about main gear contact point.
    
    Args:
        weight_N: Total aircraft weight in Newtons
        x_cg: CG position from datum (m)
        x_main: Main gear contact point from datum (m)
        x_nose: Nose gear contact point from datum (m)
        
    Returns:
        LoadSplit with nose and main gear loads
        
    Geometry Convention:
        - Positive x is typically aft
        - For tricycle: x_nose < x_cg < x_main (nose forward)
        
    Equations:
        Sum of moments about main gear = 0:
        R_nose * (x_main - x_nose) = W * (x_main - x_cg)
        R_nose = W * (x_main - x_cg) / (x_main - x_nose)
        R_main = W - R_nose
        
    Design Guidelines:
        - Nose load should be 8-15% of total weight
        - <8%: Poor steering authority, tail-heavy feel
        - >15%: Heavy nose gear, more drag, shimmy risk
    """
    wheelbase = x_main - x_nose  # Distance from nose to main
    
    if wheelbase <= 0:
        raise ValueError("Main gear must be aft of nose gear (x_main > x_nose)")
    
    # Moment arm from CG to main gear
    cg_to_main = x_main - x_cg
    
    # Nose gear reaction from moment equilibrium
    r_nose = weight_N * cg_to_main / wheelbase
    
    # Main gear takes the remainder
    r_main = weight_N - r_nose
    
    # Calculate fraction
    nose_fraction = r_nose / weight_N if weight_N > 0 else 0
    
    return LoadSplit(
        nose_or_tail_load_N=r_nose,
        main_load_total_N=r_main,
        nose_fraction=nose_fraction,
    )


def calculate_static_load_split_taildragger(
    weight_N: float,
    x_cg: float,
    x_main: float,
    x_tail: float,
) -> LoadSplit:
    """
    Calculate static load distribution for taildragger (conventional) gear.
    
    Args:
        weight_N: Total aircraft weight in Newtons
        x_cg: CG position from datum (m)
        x_main: Main gear contact point from datum (m)
        x_tail: Tail wheel contact point from datum (m)
        
    Returns:
        LoadSplit with tail and main gear loads
        
    Geometry Convention:
        - Positive x is aft
        - For taildragger: x_main < x_cg < x_tail (main forward of CG)
        
    Design Guidelines:
        - Tail load typically 5-10% of weight
        - CG must be behind main gear for ground stability
        - Too far aft CG causes ground loop tendency
    """
    wheelbase = x_tail - x_main  # Distance from main to tail
    
    if wheelbase <= 0:
        raise ValueError("Tail wheel must be aft of main gear (x_tail > x_main)")
    
    # Moment arm from CG to main gear
    cg_to_main = x_cg - x_main  # Positive when CG is aft of main
    
    # Tail reaction from moment equilibrium
    r_tail = weight_N * cg_to_main / wheelbase
    
    # Main gear takes the remainder
    r_main = weight_N - r_tail
    
    # Calculate fraction
    tail_fraction = r_tail / weight_N if weight_N > 0 else 0
    
    return LoadSplit(
        nose_or_tail_load_N=r_tail,
        main_load_total_N=r_main,
        nose_fraction=tail_fraction,
    )


def calculate_dynamic_load_factor(
    sink_rate_mps: float,
    stroke_m: float,
    efficiency: float = 0.80,
) -> float:
    """
    Calculate the dynamic load factor for landing impact.
    
    Args:
        sink_rate_mps: Vertical touchdown velocity
        stroke_m: Effective shock absorber stroke
        efficiency: Shock absorber efficiency (0.7-0.9 typical)
        
    Returns:
        Load factor (multiplier on static load)
        
    Notes:
        - Typical values: 1.5 to 3.0 for GA aircraft
        - FAR 23 requires design for specific sink rates
        - This is simplified; actual dynamics are more complex
    """
    g = G_STANDARD.magnitude
    
    # Energy balance: 0.5*m*v^2 = m*g*stroke*eff*(n-1)
    # Solving for n:
    n = (sink_rate_mps ** 2) / (2 * g * stroke_m * efficiency) + 1
    
    return n


def calculate_tire_load_requirements(
    static_main_load_per_wheel_N: float,
    dynamic_factor: float,
    safety_factor: float = 1.5,
) -> tuple[float, float]:
    """
    Calculate tire load requirements (static and dynamic).
    
    Args:
        static_main_load_per_wheel_N: Static load per main wheel
        dynamic_factor: Dynamic load multiplier from landing impact
        safety_factor: Additional safety margin (1.5 typical)
        
    Returns:
        Tuple of (required_static_N, required_dynamic_N) per tire
        
    Notes:
        - Tire ratings are typically for static loads
        - Dynamic loads must be within tire burst rating
        - Safety factor accounts for variations and wear
    """
    required_static = static_main_load_per_wheel_N * safety_factor
    required_dynamic = static_main_load_per_wheel_N * dynamic_factor * safety_factor
    
    return (required_static, required_dynamic)


def estimate_gear_positions_tricycle(
    cg_fwd_m: float,
    cg_aft_m: float,
    fuselage_length_m: float,
    main_gear_guess_m: float | None = None,
    nose_gear_guess_m: float | None = None,
) -> tuple[float, float, float, float]:
    """
    Estimate gear positions for tricycle configuration.
    
    Args:
        cg_fwd_m: Forward CG limit
        cg_aft_m: Aft CG limit
        fuselage_length_m: Estimated fuselage length
        main_gear_guess_m: Optional user-provided main gear position
        nose_gear_guess_m: Optional user-provided nose gear position
        
    Returns:
        Tuple of (x_nose_min, x_nose_max, x_main_min, x_main_max)
        
    Heuristics:
        - Main gear slightly aft of aft CG for tip-back margin
        - Nose gear near the nose, typically 0.06-0.12 * fuselage length from the nose/datum
        - Wheelbase typically 0.20-0.35 * fuselage length (varies by aircraft class)
    """
    cg_mid = (cg_fwd_m + cg_aft_m) / 2
    
    # Main gear position: slightly aft of aft CG
    if main_gear_guess_m is not None:
        x_main_mid = main_gear_guess_m
    else:
        # Place main gear ~5-10% of wheelbase aft of aft CG
        wheelbase_est = 0.30 * fuselage_length_m
        x_main_mid = cg_aft_m + 0.08 * wheelbase_est
    
    # Allow some variation in main gear position
    x_main_min = x_main_mid - 0.05 * fuselage_length_m
    x_main_max = x_main_mid + 0.05 * fuselage_length_m
    
    # Nose gear position
    if nose_gear_guess_m is not None:
        x_nose_mid = nose_gear_guess_m
    else:
        # Nose gear should usually be quite close to the nose.
        # Using 0.08*L helps keep the nose-load fraction in a typical range
        # for GA-style tricycle layouts when the datum is at/near the nose.
        x_nose_mid = 0.08 * fuselage_length_m
    
    x_nose_min = max(0.05 * fuselage_length_m, x_nose_mid - 0.03 * fuselage_length_m)
    x_nose_max = x_nose_mid + 0.05 * fuselage_length_m
    
    return (x_nose_min, x_nose_max, x_main_min, x_main_max)


def estimate_gear_positions_taildragger(
    cg_fwd_m: float,
    cg_aft_m: float,
    fuselage_length_m: float,
    main_gear_guess_m: float | None = None,
) -> tuple[float, float, float, float]:
    """
    Estimate gear positions for taildragger configuration.
    
    Args:
        cg_fwd_m: Forward CG limit
        cg_aft_m: Aft CG limit
        fuselage_length_m: Estimated fuselage length
        main_gear_guess_m: Optional user-provided main gear position
        
    Returns:
        Tuple of (x_main_min, x_main_max, x_tail_min, x_tail_max)
        
    Heuristics:
        - Main gear forward of forward CG for stability
        - Tail wheel near tail, typically 0.85-0.95 * fuselage length
        - Main gear position critical for ground handling
    """
    # Main gear position: forward of forward CG
    if main_gear_guess_m is not None:
        x_main_mid = main_gear_guess_m
    else:
        # Place main gear ~10-15% of wheelbase forward of fwd CG
        wheelbase_est = 0.70 * fuselage_length_m  # Taildraggers have longer wheelbase ratio
        x_main_mid = cg_fwd_m - 0.10 * wheelbase_est
    
    # Allow some variation
    x_main_min = x_main_mid - 0.05 * fuselage_length_m
    x_main_max = x_main_mid + 0.03 * fuselage_length_m  # Less aft variation
    
    # Tail wheel near the tail
    x_tail_mid = 0.90 * fuselage_length_m
    x_tail_min = 0.85 * fuselage_length_m
    x_tail_max = 0.95 * fuselage_length_m
    
    return (x_main_min, x_main_max, x_tail_min, x_tail_max)


def calculate_main_load_per_wheel(
    main_load_total_N: float,
    wheels_per_side: int,
    num_main_legs: int = 2,
) -> float:
    """
    Calculate load per main gear wheel.
    
    Args:
        main_load_total_N: Total load on all main gear
        wheels_per_side: Number of wheels per main gear leg
        num_main_legs: Number of main gear legs (2 for most aircraft)
        
    Returns:
        Load per individual wheel in Newtons
    """
    total_wheels = wheels_per_side * num_main_legs
    return main_load_total_N / total_wheels

