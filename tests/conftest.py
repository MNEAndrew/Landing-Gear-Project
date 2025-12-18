"""
Pytest configuration and shared fixtures.
"""

import pytest
from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities


@pytest.fixture
def basic_inputs() -> AircraftInputs:
    """Provide basic aircraft inputs for testing."""
    return AircraftInputs(
        aircraft_name="Test Aircraft",
        mtow_kg=1200.0,
        mlw_kg=1140.0,
        cg_fwd_m=2.1,
        cg_aft_m=2.4,
        landing_speed_mps=28.0,
        sink_rate_mps=2.0,
        runway=RunwayType.PAVED,
        retractable=False,
        prop_clearance_m=0.25,
        wing_low=True,
        design_priorities=DesignPriorities(),
    )


@pytest.fixture
def light_aircraft_inputs() -> AircraftInputs:
    """Provide light aircraft inputs (LSA class)."""
    return AircraftInputs(
        aircraft_name="Light Sport",
        mtow_kg=600.0,
        mlw_kg=570.0,
        cg_fwd_m=1.5,
        cg_aft_m=1.8,
        landing_speed_mps=22.0,
        sink_rate_mps=1.8,
        runway=RunwayType.GRASS,
        retractable=False,
        prop_clearance_m=0.20,
        wing_low=False,
        design_priorities=DesignPriorities(
            robustness=1.5,
            low_drag=0.5,
            low_mass=1.0,
            simplicity=2.0,
        ),
    )


@pytest.fixture
def heavy_aircraft_inputs() -> AircraftInputs:
    """Provide heavier aircraft inputs."""
    return AircraftInputs(
        aircraft_name="Heavy Twin",
        mtow_kg=3500.0,
        mlw_kg=3325.0,
        cg_fwd_m=3.2,
        cg_aft_m=3.8,
        landing_speed_mps=38.0,
        sink_rate_mps=2.5,
        runway=RunwayType.PAVED,
        retractable=True,
        prop_clearance_m=0.35,
        wing_low=True,
        design_priorities=DesignPriorities(
            robustness=1.0,
            low_drag=2.0,
            low_mass=1.0,
            simplicity=0.5,
        ),
    )

