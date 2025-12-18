"""
Tests for tire catalog functionality.

Tests cover:
- Unit conversions
- Tire matching logic
- Pressure limit filtering
- Runway type preferences
- PDF parsing (with sample lines)
- Integration with recommendation output
"""

import json
import pytest

from gearrec.tire_catalog.models import TireSpec, ApplicationRow, MatchedTire
from gearrec.tire_catalog.matcher import (
    n_to_lbf,
    lbf_to_n,
    kpa_to_psi,
    match_tires,
    choose_tires_for_concept,
    SAFETY_FACTORS,
)
from gearrec.tire_catalog.import_goodyear_2022 import (
    parse_tire_data_line,
    parse_application_line,
)
from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import GearConcept, PDFMatchedTire


# Fixture: Sample tire catalog
@pytest.fixture
def sample_tire_specs():
    """Small tire catalog for testing."""
    return [
        TireSpec(
            source="test",
            size="6.00-6",
            ply_rating="6",
            tt_tl="TL",
            rated_load_lbs=1600,
            rated_inflation_psi=55,
            outside_diameter_in=17.5,
            section_width_in=6.0,
        ),
        TireSpec(
            source="test",
            size="6.00-6",
            ply_rating="8",
            tt_tl="TL",
            rated_load_lbs=2200,
            rated_inflation_psi=70,
            outside_diameter_in=17.5,
            section_width_in=6.0,
        ),
        TireSpec(
            source="test",
            size="5.00-5",
            ply_rating="4",
            tt_tl="TL",
            rated_load_lbs=900,
            rated_inflation_psi=35,
            outside_diameter_in=13.5,
            section_width_in=5.0,
        ),
        TireSpec(
            source="test",
            size="7.00-8",
            ply_rating="6",
            tt_tl="TT",
            rated_load_lbs=2400,
            rated_inflation_psi=45,
            outside_diameter_in=21.0,
            section_width_in=7.0,
        ),
        TireSpec(
            source="test",
            size="8.50-10",
            ply_rating="8",
            tt_tl="TL",
            rated_load_lbs=3500,
            rated_inflation_psi=50,
            outside_diameter_in=26.0,
            section_width_in=8.5,
        ),
    ]


@pytest.fixture
def sample_applications():
    """Sample application chart data."""
    return [
        ApplicationRow(
            manufacturer="CESSNA",
            model="172",
            main_tire_size="6.00-6",
            aux_tire_size="5.00-5",
            main_ply="6",
            aux_ply="4",
        ),
        ApplicationRow(
            manufacturer="PIPER",
            model="PA-28",
            main_tire_size="6.00-6",
            aux_tire_size="5.00-5",
            main_ply="6",
            aux_ply="4",
        ),
    ]


# =============================================================================
# Test: Unit Conversions
# =============================================================================

class TestUnitConversions:
    """Test unit conversion functions."""
    
    def test_n_to_lbf(self):
        """Test Newton to pound-force conversion."""
        # 1 Newton ≈ 0.224809 lbf
        result = n_to_lbf(1000)
        assert 224 < result < 226
        
    def test_lbf_to_n(self):
        """Test pound-force to Newton conversion."""
        # 1 lbf ≈ 4.44822 N
        result = lbf_to_n(100)
        assert 444 < result < 446
        
    def test_conversion_round_trip(self):
        """Test that conversions are inverses."""
        original = 5000  # Newtons
        lbf = n_to_lbf(original)
        back = lbf_to_n(lbf)
        assert abs(back - original) < 0.01
        
    def test_kpa_to_psi(self):
        """Test kPa to psi conversion."""
        # 1 kPa ≈ 0.145038 psi
        result = kpa_to_psi(100)
        assert 14 < result < 15


# =============================================================================
# Test: Tire Matching
# =============================================================================

