"""
Tests for physics calculations.

Tests energy, loads, and geometry calculations.
"""

import pytest
import math

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
    estimate_gear_positions_tricycle,
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
    estimate_tire_diameter,
)
from gearrec.physics.units import kg_to_N, N_to_kg


class TestEnergyCalculations:
    """Tests for energy.py module."""
    
    def test_touchdown_energy_basic(self):
        """Test basic touchdown energy calculation."""
        # E = 0.5 * m * v^2
        # For 1000 kg at 2 m/s: E = 0.5 * 1000 * 4 = 2000 J
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
        # v^2 ratio: (4/2)^2 = 4
        assert energy_v4 == pytest.approx(4 * energy_v2, rel=0.01)
    
    def test_required_shock_force(self):
        """Test shock force calculation from energy and stroke."""
        # F = E / (stroke * efficiency)
        # For 2000 J, 0.2 m stroke, 0.8 efficiency: F = 2000 / (0.2 * 0.8) = 12500 N
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
        energy = 5000  # J
        max_force = 50000  # N
        min_force = 25000  # N
        
        min_stroke, max_stroke = calculate_stroke_range(
            energy, max_force, min_force, efficiency=0.8
        )
        
        # stroke = E / (F * efficiency)
        expected_min = energy / (max_force * 0.8)  # 0.125 m
        expected_max = energy / (min_force * 0.8)  # 0.25 m
        
        assert min_stroke == pytest.approx(expected_min, rel=0.01)
        assert max_stroke == pytest.approx(expected_max, rel=0.01)
    
    def test_recommended_stroke_range(self):
        """Test stroke range recommendations for different weights."""
        # Light aircraft should have shorter stroke
        light_min, light_max = recommend_stroke_range_for_aircraft(800, 2.0, "paved")
        # Heavy aircraft should have longer stroke
        heavy_min, heavy_max = recommend_stroke_range_for_aircraft(4000, 2.0, "paved")
        
        assert light_max < heavy_max
        assert light_min < heavy_min
    
    def test_load_factor_calculation(self):
        """Test landing load factor calculation."""
        # Typical GA: 2 m/s sink, 0.2 m stroke
        n = calculate_load_factor_from_sink(2.0, 0.2, efficiency=0.8)
        
        # Expected: n = v^2 / (2*g*stroke*eff) + 1
        # n = 4 / (2 * 9.81 * 0.2 * 0.8) + 1 ≈ 2.27
        assert n == pytest.approx(2.27, rel=0.05)
        assert n > 1.0  # Must be greater than 1g


class TestLoadsCalculations:
    """Tests for loads.py module."""
    
    def test_tricycle_load_split_basic(self):
        """Test basic tricycle load distribution."""
        weight = 10000  # N
        x_cg = 2.2      # m from datum
        x_main = 2.5    # m (aft of CG)
        x_nose = 0.5    # m (forward of CG)
        
        result = calculate_static_load_split_tricycle(weight, x_cg, x_main, x_nose)
        
        # Moment equilibrium:
        # R_nose * (2.5 - 0.5) = 10000 * (2.5 - 2.2)
        # R_nose = 10000 * 0.3 / 2.0 = 1500 N
        assert result.nose_or_tail_load_N == pytest.approx(1500.0, rel=0.01)
        assert result.main_load_total_N == pytest.approx(8500.0, rel=0.01)
        assert result.nose_fraction == pytest.approx(0.15, rel=0.01)
    
    def test_tricycle_loads_sum_to_weight(self):
        """Test that nose + main loads equal total weight."""
        weight = 12000  # N
        result = calculate_static_load_split_tricycle(weight, 2.3, 2.6, 0.6)
        
        total = result.nose_or_tail_load_N + result.main_load_total_N
        assert total == pytest.approx(weight, rel=0.001)
    
    def test_taildragger_load_split_basic(self):
        """Test basic taildragger load distribution."""
        weight = 8000   # N
        x_cg = 2.0      # m (behind main gear)
        x_main = 1.8    # m
        x_tail = 6.0    # m
        
        result = calculate_static_load_split_taildragger(weight, x_cg, x_main, x_tail)
        
        # CG is 0.2 m aft of main gear
        # Tail load = W * (x_cg - x_main) / (x_tail - x_main)
        # = 8000 * 0.2 / 4.2 ≈ 380 N
        assert result.nose_or_tail_load_N == pytest.approx(380.95, rel=0.01)
        
        # Total should equal weight
        total = result.nose_or_tail_load_N + result.main_load_total_N
        assert total == pytest.approx(weight, rel=0.001)
    
    def test_dynamic_load_factor(self):
        """Test dynamic load factor calculation."""
        factor = calculate_dynamic_load_factor(2.0, 0.2)
        
        # Should be > 1 (landing adds load)
        assert factor > 1.0
        # Should be reasonable for GA (typically 1.5-3.0)
        assert 1.5 <= factor <= 3.0
    
    def test_tire_load_requirements(self):
        """Test tire load requirement calculation."""
        static_per_wheel = 5000  # N
        dynamic_factor = 2.0
        
        static_req, dynamic_req = calculate_tire_load_requirements(
            static_per_wheel, dynamic_factor, safety_factor=1.5
        )
        
        assert static_req == pytest.approx(7500.0, rel=0.01)  # 5000 * 1.5
        assert dynamic_req == pytest.approx(15000.0, rel=0.01)  # 5000 * 2.0 * 1.5
    
    def test_main_load_per_wheel(self):
        """Test load distribution per wheel."""
        total_main = 10000  # N
        
        # Single wheel per side (2 total)
        per_wheel_single = calculate_main_load_per_wheel(total_main, 1)
        assert per_wheel_single == pytest.approx(5000.0, rel=0.01)
        
        # Dual wheels per side (4 total)
        per_wheel_dual = calculate_main_load_per_wheel(total_main, 2)
        assert per_wheel_dual == pytest.approx(2500.0, rel=0.01)


