"""
Tests for physics calculations.

Tests energy, loads, geometry, and tire catalog calculations.
"""

import pytest

from gearrec.physics.energy import (
    calculate_touchdown_energy,
    calculate_required_shock_force,
    calculate_stroke_range,
    recommend_stroke_range_for_aircraft,
    calculate_load_factor_from_sink,
)
from gearrec.physics.loads import (
    calculate_static_load_split_tricycle,
    calculate_static_load_split_taildragger,
    calculate_dynamic_load_factor,
    calculate_tire_load_requirements,
    calculate_main_load_per_wheel,
)
from gearrec.physics.geometry import (
    estimate_fuselage_length,
    calculate_track_range,
    calculate_wheelbase_range,
    calculate_strut_length_range,
    estimate_cg_height,
    check_tip_back_margin,
    check_nose_over_margin,
    check_ground_clearance,
    check_lateral_rollover,
)
from gearrec.physics.tire_catalog import (
    find_matching_tires,
    estimate_tire_dimensions,
    TIRE_CATALOG,
)
from gearrec.physics.units import kg_to_N, N_to_kg


class TestEnergyCalculations:
    """Tests for energy.py module."""
    
    def test_touchdown_energy_basic(self):
        """Test basic touchdown energy calculation: E = 0.5 * m * v^2."""
        energy = calculate_touchdown_energy(1000.0, 2.0)
        assert energy == pytest.approx(2000.0, rel=0.01)
    
    def test_touchdown_energy_scales_with_mass(self):
        """Test that energy scales linearly with mass."""
        energy_1000 = calculate_touchdown_energy(1000.0, 2.0)
        energy_2000 = calculate_touchdown_energy(2000.0, 2.0)
        assert energy_2000 == pytest.approx(2 * energy_1000, rel=0.01)
    
    def test_touchdown_energy_scales_with_velocity_squared(self):
        """Test that energy scales with velocity squared."""
        energy_v2 = calculate_touchdown_energy(1000.0, 2.0)
        energy_v4 = calculate_touchdown_energy(1000.0, 4.0)
        assert energy_v4 == pytest.approx(4 * energy_v2, rel=0.01)
    
    def test_required_shock_force(self):
        """Test shock force calculation: F = E / (stroke * efficiency)."""
        force = calculate_required_shock_force(2000.0, 0.2, efficiency=0.8)
        assert force == pytest.approx(12500.0, rel=0.01)
    
    def test_required_shock_force_invalid_stroke(self):
        """Test that zero or negative stroke raises error."""
        with pytest.raises(ValueError):
            calculate_required_shock_force(2000.0, 0.0)
        with pytest.raises(ValueError):
            calculate_required_shock_force(2000.0, -0.1)
    
    def test_stroke_range_calculation(self):
        """Test stroke range calculation from energy and force limits."""
        energy = 5000
        max_force = 50000
        min_force = 25000
        
        min_stroke, max_stroke = calculate_stroke_range(
            energy, max_force, min_force, efficiency=0.8
        )
        
        expected_min = energy / (max_force * 0.8)
        expected_max = energy / (min_force * 0.8)
        
        assert min_stroke == pytest.approx(expected_min, rel=0.01)
        assert max_stroke == pytest.approx(expected_max, rel=0.01)
    
    def test_recommended_stroke_range(self):
        """Test stroke range recommendations for different weights."""
        light_min, light_max = recommend_stroke_range_for_aircraft(800, 2.0, "paved")
        heavy_min, heavy_max = recommend_stroke_range_for_aircraft(4000, 2.0, "paved")
        
        assert light_max < heavy_max
        assert light_min < heavy_min
    
    def test_load_factor_calculation(self):
        """Test landing load factor is reasonable for typical GA."""
        n = calculate_load_factor_from_sink(2.0, 0.2, efficiency=0.8)
        assert n > 1.0
        assert 1.5 <= n <= 3.5


