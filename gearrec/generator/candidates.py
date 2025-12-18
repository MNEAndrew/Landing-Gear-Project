"""
Landing gear candidate generator.

Creates and evaluates multiple gear configurations based on aircraft inputs.
"""

from dataclasses import dataclass
from typing import Iterator

from gearrec.models.inputs import AircraftInputs, RunwayType
from gearrec.models.outputs import (
    GearConcept,
    GearConfig,
    GearType,
    GeometryRange,
    Geometry,
    TireSuggestion,
    Loads,
    CheckResult,
    Checks,
    ScoreBreakdown,
    RecommendationResult,
)
from gearrec.physics import (
    calculate_touchdown_energy,
    calculate_required_shock_force,
    estimate_fuselage_length,
    calculate_track_range,
    calculate_wheelbase_range,
    calculate_strut_length_range,
    estimate_cg_height,
    check_tip_back_margin,
    check_nose_over_margin,
)
from gearrec.physics.loads import (
    calculate_static_load_split_tricycle,
    calculate_static_load_split_taildragger,
    calculate_dynamic_load_factor,
    calculate_tire_load_requirements,
    estimate_gear_positions_tricycle,
    estimate_gear_positions_taildragger,
    calculate_main_load_per_wheel,
)
from gearrec.physics.geometry import (
    check_ground_clearance,
    check_lateral_rollover,
    estimate_tire_diameter,
)
from gearrec.physics.energy import recommend_stroke_range_for_aircraft
from gearrec.physics.units import kg_to_N
from gearrec.scoring.scorer import GearScorer


@dataclass
class CandidateConfig:
    """Configuration for a candidate gear concept."""
    config: GearConfig
    gear_type: GearType
    wheels_per_main_leg: int
    wheels_nose_or_tail: int
    stroke_m: float  # Specific stroke value for this candidate


