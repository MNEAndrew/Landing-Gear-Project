"""
FastAPI server for landing gear recommender.

Provides REST API endpoints and simple HTML UI.
WARNING: For conceptual sizing only, NOT for certification.
"""

from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.models.outputs import RecommendationResult, SweepResult, PDFMatchedTire
from gearrec.generator.candidates import GearGenerator

# Create FastAPI app
app = FastAPI(
    title="Landing Gear Recommender API",
    description="""
    Conceptual sizing tool for aircraft landing gear.
    
    **WARNING**: This tool provides rough conceptual estimates only.
    Not for certification or detailed design purposes.
    """,
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTML UI Template
HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Landing Gear Recommender</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        .warning {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .container { display: flex; gap: 20px; flex-wrap: wrap; }
        .input-section, .output-section { 
            flex: 1; 
            min-width: 400px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        textarea {
            width: 100%;
            height: 400px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .buttons { margin-top: 15px; }
        button {
            padding: 12px 24px;
            font-size: 14px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
            margin-right: 10px;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-primary:hover { background: #2980b9; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; }
        .results { margin-top: 20px; }
        .concept-card {
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .concept-card.best { border-color: #27ae60; border-width: 2px; }
        .concept-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .config-badge {
            background: #3498db;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
        }
        .score { font-size: 24px; font-weight: bold; color: #27ae60; }
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .detail-item { background: #f8f9fa; padding: 8px; border-radius: 4px; }
        .detail-label { font-size: 11px; color: #666; }
        .detail-value { font-weight: 500; }
        .checks { margin-top: 10px; }
        .check-pass { color: #27ae60; }
        .check-fail { color: #e74c3c; }
        .explanation { 
            margin-top: 10px; 
            padding: 10px; 
            background: #f8f9fa; 
            border-radius: 4px;
            font-size: 13px;
        }
        .loading { color: #666; font-style: italic; }
        pre { white-space: pre-wrap; font-size: 11px; }
        .tabs { display: flex; gap: 5px; margin-bottom: 10px; }
        .tab {
            padding: 8px 16px;
            cursor: pointer;
            border: 1px solid #ddd;
            border-radius: 4px 4px 0 0;
            background: #f5f5f5;
        }
        .tab.active { background: white; border-bottom-color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <h1>✈️ Landing Gear Recommender</h1>
    <div class="warning">
        <strong>⚠️ CONCEPTUAL SIZING ONLY</strong> - This tool provides rough estimates for preliminary design. 
        Not for certification or detailed design purposes.
    </div>
    
    <div class="container">
        <div class="input-section">
            <h3>Aircraft Parameters (JSON)</h3>
            <textarea id="inputJson">{
  "aircraft_name": "GA-2024 Trainer",
  "mtow_kg": 1200.0,
  "mlw_kg": 1140.0,
  "cg_fwd_m": 2.10,
  "cg_aft_m": 2.45,
  "cg_height_m": 1.10,
  "fuselage_length_m": 8.5,
  "landing_speed_mps": 28.0,
  "sink_rate_mps": 2.0,
  "runway": "paved",
  "retractable": false,
  "prop_clearance_m": 0.25,
  "wing_low": true,
  "brake_decel_g": 0.4,
  "design_priorities": {
    "robustness": 1.0,
    "low_drag": 0.5,
    "low_mass": 1.0,
    "simplicity": 1.5
  }
}</textarea>
            <div class="buttons">
                <button class="btn-primary" onclick="runRecommend()">🔍 Recommend</button>
                <button class="btn-secondary" onclick="runSweep()">📊 Sweep</button>
            </div>
        </div>
        
        <div class="output-section">
            <div class="tabs">
                <div class="tab active" onclick="showTab('cards')">Cards</div>
                <div class="tab" onclick="showTab('json')">Raw JSON</div>
            </div>
            <div id="results">
                <p class="loading">Enter aircraft parameters and click Recommend or Sweep.</p>
            </div>
        </div>
    </div>
    
    <script>
        let currentTab = 'cards';
        let lastResult = null;
        
        function showTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab:nth-child(${tab === 'cards' ? 1 : 2})`).classList.add('active');
            if (lastResult) renderResult(lastResult);
        }
        
        async function runRecommend() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p class="loading">Generating recommendations...</p>';
            
            try {
                const input = JSON.parse(document.getElementById('inputJson').value);
                const response = await fetch('/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(input)
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Request failed');
                }
                
                lastResult = { type: 'recommend', data: await response.json() };
                renderResult(lastResult);
            } catch (e) {
                resultsDiv.innerHTML = `<p style="color:red;">Error: ${e.message}</p>`;
            }
        }
        
        async function runSweep() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p class="loading">Running sensitivity sweep...</p>';
            
            try {
                const input = JSON.parse(document.getElementById('inputJson').value);
                const response = await fetch('/sweep', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(input)
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Request failed');
                }
                
                lastResult = { type: 'sweep', data: await response.json() };
                renderResult(lastResult);
            } catch (e) {
                resultsDiv.innerHTML = `<p style="color:red;">Error: ${e.message}</p>`;
            }
        }
        
        function renderResult(result) {
            const resultsDiv = document.getElementById('results');
            
            if (currentTab === 'json') {
                resultsDiv.innerHTML = `<pre>${JSON.stringify(result.data, null, 2)}</pre>`;
                return;
            }
            
            if (result.type === 'recommend') {
                renderRecommendCards(result.data);
            } else {
                renderSweepCards(result.data);
            }
        }
        
        function renderRecommendCards(data) {
            const resultsDiv = document.getElementById('results');
            let html = `<h3>Results for ${data.aircraft_name}</h3>`;
            
            if (data.warnings && data.warnings.length > 0) {
                html += `<div class="warning">${data.warnings.join('<br>')}</div>`;
            }
            
            data.concepts.forEach((c, i) => {
                const isBest = i === 0;
                html += `
                <div class="concept-card ${isBest ? 'best' : ''}">
                    <div class="concept-header">
                        <div>
                            <span class="config-badge">${c.config} ${c.gear_type}</span>
                            ${isBest ? '<span style="color:#27ae60;margin-left:10px;">★ Best Match</span>' : ''}
                        </div>
                        <div class="score">${(c.score * 100).toFixed(0)}%</div>
                    </div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Track</div>
                            <div class="detail-value">${c.geometry.track_m.min.toFixed(2)} - ${c.geometry.track_m.max.toFixed(2)} m</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Wheelbase</div>
                            <div class="detail-value">${c.geometry.wheelbase_m.min.toFixed(2)} - ${c.geometry.wheelbase_m.max.toFixed(2)} m</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Stroke</div>
                            <div class="detail-value">${c.geometry.stroke_m.min.toFixed(3)} - ${c.geometry.stroke_m.max.toFixed(3)} m</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Main Load/Wheel</div>
                            <div class="detail-value">${(c.loads.static_main_load_per_wheel_N/1000).toFixed(1)} kN</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Landing Energy</div>
                            <div class="detail-value">${c.loads.landing_energy_J.toFixed(0)} J</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Tire Diameter</div>
                            <div class="detail-value">${c.tire_suggestion.recommended_tire_diameter_range_m.min.toFixed(2)} - ${c.tire_suggestion.recommended_tire_diameter_range_m.max.toFixed(2)} m</div>
                        </div>
                    </div>
                    <div class="checks">
                        <span class="${c.checks.tip_back_margin.passed ? 'check-pass' : 'check-fail'}">
                            ${c.checks.tip_back_margin.passed ? '✓' : '✗'} Tip-back
                        </span>
                        <span class="${c.checks.nose_over_margin.passed ? 'check-pass' : 'check-fail'}">
                            ${c.checks.nose_over_margin.passed ? '✓' : '✗'} Nose-over
                        </span>
                        <span class="${c.checks.ground_clearance_ok ? 'check-pass' : 'check-fail'}">
                            ${c.checks.ground_clearance_ok ? '✓' : '✗'} Clearance
                        </span>
                        <span class="${c.checks.lateral_stability_ok ? 'check-pass' : 'check-fail'}">
                            ${c.checks.lateral_stability_ok ? '✓' : '✗'} Rollover
                        </span>
                    </div>
                    <div class="explanation">
                        ${c.explanation.map(e => `• ${e}`).join('<br>')}
                    </div>
                </div>`;
            });
            
            resultsDiv.innerHTML = html;
        }
        
        function renderSweepCards(data) {
            const resultsDiv = document.getElementById('results');
            let html = `<h3>Sweep Results for ${data.aircraft_name}</h3>`;
            html += `<p><strong>Most Robust:</strong> ${data.most_robust_concept}</p>`;
            html += `<p>Sink rates: ${data.sink_rates_swept.join(', ')} m/s</p>`;
            
            data.concept_results.forEach(cr => {
                const passColor = cr.pass_rate >= 0.8 ? '#27ae60' : cr.pass_rate >= 0.5 ? '#f39c12' : '#e74c3c';
                html += `
                <div class="concept-card">
                    <div class="concept-header">
                        <span class="config-badge">${cr.config} ${cr.gear_type}</span>
                        <div>
                            <span style="color:${passColor};font-weight:bold;">${(cr.pass_rate * 100).toFixed(0)}% pass</span>
                        </div>
                    </div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Avg Score</div>
                            <div class="detail-value">${(cr.avg_score * 100).toFixed(0)}%</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Best Score</div>
                            <div class="detail-value">${(cr.best_case_score * 100).toFixed(0)}%</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Worst Score</div>
                            <div class="detail-value">${(cr.worst_case_score * 100).toFixed(0)}%</div>
                        </div>
                    </div>
                </div>`;
            });
            
            resultsDiv.innerHTML = html;
        }
    </script>
</body>
</html>
"""


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the HTML UI."""
    return HTML_UI


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the API is running."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/example", response_model=AircraftInputs, tags=["Reference"])
async def get_example():
    """Get an example input configuration."""
    return AircraftInputs(
        aircraft_name="GA-2024 Trainer",
        mtow_kg=1200.0,
        mlw_kg=1140.0,
        cg_fwd_m=2.10,
        cg_aft_m=2.45,
        cg_height_m=1.10,
        fuselage_length_m=8.5,
        landing_speed_mps=28.0,
        sink_rate_mps=2.0,
        runway=RunwayType.PAVED,
        retractable=False,
        prop_clearance_m=0.25,
        wing_low=True,
        brake_decel_g=0.4,
        design_priorities=DesignPriorities(
            robustness=1.0,
            low_drag=0.5,
            low_mass=1.0,
            simplicity=1.5,
        ),
    )


class RecommendRequest(BaseModel):
    """Request body for recommend endpoint with optional tire matching."""
    aircraft: AircraftInputs
    use_pdf_tires: bool = False


@app.post("/recommend", response_model=RecommendationResult, tags=["Recommendations"])
async def recommend(
    inputs: AircraftInputs,
    use_pdf_tires: bool = Query(default=False, description="Use PDF-based Goodyear tire catalog"),
):
    """
    Generate landing gear recommendations.
    
    Returns 3-6 candidate gear configurations ranked by score.
    Optionally matches tires from PDF catalog if use_pdf_tires=true.
    """
    try:
        generator = GearGenerator(inputs)
        result = generator.generate_result()
        
        # Apply PDF tire matching if requested
        if use_pdf_tires:
            from gearrec.tire_catalog.loader import catalog_exists, load_tire_specs, load_applications
            from gearrec.tire_catalog.matcher import choose_tires_for_concept
            
            if not catalog_exists():
                raise HTTPException(
                    status_code=400, 
                    detail="Tire catalog not found. Run 'python -m gearrec import-tires' first."
                )
            
            tire_specs = load_tire_specs()
            try:
                applications = load_applications()
            except FileNotFoundError:
                applications = []
            
            # Match tires for each concept
            for concept in result.concepts:
                match_result = choose_tires_for_concept(
                    concept, inputs, tire_specs, applications
                )
                
                # Convert to PDFMatchedTire for output
                main_tires = [
                    PDFMatchedTire(
                        size=m.tire.size,
                        ply_rating=m.tire.ply_rating,
                        rated_load_lbs=m.tire.rated_load_lbs,
                        rated_inflation_psi=m.tire.rated_inflation_psi,
                        outside_diameter_in=m.tire.outside_diameter_in,
                        section_width_in=m.tire.section_width_in,
                        margin_load=m.margin_load,
                        score=m.score,
                        reasons=m.reasons,
                    )
                    for m in match_result.main
                ]
                
                nose_tires = [
                    PDFMatchedTire(
                        size=m.tire.size,
                        ply_rating=m.tire.ply_rating,
                        rated_load_lbs=m.tire.rated_load_lbs,
                        rated_inflation_psi=m.tire.rated_inflation_psi,
                        outside_diameter_in=m.tire.outside_diameter_in,
                        section_width_in=m.tire.section_width_in,
                        margin_load=m.margin_load,
                        score=m.score,
                        reasons=m.reasons,
                    )
                    for m in match_result.nose_or_tail
                ]
                
                concept.tire_suggestion.matched_main_tires = main_tires if main_tires else None
                concept.tire_suggestion.matched_nose_or_tail_tires = nose_tires if nose_tires else None
                concept.tire_suggestion.tire_selection_notes = match_result.notes if match_result.notes else None
                concept.tire_suggestion.tire_selection_warnings = match_result.warnings if match_result.warnings else None
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/sweep", response_model=SweepResult, tags=["Analysis"])
async def sweep(inputs: AircraftInputs):
    """
    Run sensitivity sweep across sink rates and CG positions.
    
    Evaluates each concept across a range of conditions and reports
    pass rates and score statistics.
    """
    try:
        generator = GearGenerator(inputs)
        result = generator.run_sweep()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/runway-types", tags=["Reference"])
async def list_runway_types():
    """Get list of supported runway types."""
    return {
        "runway_types": [rt.value for rt in RunwayType],
        "descriptions": {
            "paved": "Hard-surfaced runway (asphalt, concrete)",
            "grass": "Natural grass surface, requires larger tires",
            "gravel": "Gravel or dirt surface, needs robust gear",
        }
    }


@app.get("/tire-catalog-status", tags=["Tires"])
async def tire_catalog_status():
    """Check if PDF tire catalog is available."""
    from gearrec.tire_catalog.loader import catalog_exists, load_tire_specs, load_applications
    
    exists = catalog_exists()
    tire_count = 0
    app_count = 0
    
    if exists:
        try:
            tire_count = len(load_tire_specs())
        except Exception:
            pass
        try:
            app_count = len(load_applications())
        except Exception:
            pass
    
    return {
        "available": exists,
        "tire_count": tire_count,
        "application_count": app_count,
        "message": "Tire catalog is available" if exists else "Tire catalog not found. Run 'python -m gearrec import-tires' to import.",
        "warning": "Application charts are general reference only; verify with airframe manufacturer and tire manufacturer before installing."
    }
