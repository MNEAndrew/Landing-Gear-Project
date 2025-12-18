"""
Energy and shock absorption calculations.

Provides simplified models for:
- Touchdown kinetic energy from sink rate
- Required shock absorber force based on stroke
- Stroke range estimation

ASSUMPTIONS:
- All vertical kinetic energy must be absorbed by shock absorbers
- Tire deflection provides additional absorption (not modeled in detail here)
- Uses average force model (actual is more complex with spring/damper curves)
"""

from gearrec.physics.units import ureg, Q_, G_STANDARD


def calculate_touchdown_energy(
    landing_mass_kg: float,
    sink_rate_mps: float,
) -> float:
    """
    Calculate kinetic energy to be absorbed at touchdown.
    
    Uses E = 0.5 * m * v^2 where v is vertical (sink) rate.
    
    Args:
        landing_mass_kg: Aircraft mass at landing (typically MLW)
        sink_rate_mps: Vertical touchdown velocity in m/s
        
    Returns:
        Energy in Joules
        
    Assumptions:
        - All vertical KE absorbed by landing gear
        - Horizontal velocity absorbed by brakes, not gear (idealized)
        - No lift contribution at touchdown (conservative)
    """
    mass = Q_(landing_mass_kg, "kg")
    velocity = Q_(sink_rate_mps, "m/s")
    
    energy = 0.5 * mass * velocity**2
    
    return energy.to("J").magnitude


def calculate_required_shock_force(
    energy_J: float,
    stroke_m: float,
    efficiency: float = 0.80,
) -> float:
    """
    Calculate average force required during shock absorption.
    
    Uses work-energy principle: F_avg * stroke * efficiency = E
    
    Args:
        energy_J: Energy to absorb in Joules
        stroke_m: Shock absorber stroke (travel) in meters
        efficiency: Shock absorber efficiency (0.7-0.9 typical)
                   Accounts for energy not ideally absorbed
                   
    Returns:
        Average force in Newtons
        
    Assumptions:
        - Simple work-energy model with average force
        - Efficiency accounts for non-ideal absorption
        - Does not model specific spring/damper characteristics
        - Gear factor of 1.0 (actual varies with design)
    """
    if stroke_m <= 0:
        raise ValueError("Stroke must be positive")
    if not 0.5 <= efficiency <= 1.0:
        raise ValueError("Efficiency should be between 0.5 and 1.0")
    
    # F * stroke * efficiency = E
    # F = E / (stroke * efficiency)
    force = energy_J / (stroke_m * efficiency)
    
    return force


def calculate_stroke_range(
    energy_J: float,
    max_force_N: float,
    min_force_N: float | None = None,
    efficiency: float = 0.80,
) -> tuple[float, float]:
    """
    Calculate the range of shock absorber stroke needed.
    
    Given energy and force limits, determine required stroke range.
    
    Args:
        energy_J: Energy to absorb
        max_force_N: Maximum allowable shock force (structural limit)
        min_force_N: Minimum acceptable force (if too low, stroke too long)
        efficiency: Shock absorber efficiency
        
    Returns:
        Tuple of (min_stroke_m, max_stroke_m)
        
    Assumptions:
        - Linear work model
        - Force limits based on structural constraints
    """
    if max_force_N <= 0:
        raise ValueError("Max force must be positive")
    
    # stroke = E / (F * efficiency)
    min_stroke = energy_J / (max_force_N * efficiency)
    
    if min_force_N is not None and min_force_N > 0:
        max_stroke = energy_J / (min_force_N * efficiency)
    else:
        # Default to 2x min stroke if no min force specified
        max_stroke = min_stroke * 2.0
    
    return (min_stroke, max_stroke)


def recommend_stroke_range_for_aircraft(
    mtow_kg: float,
    sink_rate_mps: float,
    runway_type: str = "paved",
) -> tuple[float, float]:
    """
    Recommend a stroke range based on aircraft weight and conditions.
    
    Uses empirical correlations from GA aircraft data.
    
    Args:
        mtow_kg: Maximum takeoff weight
        sink_rate_mps: Design sink rate
        runway_type: paved, grass, or gravel
        
    Returns:
        Tuple of (min_stroke_m, max_stroke_m)
        
    Heuristics:
        - Light GA (<1500 kg): 0.10-0.20 m stroke typical
        - Medium GA (1500-3000 kg): 0.15-0.25 m stroke
        - Heavy GA (>3000 kg): 0.20-0.35 m stroke
        - Soft field adds 20-30% to stroke for energy absorption
    """
    # Base stroke from empirical correlation
    # Heavier aircraft need longer stroke
    if mtow_kg < 1500:
        base_min, base_max = 0.10, 0.20
    elif mtow_kg < 3000:
        base_min, base_max = 0.15, 0.25
    elif mtow_kg < 6000:
        base_min, base_max = 0.20, 0.30
    else:
        base_min, base_max = 0.25, 0.40
    
    # Adjust for sink rate (higher sink = more stroke needed)
    # Baseline is 2.0 m/s
    sink_factor = (sink_rate_mps / 2.0) ** 0.5  # Square root scaling
    
    # Adjust for runway type
    runway_factors = {
        "paved": 1.0,
        "grass": 1.2,  # Soft field needs more absorption
        "gravel": 1.25,
    }
    runway_factor = runway_factors.get(runway_type, 1.0)
    
    min_stroke = base_min * sink_factor * runway_factor
    max_stroke = base_max * sink_factor * runway_factor
    
    # Clamp to reasonable limits
    min_stroke = max(0.08, min(min_stroke, 0.35))
    max_stroke = max(0.12, min(max_stroke, 0.50))
    
    return (min_stroke, max_stroke)


def calculate_load_factor_from_sink(
    sink_rate_mps: float,
    stroke_m: float,
    efficiency: float = 0.80,
) -> float:
    """
    Calculate the load factor (n) experienced during landing.
    
    Uses energy-based approach: n = (v^2) / (2 * g * stroke * efficiency) + 1
    
    Args:
        sink_rate_mps: Vertical touchdown velocity
        stroke_m: Shock absorber stroke
        efficiency: Shock absorber efficiency
        
    Returns:
        Load factor (dimensionless, 1.0 = 1g)
        
    Notes:
        - FAR 23 typically requires design for 2.0-3.0g landing loads
        - This is a simplified model; actual loads depend on gear dynamics
    """
    g = G_STANDARD.magnitude  # 9.80665 m/s^2
    
    # From energy balance:
    # 0.5*m*v^2 = m*g*stroke*efficiency*(n-1)
    # n = v^2 / (2*g*stroke*efficiency) + 1
    
    n = (sink_rate_mps ** 2) / (2 * g * stroke_m * efficiency) + 1
    
    return n

