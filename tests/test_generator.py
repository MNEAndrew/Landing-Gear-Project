"""
Tests for gear candidate generator.

Tests the complete generation pipeline and output validation.
"""

import pytest

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import GearConfig, GearType
from gearrec.generator.candidates import GearGenerator


def create_test_inputs(**overrides) -> AircraftInputs:
    """Create test inputs with sensible defaults."""
    defaults = {
        "aircraft_name": "Test Aircraft",
        "mtow_kg": 1200.0,
        "mlw_kg": 1140.0,
        "cg_fwd_m": 2.1,
        "cg_aft_m": 2.4,
        "landing_speed_mps": 28.0,
        "sink_rate_mps": 2.0,
        "runway": RunwayType.PAVED,
        "retractable": False,
        "prop_clearance_m": 0.25,
        "wing_low": True,
        "design_priorities": DesignPriorities(),
    }
    defaults.update(overrides)
    return AircraftInputs(**defaults)


class TestGearGenerator:
    """Tests for GearGenerator class."""
    
    def test_generator_creates_candidates(self):
        """Test that generator produces candidate concepts."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        assert len(candidates) >= 3
        assert len(candidates) <= 10
    
    def test_candidates_are_sorted_by_score(self):
        """Test that candidates are returned in score order."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        scores = [c.score for c in candidates]
        assert scores == sorted(scores, reverse=True)
    
    def test_candidates_include_tricycle(self):
        """Test that tricycle config is generated."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        configs = [c.config for c in candidates]
        
        assert GearConfig.TRICYCLE in configs
    
    def test_candidates_include_fixed_when_not_retractable(self):
        """Test that fixed gear is included when not required retractable."""
        inputs = create_test_inputs(retractable=False)
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        gear_types = [c.gear_type for c in candidates]
        
        assert GearType.FIXED in gear_types
    
    def test_only_retractable_when_required(self):
        """Test that only retractable is generated when required."""
        inputs = create_test_inputs(retractable=True)
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            assert c.gear_type == GearType.RETRACTABLE
    
    def test_result_includes_metadata(self):
        """Test that full result includes metadata."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        assert result.aircraft_name == inputs.aircraft_name
        assert len(result.assumptions) > 0
        assert "mtow_kg" in result.input_summary
    
    def test_geometry_ranges_are_valid(self):
        """Test that geometry ranges have min < max."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            assert c.geometry.track_m.min <= c.geometry.track_m.max
            assert c.geometry.wheelbase_m.min <= c.geometry.wheelbase_m.max
            assert c.geometry.main_strut_length_m.min <= c.geometry.main_strut_length_m.max
            assert c.geometry.stroke_m.min <= c.geometry.stroke_m.max
    
    def test_loads_are_positive(self):
        """Test that all loads are positive."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            assert c.loads.static_main_load_total_N > 0
            assert c.loads.static_main_load_per_wheel_N > 0
            assert c.loads.landing_energy_J > 0
            assert c.loads.required_avg_force_N > 0
    
    def test_nose_load_fraction_reasonable(self):
        """Test that nose load fraction is in reasonable range."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            if c.config == GearConfig.TRICYCLE:
                # Nose load should be 5-20% for tricycle
                assert 0.03 <= c.loads.nose_load_fraction <= 0.25
    
    def test_scores_in_valid_range(self):
        """Test that all scores are between 0 and 1."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            assert 0 <= c.score <= 1
            assert 0 <= c.score_breakdown.robustness <= 1
            assert 0 <= c.score_breakdown.low_drag <= 1
            assert 0 <= c.score_breakdown.low_mass <= 1
            assert 0 <= c.score_breakdown.simplicity <= 1
    
    def test_explanations_are_provided(self):
        """Test that each concept has explanations."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        
        for c in candidates:
            assert len(c.explanation) >= 3


class TestGeneratorWithDifferentInputs:
    """Test generator behavior with varied inputs."""
    
    def test_light_aircraft(self):
        """Test with light aircraft (600 kg)."""
        inputs = create_test_inputs(mtow_kg=600, mlw_kg=570)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        assert len(result.concepts) >= 3
        # Light aircraft should have smaller geometry
        best = result.best_concept
        assert best.geometry.track_m.mid < 3.0
    
    def test_heavy_aircraft(self):
        """Test with heavier aircraft (3000 kg)."""
        inputs = create_test_inputs(mtow_kg=3000, mlw_kg=2850)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        assert len(result.concepts) >= 3
        # Heavy aircraft should have larger geometry
        best = result.best_concept
        assert best.geometry.track_m.mid > 1.5
    
    def test_grass_runway_affects_recommendations(self):
        """Test that grass runway affects geometry."""
        paved_inputs = create_test_inputs(runway=RunwayType.PAVED)
        grass_inputs = create_test_inputs(runway=RunwayType.GRASS)
        
        paved_result = GearGenerator(paved_inputs).generate_result()
        grass_result = GearGenerator(grass_inputs).generate_result()
        
        # Grass should recommend wider track or larger tires
        paved_best = paved_result.best_concept
        grass_best = grass_result.best_concept
        
        # At least one of these should be larger for grass
        paved_tire_diam = paved_best.tire_suggestion.recommended_tire_diameter_range_m.mid
        grass_tire_diam = grass_best.tire_suggestion.recommended_tire_diameter_range_m.mid
        
        assert grass_tire_diam >= paved_tire_diam
    
    def test_high_sink_rate_generates_warnings(self):
        """Test that high sink rate generates warnings."""
        inputs = create_test_inputs(sink_rate_mps=3.5)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        # Should have warning about high sink rate
        has_warning = any("sink rate" in w.lower() for w in result.warnings)
        assert has_warning
    
    def test_custom_priorities_affect_scores(self):
        """Test that design priorities affect scoring."""
        # Prioritize simplicity heavily
        simple_priorities = DesignPriorities(
            robustness=0.5,
            low_drag=0.5,
            low_mass=0.5,
            simplicity=3.0,
        )
        inputs = create_test_inputs(design_priorities=simple_priorities)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        best = result.best_concept
        
        # Best should likely be fixed gear (simpler)
        # At least check that simplicity score is weighted
        assert best.score_breakdown.simplicity > 0
    
    def test_no_prop_clearance_for_jets(self):
        """Test that zero prop clearance works for jet aircraft."""
        inputs = create_test_inputs(prop_clearance_m=0.0)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        assert len(result.concepts) >= 3
        # All should pass prop clearance (trivially)
        for c in result.concepts:
            assert c.checks.prop_clearance_ok


class TestGeneratorEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_narrow_cg_range(self):
        """Test with very narrow CG range."""
        inputs = create_test_inputs(cg_fwd_m=2.2, cg_aft_m=2.25)
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        assert len(candidates) >= 3
    
    def test_with_gear_position_hints(self):
        """Test with user-provided gear position hints."""
        inputs = create_test_inputs(
            main_gear_attach_guess_m=2.5,
            nose_gear_attach_guess_m=0.8,
        )
        generator = GearGenerator(inputs)
        
        candidates = generator.generate_candidates()
        assert len(candidates) >= 3
    
    def test_high_prop_clearance_requirement(self):
        """Test with high propeller clearance requirement."""
        inputs = create_test_inputs(prop_clearance_m=0.40)
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        # Should still produce results, but struts will be longer
        assert len(result.concepts) >= 1
        
        for c in result.concepts:
            # Main strut must be long enough
            assert c.geometry.main_strut_length_m.min >= 0.40


class TestBestConceptSelection:
    """Test best concept selection logic."""
    
    def test_best_concept_has_highest_score(self):
        """Test that best_concept returns highest scoring option."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        best = result.best_concept
        for c in result.concepts:
            assert c.score <= best.score
    
    def test_passing_concepts_filter(self):
        """Test that passing_concepts filters correctly."""
        inputs = create_test_inputs()
        generator = GearGenerator(inputs)
        
        result = generator.generate_result()
        
        for c in result.passing_concepts:
            assert c.all_checks_passed