class TestLoadsCalculations:
    """Tests for loads.py module."""
    
    def test_tricycle_load_split_basic(self):
        """Test basic tricycle load distribution."""
        weight = 10000
        result = calculate_static_load_split_tricycle(weight, 2.2, 2.5, 0.5)
        
        # Check loads sum to weight
        total = result.nose_or_tail_load_N + result.main_load_total_N
        assert total == pytest.approx(weight, rel=0.001)
    
    def test_tricycle_nose_load_fraction_reasonable(self):
        """Test that nose load fraction is in plausible range for tricycle."""
        weight = 12000
        result = calculate_static_load_split_tricycle(weight, 2.3, 2.6, 0.6)
        
        # Nose load should typically be 5-20% for tricycle
        assert 0.03 <= result.nose_fraction <= 0.25
    
    def test_taildragger_load_split_basic(self):
        """Test basic taildragger load distribution."""
        weight = 8000
        result = calculate_static_load_split_taildragger(weight, 2.0, 1.8, 6.0)
        
        total = result.nose_or_tail_load_N + result.main_load_total_N
        assert total == pytest.approx(weight, rel=0.001)
    
    def test_dynamic_load_factor(self):
        """Test dynamic load factor calculation."""
        factor = calculate_dynamic_load_factor(2.0, 0.2)
        assert factor > 1.0
        assert 1.5 <= factor <= 3.5
    
    def test_tire_load_requirements(self):
        """Test tire load requirement calculation with safety factor."""
        static_per_wheel = 5000
        dynamic_factor = 2.0
        
        static_req, dynamic_req = calculate_tire_load_requirements(
            static_per_wheel, dynamic_factor, safety_factor=1.5
        )
        
        assert static_req == pytest.approx(7500.0, rel=0.01)
        assert dynamic_req == pytest.approx(15000.0, rel=0.01)
    
    def test_main_load_per_wheel(self):
        """Test load distribution per wheel."""
        total_main = 10000
        per_wheel_single = calculate_main_load_per_wheel(total_main, 1)
        per_wheel_dual = calculate_main_load_per_wheel(total_main, 2)
        
        assert per_wheel_single == pytest.approx(5000.0, rel=0.01)
        assert per_wheel_dual == pytest.approx(2500.0, rel=0.01)


class TestGeometryCalculations:
    """Tests for geometry.py module."""
    
    def test_fuselage_length_estimate(self):
        """Test fuselage length estimation from MTOW."""
        length_light = estimate_fuselage_length(1000)
        length_heavy = estimate_fuselage_length(3000)
        
        assert 7 <= length_light <= 10
        assert length_heavy > length_light
    
    def test_track_range_basic(self):
        """Test track width range calculation."""
        min_track, max_track = calculate_track_range(9.0, "paved")
        
        assert min_track >= 1.5
        assert max_track <= 4.0
        assert min_track < max_track
    
    def test_track_wider_for_soft_field(self):
        """Test that soft field increases track range."""
        paved_min, paved_max = calculate_track_range(9.0, "paved")
        grass_min, grass_max = calculate_track_range(9.0, "grass")
        
        assert grass_min >= paved_min
        assert grass_max >= paved_max
    
    def test_wheelbase_longer_for_taildragger(self):
        """Test that taildragger has longer wheelbase."""
        tri_min, tri_max = calculate_wheelbase_range(9.0, "tricycle")
        tail_min, tail_max = calculate_wheelbase_range(9.0, "taildragger")
        
        assert tail_min > tri_max
    
    def test_strut_length_scales_with_weight(self):
        """Test that strut length increases with weight."""
        light_min, light_max = calculate_strut_length_range(800, 0.0)
        heavy_min, heavy_max = calculate_strut_length_range(3000, 0.0)
        
        assert heavy_min >= light_min
    
    def test_cg_height_estimate(self):
        """Test CG height estimation."""
        height_light = estimate_cg_height(1000)
        height_heavy = estimate_cg_height(3000)
        
        assert 0.8 <= height_light <= 1.5
        assert height_heavy >= height_light
    
    def test_tip_back_margin_pass(self):
        """Test tip-back margin check passing case."""
        result = check_tip_back_margin(
            x_cg_aft=2.3, x_main=2.5, wheelbase=2.0,
            cg_height=1.2, min_margin_ratio=0.10
        )
        assert result.passed
    
    def test_tip_back_margin_fail(self):
        """Test tip-back margin check failing case."""
        result = check_tip_back_margin(
            x_cg_aft=2.48, x_main=2.5, wheelbase=2.0,
            cg_height=1.2, min_margin_ratio=0.10
        )
        assert not result.passed
    
    def test_lateral_rollover_check(self):
        """Test lateral rollover stability check."""
        result_stable = check_lateral_rollover(track_m=2.5, cg_height_m=1.2)
        assert result_stable.passed
        assert result_stable.margin_value > 25.0