class GearGenerator:
    """
    Generator for landing gear concept candidates.
    
    Creates multiple configurations (tricycle/taildragger, fixed/retract)
    and evaluates each against aircraft requirements.
    """
    
    # Stroke values to sample (will pick best from these)
    STROKE_SAMPLES = [0.12, 0.18, 0.22, 0.28]
    
    def __init__(self, inputs: AircraftInputs):
        """
        Initialize generator with aircraft inputs.
        
        Args:
            inputs: Aircraft parameters for sizing
        """
        self.inputs = inputs
        self.scorer = GearScorer(inputs.design_priorities)
        
        # Pre-compute common values
        self.mlw_kg = inputs.get_mlw_kg()
        self.weight_N = kg_to_N(self.mlw_kg)
        self.mtow_weight_N = kg_to_N(inputs.mtow_kg)
        
        # Estimate basic geometry
        self.fuselage_length = estimate_fuselage_length(inputs.mtow_kg)
        self.cg_height = estimate_cg_height(inputs.mtow_kg, inputs.wing_low)
        
        # Landing energy
        self.touchdown_energy = calculate_touchdown_energy(
            self.mlw_kg, inputs.sink_rate_mps
        )
        
        # Get recommended stroke range
        self.stroke_range = recommend_stroke_range_for_aircraft(
            inputs.mtow_kg,
            inputs.sink_rate_mps,
            inputs.runway.value,
        )
    
    def generate_candidates(self) -> list[GearConcept]:
        """
        Generate all candidate gear concepts.
        
        Returns:
            List of GearConcept objects, sorted by score (best first)
        """
        candidates = []
        
        # Generate all configuration combinations
        for config in self._get_valid_configs():
            concept = self._build_concept(config)
            if concept is not None:
                candidates.append(concept)
        
        # Sort by score (descending)
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # Return top 3-6 candidates
        # Keep at least 3, up to 6, and include all that pass checks
        passing = [c for c in candidates if c.all_checks_passed]
        
        if len(passing) >= 6:
            return passing[:6]
        elif len(passing) >= 3:
            return passing
        else:
            # Include some failing candidates if we don't have enough passing
            return candidates[:max(3, min(6, len(candidates)))]
    
    def _get_valid_configs(self) -> Iterator[CandidateConfig]:
        """
        Generate valid configuration combinations.
        
        Yields candidate configurations based on input constraints.
        """
        # Determine valid gear types
        gear_types = [GearType.RETRACTABLE] if self.inputs.retractable else [
            GearType.FIXED, GearType.RETRACTABLE
        ]
        
        # Determine stroke values to sample
        stroke_samples = self._get_stroke_samples()
        
        # Wheel configurations based on weight
        if self.inputs.mtow_kg < 1500:
            wheel_configs = [(1, 1)]  # Single wheel per leg, single nose
        elif self.inputs.mtow_kg < 4000:
            wheel_configs = [(1, 1), (2, 1)]  # Single or dual main
        else:
            wheel_configs = [(2, 1), (2, 2)]  # Dual wheels
        
        # Generate combinations
        for gear_type in gear_types:
            for wheels_main, wheels_nose in wheel_configs:
                for stroke in stroke_samples:
                    # Tricycle configurations
                    yield CandidateConfig(
                        config=GearConfig.TRICYCLE,
                        gear_type=gear_type,
                        wheels_per_main_leg=wheels_main,
                        wheels_nose_or_tail=wheels_nose,
                        stroke_m=stroke,
                    )
                    
                    # Taildragger configurations (only if no retractable requirement)
                    # Taildraggers are less common with retractable gear
                    if gear_type == GearType.FIXED:
                        yield CandidateConfig(
                            config=GearConfig.TAILDRAGGER,
                            gear_type=gear_type,
                            wheels_per_main_leg=wheels_main,
                            wheels_nose_or_tail=1,  # Tail wheel always single
                            stroke_m=stroke,
                        )
    
    def _get_stroke_samples(self) -> list[float]:
        """Get stroke values to sample based on recommended range."""
        min_s, max_s = self.stroke_range
        
        # Generate 3 samples within the recommended range
        if max_s - min_s < 0.05:
            return [min_s, (min_s + max_s) / 2, max_s]
        else:
            step = (max_s - min_s) / 2
            return [min_s, min_s + step, max_s]
    
    def _build_concept(self, config: CandidateConfig) -> GearConcept | None:
        """
        Build a complete gear concept from configuration.
        
        Args:
            config: Candidate configuration to evaluate
            
        Returns:
            GearConcept if valid, None if fails hard constraints
        """
        try:
            # Calculate geometry
            geometry = self._calculate_geometry(config)
            
            # Calculate loads
            loads = self._calculate_loads(config, geometry)
            
            # Calculate tire suggestions
            tire_suggestion = self._calculate_tire_suggestion(config, loads)
            
            # Run safety checks
            checks = self._run_checks(config, geometry, loads, tire_suggestion)
            
            # Check hard constraints (reject if failed)
            if not self._passes_hard_constraints(config, checks):
                return None
            
            # Generate explanation
            explanation = self._generate_explanation(config, geometry, loads, checks)
            
            # Calculate score
            score, breakdown = self.scorer.score_concept(
                config=config.config,
                gear_type=config.gear_type,
                checks=checks,
                loads=loads,
                geometry=geometry,
                runway_type=self.inputs.runway,
            )
            
            return GearConcept(
                config=config.config,
                gear_type=config.gear_type,
                wheel_count_main=config.wheels_per_main_leg,
                wheel_count_nose_or_tail=config.wheels_nose_or_tail,
                geometry=geometry,
                tire_suggestion=tire_suggestion,
                loads=loads,
                checks=checks,
                explanation=explanation,
                score=score,
                score_breakdown=breakdown,
            )
        except Exception as e:
            # Log error but don't crash - just skip this candidate
            print(f"Warning: Failed to build concept {config}: {e}")
            return None
    
    def _calculate_geometry(self, config: CandidateConfig) -> Geometry:
        """Calculate geometry ranges for the configuration."""
        # Track range
        track_min, track_max = calculate_track_range(
            self.fuselage_length,
            self.inputs.runway.value,
            self.inputs.wing_low,
        )
        
        # Wheelbase range
        wheelbase_min, wheelbase_max = calculate_wheelbase_range(
            self.fuselage_length,
            config.config.value,
        )
        
        # Strut lengths
        main_strut_min, main_strut_max = calculate_strut_length_range(
            self.inputs.mtow_kg,
            self.inputs.prop_clearance_m,
            is_main_gear=True,
        )
        
        nose_strut_min, nose_strut_max = calculate_strut_length_range(
            self.inputs.mtow_kg,
            prop_clearance_m=0.0,  # Nose gear doesn't need prop clearance
            is_main_gear=False,
        )
        
        # Stroke (use specific value with small range)
        stroke_min = config.stroke_m * 0.9
        stroke_max = config.stroke_m * 1.1
        
        return Geometry(
            track_m=GeometryRange(min=track_min, max=track_max),
            wheelbase_m=GeometryRange(min=wheelbase_min, max=wheelbase_max),
            main_strut_length_m=GeometryRange(min=main_strut_min, max=main_strut_max),
            nose_or_tail_strut_length_m=GeometryRange(min=nose_strut_min, max=nose_strut_max),
            stroke_m=GeometryRange(min=stroke_min, max=stroke_max),
        )
    
    def _calculate_loads(self, config: CandidateConfig, geometry: Geometry) -> Loads:
        """Calculate load distribution for the configuration."""
        # Get gear positions
        if config.config == GearConfig.TRICYCLE:
            x_nose_min, x_nose_max, x_main_min, x_main_max = estimate_gear_positions_tricycle(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
                self.inputs.nose_gear_attach_guess_m,
            )
            
            # Use mid-range positions for load calculation
            x_nose = (x_nose_min + x_nose_max) / 2
            x_main = (x_main_min + x_main_max) / 2
            
            # Calculate static loads at worst-case CG (aft for nose load)
            load_split = calculate_static_load_split_tricycle(
                self.weight_N,
                self.inputs.cg_mid_m,  # Use mid CG for typical case
                x_main,
                x_nose,
            )
        else:
            # Taildragger
            x_main_min, x_main_max, x_tail_min, x_tail_max = estimate_gear_positions_taildragger(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
            )
            
            x_main = (x_main_min + x_main_max) / 2
            x_tail = (x_tail_min + x_tail_max) / 2
            
            load_split = calculate_static_load_split_taildragger(
                self.weight_N,
                self.inputs.cg_mid_m,
                x_main,
                x_tail,
            )
        
        # Calculate per-wheel load
        main_load_per_wheel = calculate_main_load_per_wheel(
            load_split.main_load_total_N,
            config.wheels_per_main_leg,
        )
        
        # Calculate required shock force
        required_force = calculate_required_shock_force(
            self.touchdown_energy,
            config.stroke_m,
        )
        
        return Loads(
            static_nose_or_tail_load_N=load_split.nose_or_tail_load_N,
            static_main_load_total_N=load_split.main_load_total_N,
            static_main_load_per_wheel_N=main_load_per_wheel,
            landing_energy_J=self.touchdown_energy,
            required_avg_force_N=required_force,
            nose_load_fraction=load_split.nose_fraction,
        )
    
    def _calculate_tire_suggestion(
        self, 
        config: CandidateConfig, 
        loads: Loads
    ) -> TireSuggestion:
        """Calculate tire sizing suggestions."""
        # Dynamic load factor
        dynamic_factor = calculate_dynamic_load_factor(
            self.inputs.sink_rate_mps,
            config.stroke_m,
        )
        
        # Required tire loads
        static_req, dynamic_req = calculate_tire_load_requirements(
            loads.static_main_load_per_wheel_N,
            dynamic_factor,
        )
        
        # Tire diameter range
        diam_min, diam_max = estimate_tire_diameter(
            loads.static_main_load_per_wheel_N,
            self.inputs.runway.value,
            self.inputs.tire_pressure_limit_kpa,
        )
        
        # Suggested width for soft field
        suggested_width = None
        if self.inputs.runway in [RunwayType.GRASS, RunwayType.GRAVEL]:
            # Wider tires for soft field (roughly 35-45% of diameter)
            suggested_width = (diam_min + diam_max) / 2 * 0.40
        
        return TireSuggestion(
            required_static_load_per_wheel_N=static_req,
            required_dynamic_load_per_wheel_N=dynamic_req,
            recommended_tire_diameter_range_m=GeometryRange(min=diam_min, max=diam_max),
            suggested_tire_width_m=suggested_width,
        )
    
    def _run_checks(
        self,
        config: CandidateConfig,
        geometry: Geometry,
        loads: Loads,
        tire: TireSuggestion,
    ) -> Checks:
        """Run all safety and stability checks."""
        # Get gear positions for checks
        wheelbase = geometry.wheelbase_m.mid
        
        if config.config == GearConfig.TRICYCLE:
            x_nose_min, x_nose_max, x_main_min, x_main_max = estimate_gear_positions_tricycle(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
                self.inputs.nose_gear_attach_guess_m,
            )
            x_nose = (x_nose_min + x_nose_max) / 2
            x_main = (x_main_min + x_main_max) / 2
            
            # Tip-back check (use aft CG)
            tip_back = check_tip_back_margin(
                self.inputs.cg_aft_m,
                x_main,
                wheelbase,
                self.cg_height,
            )
            
            # Nose-over check (use forward CG)
            nose_over = check_nose_over_margin(
                self.inputs.cg_fwd_m,
                x_main,
                x_nose,
                self.cg_height,
            )
        else:
            # Taildragger checks are different
            x_main_min, x_main_max, x_tail_min, x_tail_max = estimate_gear_positions_taildragger(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
            )
            x_main = (x_main_min + x_main_max) / 2
            x_tail = (x_tail_min + x_tail_max) / 2
            
            # For taildragger, tip-back isn't the same concern
            # Main concern is CG behind main gear for stability
            tip_back_margin = (self.inputs.cg_fwd_m - x_main) / wheelbase
            tip_back = CheckResult(
                passed=tip_back_margin > 0.05,
                value=tip_back_margin,
                limit=0.05,
                description=f"CG forward of main gear by {tip_back_margin*100:.1f}% of wheelbase",
            )
            
            # Nose-over not applicable for taildragger
            nose_over = CheckResult(
                passed=True,
                value=1.0,
                limit=0.0,
                description="Nose-over check not applicable for taildragger configuration",
            )
        
        # Ground clearance check
        tire_radius = tire.recommended_tire_diameter_range_m.mid / 2
        clearance_check = check_ground_clearance(
            geometry.main_strut_length_m.mid,
            geometry.stroke_m.mid,
            tire_radius,
            self.inputs.prop_clearance_m,
        )
        
        # Lateral rollover check
        rollover_check = check_lateral_rollover(
            geometry.track_m.mid,
            self.cg_height,
        )
        
        # Prop clearance (separate from general ground clearance)
        if self.inputs.prop_clearance_m > 0:
            prop_ok = clearance_check.passed
        else:
            prop_ok = True
        
        return Checks(
            tip_back_margin=CheckResult(
                passed=tip_back.passed,
                value=tip_back.margin_value,
                limit=tip_back.required_margin,
                description=tip_back.description,
            ),
            nose_over_margin=CheckResult(
                passed=nose_over.passed,
                value=nose_over.margin_value,
                limit=nose_over.required_margin,
                description=nose_over.description,
            ),
            ground_clearance_ok=clearance_check.passed,
            lateral_stability_ok=rollover_check.passed,
            prop_clearance_ok=prop_ok,
        )
    
    def _passes_hard_constraints(
        self, 
        config: CandidateConfig, 
        checks: Checks
    ) -> bool:
        """
        Check if configuration passes hard constraints.
        
        Hard constraints cause rejection, soft constraints affect score.
        """
        # Retractable requirement
        if self.inputs.retractable and config.gear_type == GearType.FIXED:
            return False
        
        # Prop clearance is a hard constraint
        if not checks.prop_clearance_ok:
            return False
        
        # Allow concepts with marginal checks to proceed (will be scored lower)
        return True
    
    def _generate_explanation(
        self,
        config: CandidateConfig,
        geometry: Geometry,
        loads: Loads,
        checks: Checks,
    ) -> list[str]:
        """Generate explanation bullet points for the concept."""
        explanation = []
        
        # Configuration rationale
        if config.config == GearConfig.TRICYCLE:
            explanation.append(
                "Tricycle configuration provides good forward visibility and ground handling"
            )
        else:
            explanation.append(
                "Taildragger configuration offers simplicity and lighter weight"
            )
        
        # Gear type rationale
        if config.gear_type == GearType.FIXED:
            explanation.append(
                "Fixed gear selected for simplicity, lower cost, and easier maintenance"
            )
        else:
            explanation.append(
                "Retractable gear reduces drag for higher cruise performance"
            )
        
        # Wheel count rationale
        if config.wheels_per_main_leg == 1:
            explanation.append(
                "Single wheel per main leg appropriate for aircraft weight class"
            )
        else:
            explanation.append(
                "Dual wheels per main leg distribute load for longer tire life"
            )
        
        # Runway considerations
        if self.inputs.runway == RunwayType.GRASS:
            explanation.append(
                "Larger tires and wider track recommended for grass operations"
            )
        elif self.inputs.runway == RunwayType.GRAVEL:
            explanation.append(
                "Robust tire sizing and longer stroke for gravel runway operations"
            )
        
        # Load distribution note
        nose_pct = loads.nose_load_fraction * 100
        if 8 <= nose_pct <= 15:
            explanation.append(
                f"Nose load fraction of {nose_pct:.1f}% is within ideal range (8-15%)"
            )
        elif nose_pct < 8:
            explanation.append(
                f"Nose load fraction of {nose_pct:.1f}% is low; consider moving main gear aft"
            )
        else:
            explanation.append(
                f"Nose load fraction of {nose_pct:.1f}% is high; consider moving main gear forward"
            )
        
        # Check results
        if checks.tip_back_margin.passed and checks.nose_over_margin.passed:
            explanation.append("All stability margins within acceptable limits")
        else:
            if not checks.tip_back_margin.passed:
                explanation.append("WARNING: Tip-back margin is marginal")
            if not checks.nose_over_margin.passed:
                explanation.append("WARNING: Nose-over margin under braking is marginal")
        
        return explanation
    
    def generate_result(self) -> RecommendationResult:
        """
        Generate complete recommendation result.
        
        Returns:
            RecommendationResult with all concepts and metadata
        """
        concepts = self.generate_candidates()
        
        # Build input summary
        input_summary = {
            "mtow_kg": self.inputs.mtow_kg,
            "mlw_kg": self.mlw_kg,
            "cg_range_m": f"{self.inputs.cg_fwd_m:.2f} - {self.inputs.cg_aft_m:.2f}",
            "landing_speed_mps": self.inputs.landing_speed_mps,
            "sink_rate_mps": self.inputs.sink_rate_mps,
            "runway": self.inputs.runway.value,
            "retractable_required": self.inputs.retractable,
        }
        
        # Document key assumptions
        assumptions = [
            f"Fuselage length estimated at {self.fuselage_length:.2f}m from MTOW correlation",
            f"CG height estimated at {self.cg_height:.2f}m from weight and wing position",
            f"Touchdown energy: {self.touchdown_energy:.0f}J from sink rate {self.inputs.sink_rate_mps} m/s",
            "Static load distribution assumes rigid body equilibrium",
            "Dynamic loads use simplified energy-based model",
            "Shock absorber efficiency assumed at 80%",
            "Braking deceleration assumed at 0.4g for nose-over check",
        ]
        
        # Generate warnings
        warnings = []
        
        if not any(c.all_checks_passed for c in concepts):
            warnings.append(
                "No configurations pass all safety checks; review geometry constraints"
            )
        
        if self.inputs.sink_rate_mps > 3.0:
            warnings.append(
                f"High sink rate ({self.inputs.sink_rate_mps} m/s) may require reinforced structure"
            )
        
        if self.inputs.runway in [RunwayType.GRASS, RunwayType.GRAVEL]:
            warnings.append(
                f"{self.inputs.runway.value.title()} runway operation may require larger tires than shown"
            )
        
        return RecommendationResult(
            aircraft_name=self.inputs.aircraft_name,
            input_summary=input_summary,
            concepts=concepts,
            assumptions=assumptions,
            warnings=warnings,
        )

