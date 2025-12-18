"""
Landing gear candidate generator.

Creates and evaluates multiple gear configurations based on aircraft inputs.
This is for CONCEPTUAL SIZING ONLY - not for certification.
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
    CGSensitivity,
    ScoreBreakdown,
    RecommendationResult,
    SweepPoint,
    ConceptSweepResult,
    SweepResult,
)
from gearrec.physics import (
    calculate_touchdown_energy,
    calculate_required_shock_force,
    calculate_track_range,
    calculate_wheelbase_range,
    calculate_strut_length_range,
    check_tip_back_margin,
    check_nose_over_margin,
    kg_to_N,
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
)
from gearrec.physics.energy import recommend_stroke_range_for_aircraft
from gearrec.physics.tire_catalog import find_matching_tires, estimate_tire_dimensions
from gearrec.scoring.scorer import GearScorer


@dataclass
class CandidateConfig:
    """Configuration for a candidate gear concept."""
    config: GearConfig
    gear_type: GearType
    wheels_per_main_leg: int
    wheels_nose_or_tail: int
    stroke_m: float
    track_m: float
    wheelbase_m: float


class GearGenerator:
    """
    Generator for landing gear concept candidates.
    
    Creates multiple configurations (tricycle/taildragger, fixed/retract)
    and evaluates each against aircraft requirements.
    
    This is for CONCEPTUAL SIZING ONLY - not for certification.
    """
    
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
        
        # Get geometry estimates
        self.fuselage_length = inputs.get_fuselage_length_m()
        self.cg_height = inputs.get_cg_height_m()
        
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
        
        # Build assumptions list
        self.assumptions = self._build_assumptions()
    
    def _build_assumptions(self) -> list[str]:
        """Build list of assumptions used in calculations."""
        assumptions = []
        
        if self.inputs.fuselage_length_m is None:
            assumptions.append(
                f"Fuselage length estimated at {self.fuselage_length:.2f}m "
                f"from MTOW correlation (k*MTOW^(1/3))"
            )
        
        if self.inputs.cg_height_m is None:
            assumptions.append(
                f"CG height estimated at {self.cg_height:.2f}m "
                f"from weight and wing position correlation"
            )
        
        assumptions.extend([
            f"Touchdown energy: {self.touchdown_energy:.0f}J "
            f"(0.5 * {self.mlw_kg:.0f}kg * {self.inputs.sink_rate_mps:.1f}m/s²)",
            "Static load distribution assumes rigid body equilibrium",
            "Dynamic loads use simplified energy-based model (F_avg = E/stroke)",
            "Shock absorber efficiency assumed at 80%",
            f"Braking deceleration assumed at {self.inputs.brake_decel_g}g for nose-over check",
            "Tire sizing is approximate; actual selection requires manufacturer data",
        ])
        
        return assumptions
    
    def _build_input_summary(self) -> dict[str, float | str]:
        """Build summary of key input parameters used."""
        return {
            "mtow_kg": self.inputs.mtow_kg,
            "mlw_kg": self.mlw_kg,
            "cg_fwd_m": self.inputs.cg_fwd_m,
            "cg_aft_m": self.inputs.cg_aft_m,
            "cg_height_m": self.cg_height,
            "fuselage_length_m": self.fuselage_length,
            "landing_speed_mps": self.inputs.landing_speed_mps,
            "sink_rate_mps": self.inputs.sink_rate_mps,
            "runway": self.inputs.runway.value,
            "brake_decel_g": self.inputs.brake_decel_g,
        }
    
    def generate_candidates(self) -> list[GearConcept]:
        """
        Generate all candidate gear concepts.
        
        Returns:
            List of GearConcept objects, sorted by score (best first).
            Guarantees at least one tricycle candidate in results.
        """
        candidates = []
        tricycle_candidates = []
        
        # Generate all configuration combinations
        for config in self._get_valid_configs():
            concept = self._build_concept(config)
            if concept is not None:
                candidates.append(concept)
                if concept.config == GearConfig.TRICYCLE:
                    tricycle_candidates.append(concept)
        
        # Sort by score (descending)
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # Select top candidates, ensuring at least one tricycle
        result = []
        tricycle_included = False
        
        for c in candidates:
            if len(result) >= 6:
                break
            result.append(c)
            if c.config == GearConfig.TRICYCLE:
                tricycle_included = True
        
        # Guarantee at least one tricycle if we have any
        if not tricycle_included and tricycle_candidates:
            # Find best tricycle and add it
            best_tricycle = max(tricycle_candidates, key=lambda c: c.score)
            if len(result) >= 6:
                # Replace lowest-scoring non-tricycle
                for i in range(len(result) - 1, -1, -1):
                    if result[i].config != GearConfig.TRICYCLE:
                        result[i] = best_tricycle
                        break
            else:
                result.append(best_tricycle)
        
        # Ensure we have at least 3 candidates
        if len(result) < 3:
            result = candidates[:max(3, len(candidates))]
        
        # Re-sort
        result.sort(key=lambda c: c.score, reverse=True)
        
        return result[:6]
    
    def _get_valid_configs(self) -> Iterator[CandidateConfig]:
        """
        Generate valid configuration combinations.
        
        Yields candidate configurations based on input constraints.
        Samples geometry space to keep total candidates manageable (<60).
        """
        # Determine valid gear types
        if self.inputs.retractable:
            gear_types = [GearType.RETRACTABLE]
        else:
            gear_types = [GearType.FIXED, GearType.RETRACTABLE]
        
        # Get geometry ranges
        track_min, track_max = calculate_track_range(
            self.fuselage_length,
            self.inputs.runway.value,
            self.inputs.wing_low,
        )
        
        # Sample 2-3 values for each dimension
        stroke_samples = self._get_stroke_samples()  # 3 values
        track_samples = [track_min, (track_min + track_max) / 2, track_max]  # 3 values
        
        # Wheel configurations based on weight
        if self.inputs.mtow_kg < 1500:
            wheel_configs = [(1, 1)]
        elif self.inputs.mtow_kg < 4000:
            wheel_configs = [(1, 1), (2, 1)]
        else:
            wheel_configs = [(2, 1), (2, 2)]
        
        # Generate combinations for tricycle
        for gear_type in gear_types:
            wb_min, wb_max = calculate_wheelbase_range(self.fuselage_length, "tricycle")
            wheelbase_samples = [wb_min, (wb_min + wb_max) / 2, wb_max]
            
            for wheels_main, wheels_nose in wheel_configs:
                for stroke in stroke_samples:
                    for track in track_samples:
                        for wheelbase in wheelbase_samples:
                            yield CandidateConfig(
                                config=GearConfig.TRICYCLE,
                                gear_type=gear_type,
                                wheels_per_main_leg=wheels_main,
                                wheels_nose_or_tail=wheels_nose,
                                stroke_m=stroke,
                                track_m=track,
                                wheelbase_m=wheelbase,
                            )
        
        # Generate combinations for taildragger (fixed only usually)
        if GearType.FIXED in gear_types:
            wb_min, wb_max = calculate_wheelbase_range(self.fuselage_length, "taildragger")
            wheelbase_samples = [wb_min, (wb_min + wb_max) / 2]  # Fewer samples
            
            for wheels_main, _ in wheel_configs[:1]:  # Only single wheel for taildragger
                for stroke in stroke_samples[:2]:  # Fewer stroke samples
                    for track in track_samples[:2]:  # Fewer track samples
                        for wheelbase in wheelbase_samples:
                            yield CandidateConfig(
                                config=GearConfig.TAILDRAGGER,
                                gear_type=GearType.FIXED,
                                wheels_per_main_leg=wheels_main,
                                wheels_nose_or_tail=1,
                                stroke_m=stroke,
                                track_m=track,
                                wheelbase_m=wheelbase,
                            )
    
    def _get_stroke_samples(self) -> list[float]:
        """Get stroke values to sample based on recommended range."""
        min_s, max_s = self.stroke_range
        mid_s = (min_s + max_s) / 2
        return [min_s, mid_s, max_s]
    
    def _build_concept(
        self, 
        config: CandidateConfig,
        cg_position: float | None = None,
        sink_rate: float | None = None,
    ) -> GearConcept | None:
        """
        Build a complete gear concept from configuration.
        
        Args:
            config: Candidate configuration to evaluate
            cg_position: Optional specific CG position (for sweep), otherwise uses mid CG
            sink_rate: Optional specific sink rate (for sweep), otherwise uses input
            
        Returns:
            GearConcept if valid, None if fails hard constraints
        """
        # Use provided values or defaults
        cg_pos = cg_position if cg_position is not None else self.inputs.cg_mid_m
        sink = sink_rate if sink_rate is not None else self.inputs.sink_rate_mps
        
        try:
            # Calculate geometry
            geometry = self._calculate_geometry(config)
            
            # Calculate loads
            loads = self._calculate_loads(config, cg_pos, sink)
            
            # Calculate tire suggestions
            tire_suggestion = self._calculate_tire_suggestion(config, loads)
            
            # Run safety checks
            checks = self._run_checks(config, geometry, loads, tire_suggestion, cg_pos)
            
            # Check hard constraints
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
                assumptions=self.assumptions.copy(),
                input_summary=self._build_input_summary(),
                score=score,
                score_breakdown=breakdown,
            )
        except Exception as e:
            # Skip invalid candidates
            return None
    
    def _calculate_geometry(self, config: CandidateConfig) -> Geometry:
        """Calculate geometry ranges for the configuration."""
        # Use sampled values with small ranges
        track_tolerance = 0.1 * config.track_m
        wheelbase_tolerance = 0.1 * config.wheelbase_m
        stroke_tolerance = 0.05 * config.stroke_m
        
        # Strut lengths
        main_strut_min, main_strut_max = calculate_strut_length_range(
            self.inputs.mtow_kg,
            self.inputs.prop_clearance_m,
            is_main_gear=True,
        )
        
        nose_strut_min, nose_strut_max = calculate_strut_length_range(
            self.inputs.mtow_kg,
            prop_clearance_m=0.0,
            is_main_gear=False,
        )
        
        return Geometry(
            track_m=GeometryRange(
                min=config.track_m - track_tolerance,
                max=config.track_m + track_tolerance,
            ),
            wheelbase_m=GeometryRange(
                min=config.wheelbase_m - wheelbase_tolerance,
                max=config.wheelbase_m + wheelbase_tolerance,
            ),
            main_strut_length_m=GeometryRange(min=main_strut_min, max=main_strut_max),
            nose_or_tail_strut_length_m=GeometryRange(min=nose_strut_min, max=nose_strut_max),
            stroke_m=GeometryRange(
                min=config.stroke_m - stroke_tolerance,
                max=config.stroke_m + stroke_tolerance,
            ),
        )
    
    def _calculate_loads(
        self, 
        config: CandidateConfig, 
        cg_position: float,
        sink_rate: float,
    ) -> Loads:
        """Calculate load distribution for the configuration."""
        # Recalculate energy for this sink rate
        touchdown_energy = calculate_touchdown_energy(self.mlw_kg, sink_rate)
        
        # Get gear positions
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
            
            load_split = calculate_static_load_split_tricycle(
                self.weight_N, cg_position, x_main, x_nose,
            )
        else:
            x_main_min, x_main_max, x_tail_min, x_tail_max = estimate_gear_positions_taildragger(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
            )
            x_main = (x_main_min + x_main_max) / 2
            x_tail = (x_tail_min + x_tail_max) / 2
            
            load_split = calculate_static_load_split_taildragger(
                self.weight_N, cg_position, x_main, x_tail,
            )
        
        # Calculate per-wheel load
        main_load_per_wheel = calculate_main_load_per_wheel(
            load_split.main_load_total_N,
            config.wheels_per_main_leg,
        )
        
        # Calculate required shock force
        required_force = calculate_required_shock_force(
            touchdown_energy,
            config.stroke_m,
        )
        
        return Loads(
            weight_N=self.weight_N,
            static_nose_or_tail_load_N=load_split.nose_or_tail_load_N,
            static_main_load_total_N=load_split.main_load_total_N,
            static_main_load_per_wheel_N=main_load_per_wheel,
            landing_energy_J=touchdown_energy,
            required_avg_force_N=required_force,
            nose_load_fraction=load_split.nose_fraction,
        )
    
    def _calculate_tire_suggestion(
        self, 
        config: CandidateConfig, 
        loads: Loads
    ) -> TireSuggestion:
        """Calculate tire sizing suggestions."""
        dynamic_factor = calculate_dynamic_load_factor(
            self.inputs.sink_rate_mps,
            config.stroke_m,
        )
        
        static_req, dynamic_req = calculate_tire_load_requirements(
            loads.static_main_load_per_wheel_N,
            dynamic_factor,
        )
        
        # Get diameter and width ranges
        prefer_soft = self.inputs.runway in [RunwayType.GRASS, RunwayType.GRAVEL]
        diam_range, width_range = estimate_tire_dimensions(
            loads.static_main_load_per_wheel_N,
            self.inputs.runway.value,
            self.inputs.tire_pressure_limit_kpa,
        )
        
        # Find matching catalog tires
        matched_tires = find_matching_tires(
            dynamic_req,
            self.inputs.tire_pressure_limit_kpa,
            prefer_soft_field=prefer_soft,
            max_results=3,
        )
        
        return TireSuggestion(
            required_static_load_per_wheel_N=static_req,
            required_dynamic_load_per_wheel_N=dynamic_req,
            recommended_tire_diameter_range_m=diam_range,
            recommended_tire_width_range_m=width_range,
            matched_catalog_tires=matched_tires if matched_tires else None,
        )
    
    def _run_checks(
        self,
        config: CandidateConfig,
        geometry: Geometry,
        loads: Loads,
        tire: TireSuggestion,
        cg_position: float,
    ) -> Checks:
        """Run all safety and stability checks."""
        wheelbase = config.wheelbase_m
        
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
            
            # Tip-back check (use aft CG - worst case)
            tip_back = check_tip_back_margin(
                self.inputs.cg_aft_m, x_main, wheelbase, self.cg_height,
            )
            
            # Nose-over check (use forward CG - worst case)
            nose_over = check_nose_over_margin(
                self.inputs.cg_fwd_m, x_main, x_nose, self.cg_height,
                braking_decel_g=self.inputs.brake_decel_g,
            )
        else:
            x_main_min, x_main_max, x_tail_min, x_tail_max = estimate_gear_positions_taildragger(
                self.inputs.cg_fwd_m,
                self.inputs.cg_aft_m,
                self.fuselage_length,
                self.inputs.main_gear_attach_guess_m,
            )
            x_main = (x_main_min + x_main_max) / 2
            
            tip_back_margin = (self.inputs.cg_fwd_m - x_main) / wheelbase
            tip_back = CheckResult(
                passed=tip_back_margin > 0.05,
                value=tip_back_margin,
                limit=0.05,
                description=f"CG forward of main gear by {tip_back_margin*100:.1f}% of wheelbase",
            )
            
            nose_over = CheckResult(
                passed=True, value=1.0, limit=0.0,
                description="Nose-over check not applicable for taildragger",
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
        rollover_check = check_lateral_rollover(config.track_m, self.cg_height)
        
        prop_ok = clearance_check.passed if self.inputs.prop_clearance_m > 0 else True
        prop_margin = clearance_check.margin_value if self.inputs.prop_clearance_m > 0 else None
        
        # CG sensitivity analysis
        cg_sensitivity = self._analyze_cg_sensitivity(config, geometry, loads, tire)
        
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
            rollover_angle_deg=rollover_check.margin_value,
            prop_clearance_margin_m=prop_margin,
            cg_range_sensitivity=cg_sensitivity,
        )
    
    def _analyze_cg_sensitivity(
        self,
        config: CandidateConfig,
        geometry: Geometry,
        loads: Loads,
        tire: TireSuggestion,
    ) -> CGSensitivity:
        """Analyze how checks vary across CG range."""
        cg_positions = [
            (self.inputs.cg_fwd_m, "fwd"),
            (self.inputs.cg_mid_m, "mid"),
            (self.inputs.cg_aft_m, "aft"),
        ]
        
        pass_count = 0
        worst_score = float('inf')
        worst_pos = "mid"
        critical_check = None
        
        for cg, label in cg_positions:
            # Simplified check at each CG
            if config.config == GearConfig.TRICYCLE:
                x_nose_min, x_nose_max, x_main_min, x_main_max = estimate_gear_positions_tricycle(
                    self.inputs.cg_fwd_m, self.inputs.cg_aft_m, self.fuselage_length,
                    self.inputs.main_gear_attach_guess_m, self.inputs.nose_gear_attach_guess_m,
                )
                x_main = (x_main_min + x_main_max) / 2
                x_nose = (x_nose_min + x_nose_max) / 2
                
                tip_back = check_tip_back_margin(cg, x_main, config.wheelbase_m, self.cg_height)
                nose_over = check_nose_over_margin(
                    cg, x_main, x_nose, self.cg_height, self.inputs.brake_decel_g
                )
                
                all_pass = tip_back.passed and nose_over.passed
                if all_pass:
                    pass_count += 1
                
                score = min(tip_back.margin_value, nose_over.margin_value)
                if score < worst_score:
                    worst_score = score
                    worst_pos = label
                    if not tip_back.passed:
                        critical_check = "tip_back"
                    elif not nose_over.passed:
                        critical_check = "nose_over"
            else:
                pass_count += 1  # Taildragger less sensitive
        
        return CGSensitivity(
            pass_rate=pass_count / len(cg_positions),
            worst_case_position=worst_pos,
            critical_check=critical_check,
        )
    
    def _passes_hard_constraints(self, config: CandidateConfig, checks: Checks) -> bool:
        """Check if configuration passes hard constraints."""
        if self.inputs.retractable and config.gear_type == GearType.FIXED:
            return False
        if not checks.prop_clearance_ok:
            return False
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
        
        if config.config == GearConfig.TRICYCLE:
            explanation.append("Tricycle configuration provides good forward visibility and ground handling")
        else:
            explanation.append("Taildragger configuration offers simplicity and lighter weight")
        
        if config.gear_type == GearType.FIXED:
            explanation.append("Fixed gear selected for simplicity, lower cost, and easier maintenance")
        else:
            explanation.append("Retractable gear reduces drag for higher cruise performance")
        
        if config.wheels_per_main_leg == 1:
            explanation.append("Single wheel per main leg appropriate for aircraft weight class")
        else:
            explanation.append("Dual wheels per main leg distribute load for longer tire life")
        
        if self.inputs.runway == RunwayType.GRASS:
            explanation.append("Wider tires recommended for grass operations")
        elif self.inputs.runway == RunwayType.GRAVEL:
            explanation.append("Robust tire sizing for gravel runway operations")
        
        nose_pct = loads.nose_load_fraction * 100
        if 8 <= nose_pct <= 15:
            explanation.append(f"Nose load fraction of {nose_pct:.1f}% is within ideal range (8-15%)")
        elif nose_pct < 8:
            explanation.append(f"Nose load fraction of {nose_pct:.1f}% is low; steering may be light")
        else:
            explanation.append(f"Nose load fraction of {nose_pct:.1f}% is high; consider geometry changes")
        
        if checks.tip_back_margin.passed and checks.nose_over_margin.passed:
            explanation.append("All stability margins within acceptable limits")
        else:
            if not checks.tip_back_margin.passed:
                explanation.append("WARNING: Tip-back margin is marginal")
            if not checks.nose_over_margin.passed:
                explanation.append("WARNING: Nose-over margin under braking is marginal")
        
        return explanation
    
    def generate_result(self) -> RecommendationResult:
        """Generate complete recommendation result."""
        concepts = self.generate_candidates()
        
        input_summary = self._build_input_summary()
        input_summary["retractable_required"] = self.inputs.retractable
        
        warnings = []
        if not any(c.all_checks_passed for c in concepts):
            warnings.append("No configurations pass all safety checks; review geometry constraints")
        if self.inputs.sink_rate_mps > 3.0:
            warnings.append(f"High sink rate ({self.inputs.sink_rate_mps} m/s) may require reinforced structure")
        if self.inputs.runway in [RunwayType.GRASS, RunwayType.GRAVEL]:
            warnings.append(f"{self.inputs.runway.value.title()} runway may require larger tires than shown")
        
        return RecommendationResult(
            aircraft_name=self.inputs.aircraft_name,
            input_summary=input_summary,
            concepts=concepts,
            assumptions=self.assumptions,
            warnings=warnings,
        )
    
    def run_sweep(
        self,
        sink_rates: list[float] | None = None,
        cg_positions: list[float] | None = None,
    ) -> SweepResult:
        """
        Run sensitivity sweep across sink rates and CG positions.
        
        Args:
            sink_rates: List of sink rates to evaluate. If None, uses default range.
            cg_positions: List of CG positions. If None, uses fwd/mid/aft.
            
        Returns:
            SweepResult with pass rates and scores for each concept.
        """
        # Default sweep parameters
        if sink_rates is None:
            base_sink = self.inputs.sink_rate_mps
            sink_rates = [
                max(1.0, base_sink - 0.5),
                base_sink,
                min(4.0, base_sink + 0.5),
                min(4.5, base_sink + 1.0),
            ]
        
        if cg_positions is None:
            cg_positions = [
                self.inputs.cg_fwd_m,
                self.inputs.cg_mid_m,
                self.inputs.cg_aft_m,
            ]
        
        cg_labels = {
            self.inputs.cg_fwd_m: "fwd",
            self.inputs.cg_mid_m: "mid",
            self.inputs.cg_aft_m: "aft",
        }
        
        # Get unique configurations to sweep
        base_candidates = self.generate_candidates()
        
        concept_results = []
        
        for concept in base_candidates:
            # Find matching config
            config = CandidateConfig(
                config=concept.config,
                gear_type=concept.gear_type,
                wheels_per_main_leg=concept.wheel_count_main,
                wheels_nose_or_tail=concept.wheel_count_nose_or_tail,
                stroke_m=concept.geometry.stroke_m.mid,
                track_m=concept.geometry.track_m.mid,
                wheelbase_m=concept.geometry.wheelbase_m.mid,
            )
            
            sweep_points = []
            
            for sink in sink_rates:
                for cg in cg_positions:
                    # Rebuild concept at this point
                    test_concept = self._build_concept(config, cg_position=cg, sink_rate=sink)
                    
                    if test_concept is None:
                        sweep_points.append(SweepPoint(
                            sink_rate_mps=sink,
                            cg_position_m=cg,
                            cg_label=cg_labels.get(cg, f"{cg:.2f}m"),
                            all_checks_passed=False,
                            score=0.0,
                            failed_checks=["build_failed"],
                        ))
                    else:
                        failed = []
                        if not test_concept.checks.tip_back_margin.passed:
                            failed.append("tip_back")
                        if not test_concept.checks.nose_over_margin.passed:
                            failed.append("nose_over")
                        if not test_concept.checks.ground_clearance_ok:
                            failed.append("ground_clearance")
                        if not test_concept.checks.lateral_stability_ok:
                            failed.append("lateral_stability")
                        if not test_concept.checks.prop_clearance_ok:
                            failed.append("prop_clearance")
                        
                        sweep_points.append(SweepPoint(
                            sink_rate_mps=sink,
                            cg_position_m=cg,
                            cg_label=cg_labels.get(cg, f"{cg:.2f}m"),
                            all_checks_passed=test_concept.all_checks_passed,
                            score=test_concept.score,
                            failed_checks=failed,
                        ))
            
            # Calculate statistics
            scores = [p.score for p in sweep_points]
            pass_count = sum(1 for p in sweep_points if p.all_checks_passed)
            
            concept_results.append(ConceptSweepResult(
                config=concept.config,
                gear_type=concept.gear_type,
                pass_rate=pass_count / len(sweep_points) if sweep_points else 0,
                avg_score=sum(scores) / len(scores) if scores else 0,
                worst_case_score=min(scores) if scores else 0,
                best_case_score=max(scores) if scores else 0,
                sweep_points=sweep_points,
            ))
        
        # Find most robust
        most_robust = max(concept_results, key=lambda r: r.pass_rate)
        most_robust_name = f"{most_robust.config.value}_{most_robust.gear_type.value}"
        
        return SweepResult(
            aircraft_name=self.inputs.aircraft_name,
            sink_rates_swept=sink_rates,
            cg_positions_swept=cg_positions,
            concept_results=concept_results,
            most_robust_concept=most_robust_name,
            warnings=[],
        )
