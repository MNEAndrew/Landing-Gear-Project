"""
Scoring system for landing gear concepts.

Evaluates concepts based on:
- Safety check pass/fail
- Design priorities (robustness, drag, mass, simplicity)
- Runway type compatibility
"""

from gearrec.models.inputs import DesignPriorities, RunwayType
from gearrec.models.outputs import (
    GearConfig,
    GearType,
    Checks,
    Loads,
    Geometry,
    ScoreBreakdown,
)


class GearScorer:
    """
    Scores landing gear concepts based on design priorities.
    
    Scoring Philosophy:
    - Each criterion is scored 0.0 to 1.0
    - Final score is weighted average based on design priorities
    - Failed safety checks apply multiplicative penalties
    """
    
    # Penalty factors for failed checks
    FAILED_CHECK_PENALTY = 0.5  # Multiply score by this for each failed check
    MARGINAL_CHECK_PENALTY = 0.8  # For checks that barely pass
    
    def __init__(self, priorities: DesignPriorities):
        """
        Initialize scorer with design priorities.
        
        Args:
            priorities: Weights for scoring criteria
        """
        self.priorities = priorities
        self.weights = priorities.normalized()
    
    def score_concept(
        self,
        config: GearConfig,
        gear_type: GearType,
        checks: Checks,
        loads: Loads,
        geometry: Geometry,
        runway_type: RunwayType,
    ) -> tuple[float, ScoreBreakdown]:
        """
        Score a gear concept.
        
        Args:
            config: Tricycle or taildragger
            gear_type: Fixed or retractable
            checks: Safety check results
            loads: Load calculations
            geometry: Geometry ranges
            runway_type: Primary runway surface
            
        Returns:
            Tuple of (overall_score, breakdown)
        """
        # Calculate individual scores
        robustness = self._score_robustness(config, gear_type, geometry, runway_type)
        low_drag = self._score_drag(gear_type, config, geometry)
        low_mass = self._score_mass(gear_type, geometry, loads)
        simplicity = self._score_simplicity(config, gear_type)
        
        # Calculate checks penalty
        checks_penalty = self._calculate_checks_penalty(checks)
        
        # Build breakdown
        breakdown = ScoreBreakdown(
            robustness=robustness,
            low_drag=low_drag,
            low_mass=low_mass,
            simplicity=simplicity,
            checks_penalty=checks_penalty,
        )
        
        # Calculate weighted score
        weighted_score = (
            self.weights["robustness"] * robustness +
            self.weights["low_drag"] * low_drag +
            self.weights["low_mass"] * low_mass +
            self.weights["simplicity"] * simplicity
        )
        
        # Apply checks penalty
        final_score = weighted_score * (1.0 - checks_penalty)
        
        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))
        
        return (final_score, breakdown)
    
    def _score_robustness(
        self,
        config: GearConfig,
        gear_type: GearType,
        geometry: Geometry,
        runway_type: RunwayType,
    ) -> float:
        """
        Score for robustness/reliability.
        
        Factors:
        - Fixed gear is more robust than retractable
        - Wider track is more stable
        - Longer stroke absorbs more energy
        - Tricycle more robust on runway than taildragger
        """
        score = 0.5  # Base score
        
        # Fixed gear is more robust
        if gear_type == GearType.FIXED:
            score += 0.15
        
        # Configuration robustness
        if config == GearConfig.TRICYCLE:
            score += 0.10  # More stable on runway
        
        # Track width contribution (wider = more stable)
        track_mid = geometry.track_m.mid
        if track_mid >= 2.5:
            score += 0.15
        elif track_mid >= 2.0:
            score += 0.10
        elif track_mid >= 1.5:
            score += 0.05
        
        # Stroke contribution (more stroke = better energy absorption)
        stroke_mid = geometry.stroke_m.mid
        if stroke_mid >= 0.25:
            score += 0.10
        elif stroke_mid >= 0.18:
            score += 0.05
        
        # Runway type bonus (grass/gravel needs more robustness)
        if runway_type in [RunwayType.GRASS, RunwayType.GRAVEL]:
            # Penalize if track is narrow for soft field
            if track_mid < 2.0:
                score -= 0.10
            if stroke_mid < 0.18:
                score -= 0.05
        
        return max(0.0, min(1.0, score))
    
    def _score_drag(
        self,
        gear_type: GearType,
        config: GearConfig,
        geometry: Geometry,
    ) -> float:
        """
        Score for aerodynamic efficiency (low drag).
        
        Factors:
        - Retractable gear has much lower drag
        - Smaller frontal area is better
        - Shorter struts when extended
        """
        score = 0.5  # Base score
        
        # Retractable is the big win for drag
        if gear_type == GearType.RETRACTABLE:
            score += 0.40  # Major drag reduction
        
        # Fixed gear drag varies with configuration
        if gear_type == GearType.FIXED:
            # Taildragger has slightly less drag (no nose gear)
            if config == GearConfig.TAILDRAGGER:
                score += 0.05
            
            # Shorter struts = smaller frontal area
            strut_mid = geometry.main_strut_length_m.mid
            if strut_mid < 0.45:
                score += 0.10
            elif strut_mid < 0.55:
                score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def _score_mass(
        self,
        gear_type: GearType,
        geometry: Geometry,
        loads: Loads,
    ) -> float:
        """
        Score for low mass.
        
        Factors:
        - Fixed gear is lighter than retractable
        - Shorter struts are lighter
        - Smaller required forces = lighter structure
        """
        score = 0.5  # Base score
        
        # Fixed gear is lighter (no actuation, simpler structure)
        if gear_type == GearType.FIXED:
            score += 0.20
        
        # Shorter struts = lighter
        strut_mid = geometry.main_strut_length_m.mid
        if strut_mid < 0.45:
            score += 0.15
        elif strut_mid < 0.55:
            score += 0.10
        elif strut_mid < 0.65:
            score += 0.05
        
        # Lower loads = lighter structure
        # Normalize by typical GA loads (~50kN total for 1500kg aircraft)
        load_ratio = loads.static_main_load_total_N / 50000
        if load_ratio < 0.8:
            score += 0.10
        elif load_ratio < 1.2:
            score += 0.05
        elif load_ratio > 1.5:
            score -= 0.05
        
        return max(0.0, min(1.0, score))
    
    def _score_simplicity(
        self,
        config: GearConfig,
        gear_type: GearType,
    ) -> float:
        """
        Score for design simplicity.
        
        Factors:
        - Fixed gear is simpler
        - Taildragger is simpler (less structure)
        - Single wheel per leg is simpler
        """
        score = 0.5  # Base score
        
        # Fixed gear is much simpler
        if gear_type == GearType.FIXED:
            score += 0.30
        
        # Configuration simplicity
        if config == GearConfig.TAILDRAGGER:
            score += 0.10  # Simpler overall structure
        elif config == GearConfig.TRICYCLE:
            score += 0.05  # More parts but proven design
        
        return max(0.0, min(1.0, score))
    
    def _calculate_checks_penalty(self, checks: Checks) -> float:
        """
        Calculate penalty factor from failed checks.
        
        Returns:
            Penalty as fraction (0.0 = no penalty, up to ~0.5 for failures)
        """
        penalty = 0.0
        
        # Tip-back margin
        if not checks.tip_back_margin.passed:
            penalty += 0.15
        elif checks.tip_back_margin.value < checks.tip_back_margin.limit * 1.2:
            penalty += 0.05  # Marginal pass
        
        # Nose-over margin
        if not checks.nose_over_margin.passed:
            penalty += 0.15
        elif checks.nose_over_margin.value < checks.nose_over_margin.limit * 1.2:
            penalty += 0.05
        
        # Ground clearance
        if not checks.ground_clearance_ok:
            penalty += 0.20
        
        # Lateral stability
        if not checks.lateral_stability_ok:
            penalty += 0.10
        
        # Prop clearance
        if not checks.prop_clearance_ok:
            penalty += 0.25  # Critical safety issue
        
        return min(0.8, penalty)  # Cap at 80% penalty