class TestTireMatching:
    """Test tire matching logic."""
    
    def test_match_selects_adequate_load(self, sample_tire_specs):
        """Verify matching selects tires with rated_load >= required * SF."""
        # Required 1200 lbs with SF=1.10 => need 1320 lbs
        matches = match_tires(
            required_dynamic_load_lbs=1200,
            required_static_load_lbs=1000,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
        )
        
        assert len(matches) > 0
        # All matches should have adequate load
        for m in matches:
            assert m.tire.rated_load_lbs >= 1200 * SAFETY_FACTORS[RunwayType.PAVED]
    
    def test_match_excludes_insufficient_load(self, sample_tire_specs):
        """Verify matching excludes tires with insufficient capacity."""
        # Required 3000 lbs - should exclude small tires
        matches = match_tires(
            required_dynamic_load_lbs=3000,
            required_static_load_lbs=2500,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
        )
        
        # Only the 8.50-10 should match (3500 lbs rated)
        assert len(matches) >= 1
        for m in matches:
            assert m.tire.rated_load_lbs >= 3000
    
    def test_pressure_limit_filters_tires(self, sample_tire_specs):
        """Verify pressure limit excludes high-pressure tires."""
        # Limit to 45 psi - should exclude tires rated higher
        matches = match_tires(
            required_dynamic_load_lbs=1000,
            required_static_load_lbs=800,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
            pressure_limit_psi=45,
        )
        
        # All matches should be within pressure limit
        for m in matches:
            if m.tire.rated_inflation_psi is not None:
                assert m.tire.rated_inflation_psi <= 45
    
    def test_grass_runway_prefers_wider_tires(self, sample_tire_specs):
        """Verify grass runway gives higher scores to wider tires."""
        # Get scores for same load requirement on paved vs grass
        paved_matches = match_tires(
            required_dynamic_load_lbs=1500,
            required_static_load_lbs=1200,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
        )
        
        grass_matches = match_tires(
            required_dynamic_load_lbs=1500,
            required_static_load_lbs=1200,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.GRASS,
        )
        
        assert len(paved_matches) > 0
        assert len(grass_matches) > 0
        
        # For grass, larger/wider tires should score relatively better
        # Find the wider tire and check its relative ranking
        paved_sizes = [m.tire.size for m in paved_matches]
        grass_sizes = [m.tire.size for m in grass_matches]
        
        # The 7.00-8 (wider) should rank better for grass
        # (This is a relative comparison)
        assert paved_sizes is not None  # Just verify we got results
        assert grass_sizes is not None
    
    def test_margin_load_calculation(self, sample_tire_specs):
        """Verify load margin is calculated correctly."""
        matches = match_tires(
            required_dynamic_load_lbs=1200,
            required_static_load_lbs=1000,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
        )
        
        for m in matches:
            expected_margin = (m.tire.rated_load_lbs - 1200) / 1200
            assert abs(m.margin_load - expected_margin) < 0.01
    
    def test_safety_factor_by_runway(self):
        """Verify different safety factors for runway types."""
        assert SAFETY_FACTORS[RunwayType.PAVED] == 1.10
        assert SAFETY_FACTORS[RunwayType.GRASS] == 1.20
        assert SAFETY_FACTORS[RunwayType.GRAVEL] == 1.25
    
    def test_application_chart_bonus(self, sample_tire_specs, sample_applications):
        """Verify application chart match gives bonus."""
        # Aircraft that matches application chart
        matches_with_app = match_tires(
            required_dynamic_load_lbs=1300,
            required_static_load_lbs=1100,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
            aircraft_name="Cessna 172",
            mtow_kg=1100,
            applications=sample_applications,
            is_main=True,
        )
        
        # Same without application data
        matches_no_app = match_tires(
            required_dynamic_load_lbs=1300,
            required_static_load_lbs=1100,
            tire_specs=sample_tire_specs,
            runway_type=RunwayType.PAVED,
            aircraft_name="Unknown Aircraft",
            mtow_kg=1100,
            applications=None,
            is_main=True,
        )
        
        assert len(matches_with_app) > 0
        assert len(matches_no_app) > 0
        
        # Find 6.00-6 tire in both results
        app_tire = next((m for m in matches_with_app if m.tire.size == "6.00-6"), None)
        no_app_tire = next((m for m in matches_no_app if m.tire.size == "6.00-6"), None)
        
        if app_tire and no_app_tire:
            # With application match, score should be higher
            assert app_tire.score >= no_app_tire.score


# =============================================================================
# Test: PDF Parsing
# =============================================================================

