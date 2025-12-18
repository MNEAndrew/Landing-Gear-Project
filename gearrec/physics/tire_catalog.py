"""
Tire catalog and matching logic.

Provides a minimal internal tire catalog for conceptual sizing.
This is for CONCEPTUAL SIZING ONLY - actual tire selection requires
manufacturer data and certification considerations.

ASSUMPTIONS:
- Catalog represents typical GA aircraft tires
- Load ratings are approximate for conceptual purposes
- Pressure ratings are typical values
"""

from dataclasses import dataclass
from typing import Optional

from gearrec.models.outputs import CatalogTire, GeometryRange


@dataclass
class TireCatalogEntry:
    """Internal tire catalog entry."""
    name: str
    diameter_m: float
    width_m: float
    max_load_N: float
    max_pressure_kpa: Optional[float] = None
    soft_field_suitable: bool = False


# Minimal tire catalog for conceptual sizing
# Based on typical GA aircraft tire sizes
TIRE_CATALOG: list[TireCatalogEntry] = [
    # Small/ultralight tires
    TireCatalogEntry(
        name="4.00-6",
        diameter_m=0.305,
        width_m=0.102,
        max_load_N=2670,
        max_pressure_kpa=207,
        soft_field_suitable=False,
    ),
    TireCatalogEntry(
        name="5.00-5",
        diameter_m=0.356,
        width_m=0.127,
        max_load_N=4450,
        max_pressure_kpa=310,
        soft_field_suitable=False,
    ),
    # Light GA tires
    TireCatalogEntry(
        name="6.00-6",
        diameter_m=0.432,
        width_m=0.152,
        max_load_N=6670,
        max_pressure_kpa=345,
        soft_field_suitable=True,
    ),
    TireCatalogEntry(
        name="6.50-8",
        diameter_m=0.483,
        width_m=0.165,
        max_load_N=7560,
        max_pressure_kpa=276,
        soft_field_suitable=True,
    ),
    TireCatalogEntry(
        name="7.00-6",
        diameter_m=0.483,
        width_m=0.178,
        max_load_N=9790,
        max_pressure_kpa=345,
        soft_field_suitable=True,
    ),
    # Medium GA tires
    TireCatalogEntry(
        name="8.00-6",
        diameter_m=0.508,
        width_m=0.203,
        max_load_N=13350,
        max_pressure_kpa=379,
        soft_field_suitable=True,
    ),
    TireCatalogEntry(
        name="8.50-6",
        diameter_m=0.533,
        width_m=0.216,
        max_load_N=15570,
        max_pressure_kpa=414,
        soft_field_suitable=True,
    ),
    # Larger GA / light twin tires
    TireCatalogEntry(
        name="22x8.00-8",
        diameter_m=0.559,
        width_m=0.203,
        max_load_N=17800,
        max_pressure_kpa=310,
        soft_field_suitable=True,
    ),
    TireCatalogEntry(
        name="24x7.25-10",
        diameter_m=0.610,
        width_m=0.184,
        max_load_N=20020,
        max_pressure_kpa=448,
        soft_field_suitable=False,
    ),
    TireCatalogEntry(
        name="26x10.5-6 Bush",
        diameter_m=0.660,
        width_m=0.267,
        max_load_N=22240,
        max_pressure_kpa=138,
        soft_field_suitable=True,
    ),
    # Heavy GA / turboprop
    TireCatalogEntry(
        name="29x11.0-10",
        diameter_m=0.737,
        width_m=0.279,
        max_load_N=31140,
        max_pressure_kpa=345,
        soft_field_suitable=True,
    ),
]


