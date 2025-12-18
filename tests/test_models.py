"""
Tests for Pydantic models.

Tests input validation, output model behavior, and JSON serialization.
"""

import json
import pytest
from pydantic import ValidationError

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import (
    GeometryRange,
    GearConfig,
    GearType,
    ScoreBreakdown,
    SweepResult,
    ConceptSweepResult,
    SweepPoint,
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
            robustness=2.0, low_drag=1.0, low_mass=3.0, simplicity=4.0,
        )
        
        normalized = priorities.normalized()
        total = sum(normalized.values())
        
        assert total == pytest.approx(1.0, rel=0.001)
    
    def test_normalized_with_all_zero(self):
        """Test normalization with all zero weights."""
        priorities = DesignPriorities(
            robustness=0.0, low_drag=0.0, low_mass=0.0, simplicity=0.0,
        )
        
        normalized = priorities.normalized()
        
        assert normalized["robustness"] == 0.25


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
    
    def test_fuselage_length_estimation(self):
        """Test fuselage length estimation when not provided."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1200.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        length = inputs.get_fuselage_length_m()
        assert 5 <= length <= 25
    
    def test_explicit_fuselage_length_used(self):
        """Test that explicit fuselage length is used when provided."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1200.0,
            fuselage_length_m=10.5,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.get_fuselage_length_m() == 10.5
    
    def test_cg_height_estimation(self):
        """Test CG height estimation when not provided."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1200.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        height = inputs.get_cg_height_m()
        assert 0.8 <= height <= 2.5
    
    def test_invalid_cg_range_raises_error(self):
        """Test that aft CG before forward CG raises error."""
        with pytest.raises(ValidationError):
            AircraftInputs(
                aircraft_name="Test",
                mtow_kg=1000.0,
                cg_fwd_m=2.5,
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
    
    def test_brake_decel_g_default(self):
        """Test that brake_decel_g has correct default."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1000.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        assert inputs.brake_decel_g == 0.4


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


class TestJSONSerialization:
    """Tests for JSON serialization round-trip."""
    
    def test_aircraft_inputs_json_roundtrip(self):
        """Test that AircraftInputs survives JSON round-trip."""
        inputs = AircraftInputs(
            aircraft_name="Test",
            mtow_kg=1200.0,
            cg_fwd_m=2.0,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
            sink_rate_mps=2.5,
            runway=RunwayType.GRASS,
        )
        
        json_str = inputs.model_dump_json()
        restored = AircraftInputs.model_validate_json(json_str)
        
        assert restored.aircraft_name == inputs.aircraft_name
        assert restored.mtow_kg == inputs.mtow_kg
        assert restored.runway == inputs.runway
    
    def test_sweep_result_json_roundtrip(self):
        """Test that SweepResult survives JSON round-trip."""
        result = SweepResult(
            aircraft_name="Test",
            sink_rates_swept=[1.5, 2.0, 2.5],
            cg_positions_swept=[2.0, 2.2, 2.4],
            concept_results=[
                ConceptSweepResult(
                    config=GearConfig.TRICYCLE,
                    gear_type=GearType.FIXED,
                    pass_rate=0.8,
                    avg_score=0.75,
                    worst_case_score=0.6,
                    best_case_score=0.9,
                    sweep_points=[
                        SweepPoint(
                            sink_rate_mps=2.0,
                            cg_position_m=2.2,
                            cg_label="mid",
                            all_checks_passed=True,
                            score=0.75,
                            failed_checks=[],
                        )
                    ],
                )
            ],
            most_robust_concept="tricycle_fixed",
        )
        
        json_str = result.model_dump_json()
        restored = SweepResult.model_validate_json(json_str)
        
        assert restored.aircraft_name == result.aircraft_name
        assert restored.most_robust_concept == result.most_robust_concept
        assert len(restored.concept_results) == 1


class TestScoreBreakdown:
    """Tests for ScoreBreakdown model."""
    
    def test_valid_scores(self):
        """Test valid score values."""
        breakdown = ScoreBreakdown(
            robustness=0.8,
            low_drag=0.6,
            low_mass=0.9,
            simplicity=0.7,
        )
        
        assert breakdown.robustness == 0.8
    
    def test_invalid_score_over_one(self):
        """Test that score > 1 raises error."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(
                robustness=1.5,
                low_drag=0.6,
                low_mass=0.9,
                simplicity=0.7,
            )
    
    def test_invalid_score_negative(self):
        """Test that negative score raises error."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(
                robustness=-0.1,
                low_drag=0.6,
                low_mass=0.9,
                simplicity=0.7,
            )