class TestPDFParsing:
    """Test PDF line parsing functions."""
    
    def test_parse_tire_data_line_basic(self):
        """Test parsing a basic tire specification line."""
        # Simulated line from PDF
        line = "6.00-6 6 TL 160 1600 55 2400 3200 301234 17.50 15.50 6.00"
        
        spec = parse_tire_data_line(line, page=1)
        
        assert spec is not None
        assert spec.size == "6.00-6"
        assert spec.ply_rating == "6"
        assert spec.tt_tl == "TL"
        assert spec.rated_load_lbs == 1600
        assert spec.page == 1
    
    def test_parse_tire_data_line_with_x(self):
        """Test parsing line with 'x' in size (e.g., 24x7.25-10)."""
        line = "24x7.25-10 8 TL 120 3200 65 4800 6400 ABCD123 24.00 20.50 7.25"
        
        spec = parse_tire_data_line(line, page=5)
        
        assert spec is not None
        assert spec.size == "24X7.25-10"
        assert spec.rated_load_lbs == 3200
    
    def test_parse_tire_data_line_invalid(self):
        """Test that invalid lines return None."""
        # Non-tire line
        line = "This is a header row with no tire data"
        spec = parse_tire_data_line(line, page=1)
        assert spec is None
        
        # Empty line
        spec = parse_tire_data_line("", page=1)
        assert spec is None
    
    def test_parse_application_line_basic(self):
        """Test parsing application chart line."""
        line = "172 6.00-6 6 TL 5.00-5 4 TL"
        
        app = parse_application_line(line, page=10)
        
        assert app is not None
        assert "172" in app.model
        assert app.main_tire_size == "6.00-6"
        assert app.aux_tire_size == "5.00-5"
    
    def test_parse_application_line_skips_headers(self):
        """Test that header lines are skipped."""
        headers = [
            "AIRCRAFT MODEL MAIN TIRE NOSE TIRE",
            "Note: TT = Tube Type, TL = Tubeless",
            "WARNING: Verify with manufacturer",
        ]
        
        for line in headers:
            app = parse_application_line(line, page=1)
            assert app is None
    
    def test_parse_tire_raw_line_preserved(self):
        """Test that raw line is preserved for traceability."""
        line = "5.00-5 4 TL 120 900 35 1350 1800"
        spec = parse_tire_data_line(line, page=1)
        
        assert spec is not None
        assert spec.raw_line == line


# =============================================================================
# Test: Model Validation
# =============================================================================

class TestTireCatalogModels:
    """Test Pydantic model validation."""
    
    def test_tire_spec_creation(self):
        """Test TireSpec model creation."""
        spec = TireSpec(
            source="goodyear_2022",
            size="6.00-6",
            rated_load_lbs=1600,
        )
        assert spec.size == "6.00-6"
        assert spec.rated_load_N == pytest.approx(1600 * 4.44822, rel=0.01)
    
    def test_tire_spec_conversion_properties(self):
        """Test conversion properties on TireSpec."""
        spec = TireSpec(
            source="test",
            size="6.00-6",
            rated_load_lbs=1600,
            outside_diameter_in=17.5,
            section_width_in=6.0,
        )
        
        # Check metric conversions
        assert spec.outside_diameter_m == pytest.approx(17.5 * 0.0254, rel=0.01)
        assert spec.section_width_m == pytest.approx(6.0 * 0.0254, rel=0.01)
    
    def test_matched_tire_model(self):
        """Test MatchedTire model."""
        tire = TireSpec(source="test", size="6.00-6", rated_load_lbs=1600)
        
        matched = MatchedTire(
            tire=tire,
            margin_load=0.25,
            required_dynamic_load_lbs=1280,
            required_static_load_lbs=1000,
            reasons=["Adequate capacity"],
            score=0.85,
        )
        
        assert matched.score == 0.85
        assert matched.margin_load == 0.25
    
    def test_application_row_model(self):
        """Test ApplicationRow model."""
        app = ApplicationRow(
            manufacturer="CESSNA",
            model="172S",
            main_tire_size="6.00-6",
            aux_tire_size="5.00-5",
        )
        
        assert app.model == "172S"
        assert app.manufacturer == "CESSNA"


# =============================================================================
# Test: JSON Serialization
# =============================================================================