def find_matching_tires(
    required_load_N: float,
    tire_pressure_limit_kpa: Optional[float] = None,
    prefer_soft_field: bool = False,
    max_results: int = 3,
) -> list[CatalogTire]:
    """
    Find tires from catalog that meet load requirements.
    
    Args:
        required_load_N: Required dynamic load capacity per tire
        tire_pressure_limit_kpa: Maximum allowable tire pressure (if specified)
        prefer_soft_field: If True, prefer wider tires suitable for soft fields
        max_results: Maximum number of tires to return
        
    Returns:
        List of matching CatalogTire objects, sorted by preference
        
    Matching Logic:
        1. Must meet required_load_N
        2. If tire_pressure_limit_kpa specified, must not exceed it
        3. If prefer_soft_field, prioritize wider tires with soft_field_suitable flag
        4. Otherwise prefer smallest adequate tire
    """
    candidates = []
    
    for entry in TIRE_CATALOG:
        # Check load capacity (require 10% margin)
        if entry.max_load_N < required_load_N * 1.1:
            continue
        
        # Check pressure limit if specified
        if tire_pressure_limit_kpa is not None and entry.max_pressure_kpa is not None:
            if entry.max_pressure_kpa > tire_pressure_limit_kpa:
                continue
        
        candidates.append(entry)
    
    if not candidates:
        return []
    
    # Sort by preference
    if prefer_soft_field:
        # Prefer: soft field suitable, then wider, then smaller diameter
        candidates.sort(
            key=lambda t: (
                not t.soft_field_suitable,  # Soft field first
                -t.width_m,                  # Wider first
                t.diameter_m,                # Then smaller diameter
            )
        )
    else:
        # Prefer smallest tire that meets requirements
        candidates.sort(
            key=lambda t: (
                t.diameter_m,  # Smallest diameter
                t.width_m,     # Then narrowest
            )
        )
    
    # Convert to output model
    result = []
    for entry in candidates[:max_results]:
        result.append(CatalogTire(
            name=entry.name,
            diameter_m=entry.diameter_m,
            width_m=entry.width_m,
            max_load_N=entry.max_load_N,
            max_pressure_kpa=entry.max_pressure_kpa,
        ))
    
    return result


def estimate_tire_dimensions(
    load_per_tire_N: float,
    runway_type: str = "paved",
    tire_pressure_limit_kpa: Optional[float] = None,
) -> tuple[GeometryRange, GeometryRange]:
    """
    Estimate tire diameter and width ranges based on load and conditions.
    
    Args:
        load_per_tire_N: Required load capacity per tire in Newtons
        runway_type: paved, grass, or gravel
        tire_pressure_limit_kpa: Maximum tire pressure constraint
        
    Returns:
        Tuple of (diameter_range, width_range) as GeometryRange objects
        
    Heuristics:
        - Diameter scales with load (heavier = larger)
        - Soft field favors wider tires
        - Low pressure limits favor larger contact patch
    """
    # Base diameter from load correlation
    if load_per_tire_N < 3000:
        base_diam_min, base_diam_max = 0.25, 0.35
        base_width_min, base_width_max = 0.08, 0.12
    elif load_per_tire_N < 5000:
        base_diam_min, base_diam_max = 0.30, 0.40
        base_width_min, base_width_max = 0.10, 0.14
    elif load_per_tire_N < 10000:
        base_diam_min, base_diam_max = 0.35, 0.50
        base_width_min, base_width_max = 0.12, 0.18
    elif load_per_tire_N < 20000:
        base_diam_min, base_diam_max = 0.45, 0.60
        base_width_min, base_width_max = 0.15, 0.22
    else:
        base_diam_min, base_diam_max = 0.55, 0.75
        base_width_min, base_width_max = 0.20, 0.30
    
    # Runway adjustment factors
    runway_factors = {
        "paved": (1.0, 1.0),    # (diameter factor, width factor)
        "grass": (1.15, 1.30),  # Larger, wider for soft field
        "gravel": (1.10, 1.20),
    }
    diam_factor, width_factor = runway_factors.get(runway_type, (1.0, 1.0))
    
    # Pressure limit adjustment
    if tire_pressure_limit_kpa is not None:
        if tire_pressure_limit_kpa < 200:  # Very low pressure
            diam_factor *= 1.20
            width_factor *= 1.30
        elif tire_pressure_limit_kpa < 300:  # Low pressure
            diam_factor *= 1.10
            width_factor *= 1.15
    
    diameter_range = GeometryRange(
        min=base_diam_min * diam_factor,
        max=base_diam_max * diam_factor,
    )
    
    width_range = GeometryRange(
        min=base_width_min * width_factor,
        max=base_width_max * width_factor,
    )
    
    return diameter_range, width_range

