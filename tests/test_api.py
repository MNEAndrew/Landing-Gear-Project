"""
Tests for FastAPI endpoints.

Uses TestClient to test API endpoints without running a server.
"""

import pytest
from fastapi.testclient import TestClient

from gearrec.api.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def example_input():
    """Example input data for testing."""
    return {
        "aircraft_name": "Test Aircraft",
        "mtow_kg": 1200.0,
        "mlw_kg": 1140.0,
        "cg_fwd_m": 2.1,
        "cg_aft_m": 2.4,
        "landing_speed_mps": 28.0,
        "sink_rate_mps": 2.0,
        "runway": "paved",
        "retractable": False,
        "prop_clearance_m": 0.25,
        "wing_low": True,
        "brake_decel_g": 0.4,
        "design_priorities": {
            "robustness": 1.0,
            "low_drag": 0.5,
            "low_mass": 1.0,
            "simplicity": 1.5
        }
    }


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_ok(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    """Tests for / endpoint (HTML UI)."""
    
    def test_root_returns_html(self, client):
        """Test that root returns HTML page."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Landing Gear Recommender" in response.text


class TestExampleEndpoint:
    """Tests for /example endpoint."""
    
    def test_example_returns_valid_input(self, client):
        """Test that example endpoint returns valid AircraftInputs."""
        response = client.get("/example")
        
        assert response.status_code == 200
        data = response.json()
        assert "aircraft_name" in data
        assert "mtow_kg" in data
        assert data["mtow_kg"] > 0


class TestRecommendEndpoint:
    """Tests for /recommend endpoint."""
    
    def test_recommend_returns_concepts(self, client, example_input):
        """Test that recommend endpoint returns concepts."""
        response = client.post("/recommend", json=example_input)
        
        assert response.status_code == 200
        data = response.json()
        assert "concepts" in data
        assert 3 <= len(data["concepts"]) <= 6
    
    def test_recommend_concepts_have_required_fields(self, client, example_input):
        """Test that returned concepts have all required fields."""
        response = client.post("/recommend", json=example_input)
        data = response.json()
        
        concept = data["concepts"][0]
        assert "config" in concept
        assert "gear_type" in concept
        assert "geometry" in concept
        assert "loads" in concept
        assert "checks" in concept
        assert "score" in concept
        assert "explanation" in concept
        assert "assumptions" in concept
    
    def test_recommend_with_invalid_input_returns_error(self, client):
        """Test that invalid input returns 400 or 422."""
        invalid_input = {"aircraft_name": "Test"}  # Missing required fields
        
        response = client.post("/recommend", json=invalid_input)
        
        assert response.status_code in [400, 422]
    
    def test_recommend_includes_assumptions(self, client, example_input):
        """Test that result includes assumptions."""
        response = client.post("/recommend", json=example_input)
        data = response.json()
        
        assert "assumptions" in data
        assert len(data["assumptions"]) > 0


class TestSweepEndpoint:
    """Tests for /sweep endpoint."""
    
    def test_sweep_returns_valid_result(self, client, example_input):
        """Test that sweep endpoint returns valid SweepResult."""
        response = client.post("/sweep", json=example_input)
        
        assert response.status_code == 200
        data = response.json()
        assert "sink_rates_swept" in data
        assert "cg_positions_swept" in data
        assert "concept_results" in data
        assert "most_robust_concept" in data
    
    def test_sweep_pass_rate_in_range(self, client, example_input):
        """Test that sweep pass rates are between 0 and 1."""
        response = client.post("/sweep", json=example_input)
        data = response.json()
        
        for cr in data["concept_results"]:
            assert 0 <= cr["pass_rate"] <= 1
    
    def test_sweep_has_sweep_points(self, client, example_input):
        """Test that sweep results include sweep points."""
        response = client.post("/sweep", json=example_input)
        data = response.json()
        
        for cr in data["concept_results"]:
            assert "sweep_points" in cr
            assert len(cr["sweep_points"]) > 0


class TestRunwayTypesEndpoint:
    """Tests for /runway-types endpoint."""
    
    def test_runway_types_returns_list(self, client):
        """Test that runway-types returns list of types."""
        response = client.get("/runway-types")
        
        assert response.status_code == 200
        data = response.json()
        assert "runway_types" in data
        assert "paved" in data["runway_types"]
        assert "grass" in data["runway_types"]
        assert "gravel" in data["runway_types"]