class TestGeometryCalculations:
    """Tests for geometry.py module."""
    
    def test_fuselage_length_estimate(self):
        """Test fuselage length estimation from MTOW."""
        # Light GA aircraft (~1000 kg) should be ~8-9 m
        length_light = estimate_fuselage_length(1000)
        assert 7 <= length_light <= 10
        
        # Heavier aircraft should be longer
        length_heavy = estimate_fuselage_length(3000)
        assert length_heavy > length_light
    
    def test_track_range_basic(self):
        """Test track width range calculation."""
        fuselage_length = 9.0  # m
        
        min_track, max_track = calculate_track_range(fuselage_length, "paved")
        
        # Should be roughly 0.18-0.28 * length = 1.62-2.52 m
        assert min_track >= 1.5  # Minimum practical
        assert max_track <= 4.0  # Maximum practical for GA
        assert min_track < max_track
    
    def test_track_wider_for_soft_field(self):
        """Test that soft field increases track range."""
        fuselage_length = 9.0
        
        paved_min, paved_max = calculate_track_range(fuselage_length, "paved")
        grass_min, grass_max = calculate_track_range(fuselage_length, "grass")
        
        # Grass should recommend wider track
        assert grass_min >= paved_min
        assert grass_max >= paved_max
    
    def test_wheelbase_range_tricycle(self):
        """Test wheelbase range for tricycle config."""
        fuselage_length = 9.0
        
        min_wb, max_wb = calculate_wheelbase_range(fuselage_length, "tricycle")
        
        # Should be 0.25-0.35 * length = 2.25-3.15 m
        assert 2.0 <= min_wb <= 4.0
        assert min_wb < max_wb
    
    def test_wheelbase_longer_for_taildragger(self):
        """Test that taildragger has longer wheelbase."""
        fuselage_length = 9.0
        
        tri_min, tri_max = calculate_wheelbase_range(fuselage_length, "tricycle")
        tail_min, tail_max = calculate_wheelbase_range(fuselage_length, "taildragger")
        
        # Taildragger wheelbase is much longer (main to tail)
        assert tail_min > tri_max
    
    def test_strut_length_scales_with_weight(self):
        """Test that strut length increases with weight."""
        light_min, light_max = calculate_strut_length_range(800, 0.0)
        heavy_min, heavy_max = calculate_strut_length_range(3000, 0.0)
        
        assert heavy_min >= light_min
        assert heavy_max >= light_max
    
    def test_strut_length_includes_prop_clearance(self):
        """Test that propeller clearance affects strut length."""
        no_prop_min, no_prop_max = calculate_strut_length_range(1200, 0.0)
        with_prop_min, with_prop_max = calculate_strut_length_range(1200, 0.30)
        
        # Prop clearance should increase minimum strut length
        assert with_prop_min >= no_prop_min
    
    def test_cg_height_estimate(self):
        """Test CG height estimation."""
        # Light aircraft
        height_light = estimate_cg_height(1000)
        assert 0.8 <= height_light <= 1.5
        
        # Heavier aircraft should have higher CG
        height_heavy = estimate_cg_height(3000)
        assert height_heavy >= height_light
    
    def test_tip_back_margin_pass(self):
        """Test tip-back margin check passing case."""
        # CG forward of main gear
        result = check_tip_back_margin(
            x_cg_aft=2.3,      # Aft CG
            x_main=2.5,         # Main gear position
            wheelbase=2.0,      # m
            cg_height=1.2,
            min_margin_ratio=0.10
        )
        
        # Margin = (2.5 - 2.3) / 2.0 = 0.10, equals minimum
        assert result.passed
        assert result.margin_value == pytest.approx(0.10, rel=0.01)
    
    def test_tip_back_margin_fail(self):
        """Test tip-back margin check failing case."""
        # CG too close to main gear
        result = check_tip_back_margin(
            x_cg_aft=2.45,
            x_main=2.5,
            wheelbase=2.0,
            cg_height=1.2,
            min_margin_ratio=0.10
        )
        
        # Margin = (2.5 - 2.45) / 2.0 = 0.025 < 0.10
        assert not result.passed
        assert result.margin_value < 0.10
    
    def test_nose_over_margin_pass(self):
        """Test nose-over margin check passing case."""
        result = check_nose_over_margin(
            x_cg_fwd=2.0,
            x_main=2.5,
            x_nose=0.5,
            cg_height=1.2,
            braking_decel_g=0.4
        )
        
        # CG is 1.5 m aft of nose
        # Critical distance = 0.4 * 1.2 = 0.48 m
        # Should pass with good margin
        assert result.passed
    
    def test_ground_clearance_check(self):
        """Test ground clearance check."""
        result = check_ground_clearance(
            strut_length_m=0.5,
            stroke_m=0.2,
            tire_radius_m=0.2,
            prop_clearance_required_m=0.25,
            static_deflection_fraction=0.3
        )
        
        # Height = 0.5 + 0.2 - (0.2 * 0.3) = 0.64 m
        # Required = 0.25 m
        # Should pass
        assert result.passed
    
    def test_lateral_rollover_check(self):
        """Test lateral rollover stability check."""
        # Wide track, low CG - should pass easily
        result_stable = check_lateral_rollover(
            track_m=2.5,
            cg_height_m=1.2,
            min_rollover_angle_deg=25.0
        )
        
        # Rollover angle = atan(1.25/1.2) ≈ 46°
        assert result_stable.passed
        assert result_stable.margin_value > 25.0
        
        # Narrow track, high CG - may fail
        result_unstable = check_lateral_rollover(
            track_m=1.5,
            cg_height_m=2.0,
            min_rollover_angle_deg=25.0
        )
        
        # Rollover angle = atan(0.75/2.0) ≈ 20.5°
        assert not result_unstable.passed
    
    def test_tire_diameter_estimate(self):
        """Test tire diameter estimation from load."""
        # Light load
        min_d, max_d = estimate_tire_diameter(3000, "paved")
        assert 0.25 <= min_d <= 0.40
        assert min_d < max_d
        
        # Heavy load should need larger tires
        heavy_min, heavy_max = estimate_tire_diameter(15000, "paved")
        assert heavy_min > min_d


class TestUnitConversions:
    """Tests for unit conversion utilities."""
    
    def test_kg_to_N(self):
        """Test mass to weight conversion."""
        # 1 kg → ~9.81 N
        weight = kg_to_N(1.0)
        assert weight == pytest.approx(9.80665, rel=0.001)
        
        # 100 kg → ~981 N
        weight_100 = kg_to_N(100.0)
        assert weight_100 == pytest.approx(980.665, rel=0.001)
    
    def test_N_to_kg(self):
        """Test weight to mass conversion."""
        # ~9.81 N → 1 kg
        mass = N_to_kg(9.80665)
        assert mass == pytest.approx(1.0, rel=0.001)
    
    def test_roundtrip_conversion(self):
        """Test that kg→N→kg gives original value."""
        original = 123.45
        converted = N_to_kg(kg_to_N(original))
        assert converted == pytest.approx(original, rel=0.0001)