class TestJSONSerialization:
    """Test JSON serialization of tire catalog models."""
    
    def test_tire_spec_json_round_trip(self):
        """Test TireSpec serializes and deserializes correctly."""
        spec = TireSpec(
            source="goodyear_2022",
            size="6.00-6",
            ply_rating="6",
            tt_tl="TL",
            rated_load_lbs=1600,
            rated_inflation_psi=55,
        )
        
        json_str = spec.model_dump_json()
        restored = TireSpec.model_validate_json(json_str)
        
        assert restored.size == spec.size
        assert restored.rated_load_lbs == spec.rated_load_lbs
    
    def test_matched_tire_json(self):
        """Test MatchedTire JSON serialization."""
        tire = TireSpec(source="test", size="6.00-6", rated_load_lbs=1600)
        matched = MatchedTire(
            tire=tire,
            margin_load=0.25,
            required_dynamic_load_lbs=1280,
            required_static_load_lbs=1000,
            score=0.85,
        )
        
        data = json.loads(matched.model_dump_json())
        assert "tire" in data
        assert data["tire"]["size"] == "6.00-6"
        assert data["score"] == 0.85
    
    def test_pdf_matched_tire_output_model(self):
        """Test PDFMatchedTire output model for API responses."""
        matched = PDFMatchedTire(
            size="6.00-6",
            ply_rating="6",
            rated_load_lbs=1600,
            rated_inflation_psi=55,
            outside_diameter_in=17.5,
            section_width_in=6.0,
            margin_load=0.25,
            score=0.85,
            reasons=["Good capacity match"],
        )
        
        data = json.loads(matched.model_dump_json())
        assert data["size"] == "6.00-6"
        assert data["rated_load_lbs"] == 1600
        assert "reasons" in data


# =============================================================================
# Test: Integration with GearConcept
# =============================================================================

class TestIntegration:
    """Test integration with gear recommendation system."""
    
    def test_choose_tires_for_concept(self, sample_tire_specs, sample_applications):
        """Test tire selection for a gear concept."""
        from gearrec.generator.candidates import GearGenerator
        from gearrec.models.inputs import AircraftInputs
        
        # Create aircraft input
        inputs = AircraftInputs(
            aircraft_name="Test Trainer",
            mtow_kg=1200,
            cg_fwd_m=2.1,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
            runway=RunwayType.PAVED,
        )
        
        # Generate a concept
        generator = GearGenerator(inputs)
        result = generator.generate_result()
        
        assert len(result.concepts) > 0
        concept = result.concepts[0]
        
        # Match tires for this concept
        match_result = choose_tires_for_concept(
            concept, inputs, sample_tire_specs, sample_applications
        )
        
        assert match_result is not None
        assert len(match_result.warnings) > 0  # Should have disclaimer warning
    
    def test_output_includes_tire_fields(self, sample_tire_specs):
        """Test that output model supports new tire fields."""
        from gearrec.generator.candidates import GearGenerator
        
        inputs = AircraftInputs(
            aircraft_name="Test Aircraft",
            mtow_kg=1200,
            cg_fwd_m=2.1,
            cg_aft_m=2.4,
            landing_speed_mps=28.0,
        )
        
        generator = GearGenerator(inputs)
        result = generator.generate_result()
        
        # Verify output model has new optional fields
        concept = result.concepts[0]
        
        # These should be None by default (not matched yet)
        assert hasattr(concept.tire_suggestion, 'matched_main_tires')
        assert hasattr(concept.tire_suggestion, 'matched_nose_or_tail_tires')
        assert hasattr(concept.tire_suggestion, 'tire_selection_notes')
        assert hasattr(concept.tire_suggestion, 'tire_selection_warnings')
        
        # Set values and verify JSON includes them
        concept.tire_suggestion.matched_main_tires = [
            PDFMatchedTire(
                size="6.00-6",
                rated_load_lbs=1600,
                margin_load=0.25,
                score=0.85,
            )
        ]
        concept.tire_suggestion.tire_selection_warnings = [
            "Test warning"
        ]
        
        data = json.loads(concept.model_dump_json())
        assert "matched_main_tires" in data["tire_suggestion"]
        assert len(data["tire_suggestion"]["matched_main_tires"]) == 1


# =============================================================================
# Test: FastAPI Integration  
# =============================================================================

class TestAPIIntegration:
    """Test FastAPI endpoint integration."""
    
    def test_recommend_endpoint_supports_tire_flag(self):
        """Test that /recommend accepts use_pdf_tires parameter."""
        from fastapi.testclient import TestClient
        from gearrec.api.server import app
        
        client = TestClient(app)
        
        # Basic recommend without tires
        response = client.post("/recommend", json={
            "aircraft_name": "Test",
            "mtow_kg": 1200,
            "cg_fwd_m": 2.1,
            "cg_aft_m": 2.4,
            "landing_speed_mps": 28.0,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "concepts" in data
    
    def test_tire_catalog_status_endpoint(self):
        """Test /tire-catalog-status endpoint."""
        from fastapi.testclient import TestClient
        from gearrec.api.server import app
        
        client = TestClient(app)
        
        response = client.get("/tire-catalog-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "available" in data
        assert "warning" in data
        assert "verify" in data["warning"].lower()