class TestTireCatalog:
    """Tests for tire_catalog.py module."""
    
    def test_catalog_has_entries(self):
        """Test that tire catalog is populated."""
        assert len(TIRE_CATALOG) > 0
    
    def test_find_matching_tires_basic(self):
        """Test basic tire matching."""
        tires = find_matching_tires(required_load_N=8000)
        
        assert len(tires) > 0
        # All matched tires should meet load requirement with margin
        for tire in tires:
            assert tire.max_load_N >= 8000 * 1.1
    
    def test_find_matching_tires_respects_pressure_limit(self):
        """Test that tire matching respects pressure limit when provided."""
        # Find tires with low pressure limit
        tires = find_matching_tires(
            required_load_N=5000,
            tire_pressure_limit_kpa=200,  # Very low limit
        )
        
        # All matched tires should have pressure <= limit (or no pressure rating)
        for tire in tires:
            if tire.max_pressure_kpa is not None:
                assert tire.max_pressure_kpa <= 200
    
    def test_find_matching_tires_soft_field_prefers_wider(self):
        """Test that soft field preference favors wider tires."""
        normal_tires = find_matching_tires(required_load_N=8000, prefer_soft_field=False)
        soft_tires = find_matching_tires(required_load_N=8000, prefer_soft_field=True)
        
        if normal_tires and soft_tires:
            # Soft field first choice should be at least as wide
            assert soft_tires[0].width_m >= normal_tires[0].width_m * 0.9
    
    def test_estimate_tire_dimensions_grass_wider(self):
        """Test that grass runway shifts tire width recommendations upward."""
        paved_diam, paved_width = estimate_tire_dimensions(5000, "paved")
        grass_diam, grass_width = estimate_tire_dimensions(5000, "grass")
        
        # Grass should recommend wider tires
        assert grass_width.min >= paved_width.min
        assert grass_width.max >= paved_width.max
    
    def test_estimate_tire_dimensions_gravel_larger(self):
        """Test that gravel runway shifts tire diameter recommendations upward."""
        paved_diam, paved_width = estimate_tire_dimensions(5000, "paved")
        gravel_diam, gravel_width = estimate_tire_dimensions(5000, "gravel")
        
        assert gravel_diam.min >= paved_diam.min


class TestUnitConversions:
    """Tests for unit conversion utilities."""
    
    def test_kg_to_N(self):
        """Test mass to weight conversion."""
        weight = kg_to_N(1.0)
        assert weight == pytest.approx(9.80665, rel=0.001)
    
    def test_N_to_kg(self):
        """Test weight to mass conversion."""
        mass = N_to_kg(9.80665)
        assert mass == pytest.approx(1.0, rel=0.001)
    
    def test_roundtrip_conversion(self):
        """Test that kg→N→kg gives original value."""
        original = 123.45
        converted = N_to_kg(kg_to_N(original))
        assert converted == pytest.approx(original, rel=0.0001)
