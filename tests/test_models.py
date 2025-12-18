"""
Tests for Pydantic models.

Tests input validation and output model behavior.
"""

import pytest
from pydantic import ValidationError

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import (
    GeometryRange,
    GearConcept,
    GearConfig,
    GearType,
    Geometry,
    TireSuggestion,
    Loads,
    CheckResult,
    Checks,
    ScoreBreakdown,
)


class TestDesignPriorities:
    """Tests for DesignPriorities model."""
    
    def test_default_priorities(self):
        """Test default priority values."""
        priorities = DesignPriorities()
        
        assert priorities.robustness == 1.0
        assert priorities.low_drag == 1.0
        assert priorities.low_mass == 1.0
        assert priorities.simplicity == 1.0
    
    def test_normalized_weights_sum_to_one(self):
        """Test that normalized weights sum to 1.0."""
        priorities = DesignPriorities(
            robustness=2.0,
            low_drag=1.0,
            low_mass=3.0,
            simplicity=4.0,
        )
        
        normalized = priorities.normalized()
        total = sum(normalized.values())
        
        assert total == pytest.approx(1.0, rel=0.001)
    
    def test_normalized_with_all_zero(self):
        """Test normalization with all zero weights."""
        priorities = DesignPriorities(
            robustness=0.0,
            low_drag=0.0,
            low_mass=0.0,
            simplicity=0.0,
        )
        
        normalized = priorities.normalized()
        
        # Should return equal weights
        assert normalized["robustness"] == 0.25
        assert normalized["low_drag"] == 0.25


class TestAircraftInputs:
    """Tests for AircraftInputs model."""
    
    def test_valid_inputs(self):
        """Test creating valid inputs."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1200.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.aircraft_name == "Test"
        assert inputs.mtow_kg == 1200.0
    
    def test_mlw_defaults_to_95_percent_mtow(self):
        """Test that MLW defaults to 95% of MTOW."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.get_mlw_kg() == pytest.approx(950.0, rel=0.01)
    
    def test_explicit_mlw_used(self):
        """Test that explicit MLW is used when provided."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            mlw_kg=900.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.get_mlw_kg() == 900.0
    
    def test_cg_mid_calculation(self):
        """Test CG midpoint calculation."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.cg_mid_m == pytest.approx(2.2, rel=0.01)
    
    def test_cg_range_calculation(self):
        """Test CG range calculation."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.cg_range_m == pytest.approx(0.4, rel=0.01)
    
    def test_invalid_cg_range_raises_error(self):
        """Test that aft CG before forward CG raises error."""
        with pytest.raises(ValidationError):
            AircraftInputs(
                aircraft_name="Test",
                mtow_kg=1000.0,
                cg_fwd_m=2.5,  # Forward is aft of "aft"
                cg_aft_m=2.0,
                landing_speed_mps=28.0,
            )
    
    def test_invalid_mtow_raises_error(self):
        """Test that negative MTOW raises error."""
        with pytest.raises(ValidationError):
            AircraftInputs(
                aircraft_name="Test",
                mtow_kg=-100.0,
                cg_fwd_m=2.0,
                cg_aft_m=2.4,
                landing_speed_mps=28.0,
            )
    
    def test_sink_rate_limits(self):
        """Test sink rate validation limits."""
        # Valid sink rate
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
            sink_rate_mps=3.0,
        )
        assert inputs.sink_rate_mps == 3.0
        
        # Sink rate too high
        with pytest.raises(ValidationError):
            AircraftInputs(
                aircraft_name="Test",
                mtow_kg=1000.0,
                cg_fwd_m=2.0,
                cg_aft_m=2.4,
                landing_speed_mps=28.0,
                sink_rate_mps=6.0,  # Too high
            )
    
    def test_runway_enum(self):
        """Test runway type enum values."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
            runway=RunwayType.GRASS,
        )
        
        assert inputs.runway == RunwayType.GRASS
        assert inputs.runway.value == "grass"


class TestGeometryRange:
    """Tests for GeometryRange model."""
    
    def test_mid_calculation(self):
        """Test midpoint calculation."""
        range_ = GeometryRange(min=2.0, max=3.0)
        assert range_.mid == 2.5
    
    def test_span_calculation(self):
        """Test span calculation."""
        range_ = GeometryRange(min=2.0, max=3.0)
        assert range_.span == 1.0


class TestOutputModels:
    """Tests for output model structures."""
    
    def test_check_result_structure(self):
        """Test CheckResult model."""
        check = CheckResult(
            passed=True,
            value=0.15,
            limit=0.10,
            description="Test check",
        )
        
        assert check.passed
        assert check.value > check.limit
    
    def test_score_breakdown_bounds(self):
        """Test ScoreBreakdown value bounds."""
        # Valid scores
        breakdown = ScoreBreakdown(
            robustness=0.8,
            low_drag=0.6,
            low_mass=0.9,
            simplicity=0.7,
            checks_penalty=0.1,
        )
        
        assert 0 <= breakdown.robustness <= 1
        
        # Invalid score raises error
        with pytest.raises(ValidationError):
            ScoreBreakdown(
                robustness=1.5,  # > 1
                low_drag=0.6,
                low_mass=0.9,
                simplicity=0.7,
            )

