# Landing Gear Recommender (gearrec)

A **conceptual sizing tool** for aircraft landing gear that generates 3–6 candidate gear configurations based on aircraft parameters. This tool is intended for **preliminary design exploration only** and is **NOT suitable for certification or detailed design**.

## ⚠️ Disclaimer

This tool provides **rough conceptual estimates** using simplified physics models. The outputs are intended to help designers explore the solution space early in the design process. **Do not use these results for:**
- Certification purposes
- Detailed structural design
- Final component selection
- Safety-critical decisions

Always consult qualified aerospace engineers and follow applicable regulations (FAR/CS-23, FAR/CS-25, etc.) for actual aircraft design.

## Features

- **Multiple configurations**: Generates tricycle (fixed/retractable) and taildragger options
- **Physics-based sizing**: Uses simplified but documented models for loads, energy absorption, and geometry
- **Unit-aware calculations**: Physics calculations use [pint](https://pint.readthedocs.io/) for dimensional correctness
- **Tire catalog matching**: Includes internal tire catalog with matching logic
- **Configurable scoring**: Weight design priorities (robustness, drag, mass, simplicity)
- **Safety checks**: Validates tip-back, nose-over, rollover, and ground clearance margins
- **Sensitivity sweep**: Analyze robustness across sink rates and CG positions
- **CLI & API**: Command-line interface plus FastAPI web service with HTML UI

## Installation

```bash
# Clone the repository
git clone https://github.com/MNEAndrew/Landing-Gear-Project.git
cd "Landing-Gear-Project"

# Install in development mode
pip install -e ".[dev]"
```

## Quick Start

### Generate example input file
```bash
python -m gearrec make-example
# Creates example_input.json
```

### Run recommendation
```bash
python -m gearrec recommend --input example_input.json
# Outputs JSON with 3-6 gear concepts
```

### Save output to file
```bash
python -m gearrec recommend --input example_input.json --output results.json
```

### Run sensitivity sweep
```bash
python -m gearrec sweep --input example_input.json
# Outputs sweep analysis across sink rates and CG positions
```

### Start web API with HTML UI
```bash
python -m gearrec serve --port 8000
# API available at http://localhost:8000
# HTML UI at http://localhost:8000/
# API docs at http://localhost:8000/docs
```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `aircraft_name` | str | Yes | - | Aircraft identifier |
| `mtow_kg` | float | Yes | - | Maximum takeoff weight (kg) |
| `mlw_kg` | float | No | 0.95×MTOW | Maximum landing weight (kg) |
| `cg_fwd_m` | float | Yes | - | Forward CG limit from datum (m) |
| `cg_aft_m` | float | Yes | - | Aft CG limit from datum (m) |
| `cg_height_m` | float | No | estimated | CG height above ground (m) |
| `fuselage_length_m` | float | No | estimated | Fuselage length (m) |
| `main_gear_attach_guess_m` | float | No | auto | Main gear attachment point from datum (m) |
| `nose_gear_attach_guess_m` | float | No | auto | Nose gear attachment point from datum (m) |
| `landing_speed_mps` | float | Yes | - | Landing approach speed (m/s) |
| `sink_rate_mps` | float | No | 2.0 | Vertical touchdown rate (m/s) |
| `runway` | enum | No | paved | Runway surface: paved, grass, gravel |
| `retractable` | bool | No | false | Whether retractable gear is required |
| `prop_clearance_m` | float | No | 0.0 | Required propeller ground clearance (m) |
| `wing_low` | bool | No | true | Low-wing configuration |
| `tire_pressure_limit_kpa` | float | No | None | Maximum allowable tire pressure (kPa) |
| `max_gear_mass_kg` | float | No | None | Maximum gear system mass constraint (kg) |
| `brake_decel_g` | float | No | 0.4 | Assumed braking deceleration (g's) |
| `design_priorities` | dict | No | equal | Weights for {robustness, low_drag, low_mass, simplicity} |

## Output Structure

Each candidate concept includes:

```json
{
  "config": "tricycle",
  "gear_type": "fixed",
  "wheel_count_main": 1,
  "wheel_count_nose_or_tail": 1,
  "geometry": {
    "track_m": {"min": 2.0, "max": 2.5},
    "wheelbase_m": {"min": 2.5, "max": 3.5},
    "main_strut_length_m": {"min": 0.4, "max": 0.6},
    "nose_or_tail_strut_length_m": {"min": 0.3, "max": 0.5},
    "stroke_m": {"min": 0.15, "max": 0.20}
  },
  "tire_suggestion": {
    "required_static_load_per_wheel_N": 7500,
    "required_dynamic_load_per_wheel_N": 15000,
    "recommended_tire_diameter_range_m": {"min": 0.35, "max": 0.45},
    "recommended_tire_width_range_m": {"min": 0.12, "max": 0.16},
    "matched_catalog_tires": [{"name": "6.00-6", ...}]
  },
  "loads": {
    "weight_N": 11178,
    "static_nose_or_tail_load_N": 1200,
    "static_main_load_total_N": 9978,
    "static_main_load_per_wheel_N": 4989,
    "landing_energy_J": 2280,
    "required_avg_force_N": 14250,
    "nose_load_fraction": 0.107
  },
  "checks": {
    "tip_back_margin": {"passed": true, "value": 0.15, "limit": 0.10},
    "nose_over_margin": {"passed": true, "value": 0.25, "limit": 0.08},
    "ground_clearance_ok": true,
    "lateral_stability_ok": true,
    "prop_clearance_ok": true,
    "rollover_angle_deg": 46.2,
    "cg_range_sensitivity": {"pass_rate": 1.0, "worst_case_position": "aft"}
  },
  "explanation": ["..."],
  "assumptions": ["..."],
  "input_summary": {"mtow_kg": 1200, ...},
  "score": 0.82,
  "score_breakdown": {...}
}
```

## Physics Models

### Touchdown Energy
```
E = 0.5 × m × sink_rate²
```
Where m is maximum landing weight.

### Required Shock Force
```
F_avg = E / (stroke × efficiency)
```
Efficiency assumed at 80%.

### Static Load Distribution (Tricycle)
```
R_nose = W × (x_main - x_cg) / (x_main - x_nose)
R_main = W - R_nose
```

### Geometry Heuristics
- **Fuselage length** (if not provided): `k × MTOW^(1/3)`, k ≈ 0.85
- **Track**: 0.18–0.28 × fuselage length
- **Wheelbase**: 0.25–0.38 × fuselage length (tricycle)

### Safety Checks
- **Tip-back**: CG must be forward of main gear by margin
- **Nose-over**: Under braking (default 0.4g), gear must not flip
- **Rollover**: Track vs CG height angle check
- **Ground clearance**: Propeller and structure clearance

## Project Structure

```
gearrec/
├── __init__.py
├── __main__.py
├── models/           # Pydantic data models
│   ├── inputs.py     # AircraftInputs
│   └── outputs.py    # GearConcept, SweepResult
├── physics/          # Unit-aware calculations
│   ├── units.py      # Pint unit registry
│   ├── energy.py     # Energy & force calculations
│   ├── loads.py      # Load distribution
│   ├── geometry.py   # Geometry heuristics
│   └── tire_catalog.py  # Tire catalog & matching
├── generator/        # Candidate generation
│   └── candidates.py # GearGenerator with sweep
├── scoring/          # Scoring system
│   └── scorer.py
├── cli/              # Command-line interface
│   └── main.py
└── api/              # FastAPI web interface
    └── server.py     # REST API + HTML UI
```

## Running Tests

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov=gearrec      # With coverage
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | HTML UI |
| GET | `/health` | Health check |
| GET | `/example` | Get example input |
| POST | `/recommend` | Generate recommendations |
| POST | `/sweep` | Run sensitivity sweep |
| GET | `/runway-types` | List runway types |

## Sweep Analysis

The sweep command evaluates each concept across:
- Multiple sink rates (around the input value)
- CG positions (forward, mid, aft)

Results include:
- `pass_rate`: Fraction of conditions passing all checks
- `avg_score`, `worst_case_score`, `best_case_score`
- `most_robust_concept`: Best overall robustness

## Installation & CLI

```bash
pip install -e .[dev]
```

CLI usage:
- `gearrec make-example`
- `gearrec recommend --input example_input.json`
- `gearrec sweep --input example_input.json`
- `gearrec import-tires --data-section <Data-Section.pdf> --app-charts <Application-Charts.pdf>`
- `gearrec serve --port 8000`

## Local executable build (PyInstaller, beta)
- macOS/Linux: `./scripts/build_exe.sh`
- Windows (PowerShell): `./scripts/build_exe.ps1`

Outputs land in `dist/gearrec-<os>-<arch>/gearrec[.exe]` and support `gearrec --help`, `gearrec recommend --input ...`.

## Release process (GitHub Actions)
1) Update version (`python scripts/bump_version.py <new-version>`) and commit.
2) Tag: `git tag v0.1.0-beta && git push origin v0.1.0-beta`
3) GitHub Actions (release workflow) runs tests, builds PyInstaller executables for Windows/macOS/Linux, uploads artifacts, and creates a GitHub Release with attached zips.

## Safety disclaimer
This tool is for **conceptual sizing only**. Always verify with airframe and tire manufacturers and follow applicable regulations before any installation or certification activity.

## License

MIT License - See LICENSE file for details.

## Contributing

This is a conceptual tool for educational and preliminary design purposes. Contributions that improve the physics models, add configuration options, or enhance documentation are welcome.
