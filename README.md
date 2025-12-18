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
- **Unit-aware calculations**: All physics use [pint](https://pint.readthedocs.io/) for dimensional correctness
- **Configurable scoring**: Weight design priorities (robustness, drag, mass, simplicity)
- **Safety checks**: Validates tip-back, nose-over, and ground clearance margins
- **CLI & API**: Command-line interface plus optional FastAPI web service

## Installation

```bash
# Clone and install in development mode
cd "Landing Gear Project"
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

### Start web API (optional)
```bash
python -m gearrec serve --port 8000
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `aircraft_name` | str | Yes | - | Aircraft identifier |
| `mtow_kg` | float | Yes | - | Maximum takeoff weight (kg) |
| `mlw_kg` | float | No | 0.95×MTOW | Maximum landing weight (kg) |
| `cg_fwd_m` | float | Yes | - | Forward CG limit from datum (m) |
| `cg_aft_m` | float | Yes | - | Aft CG limit from datum (m) |
| `main_gear_attach_guess_m` | float | No | auto | Main gear attachment point from datum (m) |
| `nose_gear_attach_guess_m` | float | No | auto | Nose gear attachment point from datum (m) |
| `landing_speed_mps` | float | Yes | - | Landing approach speed (m/s) |
| `sink_rate_mps` | float | No | 2.0 | Vertical touchdown rate (m/s) |
| `runway` | enum | No | paved | Runway surface: paved, grass, gravel |
| `retractable` | bool | No | false | Whether retractable gear is required |
| `prop_clearance_m` | float | No | 0.0 | Required propeller ground clearance (m) |
| `wing_low` | bool | No | false | Low-wing configuration (affects tip clearance) |
| `tire_pressure_limit_kpa` | float | No | None | Maximum allowable tire pressure (kPa) |
| `max_gear_mass_kg` | float | No | None | Maximum gear system mass constraint (kg) |
| `design_priorities` | dict | No | equal | Weights for {robustness, low_drag, low_mass, simplicity} |

## Output Structure

Each candidate includes:

```json
{
  "config": "tricycle",
  "gear_type": "fixed",
  "wheel_count_main": 1,
  "wheel_count_nose_or_tail": 1,
  "geometry": {
    "track_m": {"min": 2.0, "max": 2.5},
    "wheelbase_m": {"min": 4.0, "max": 5.0},
    "main_strut_length_m": {"min": 0.4, "max": 0.6},
    "nose_or_tail_strut_length_m": {"min": 0.3, "max": 0.5},
    "stroke_m": {"min": 0.15, "max": 0.25}
  },
  "tire_suggestion": {
    "required_static_load_per_wheel_N": 12000,
    "required_dynamic_load_per_wheel_N": 24000,
    "recommended_tire_diameter_range_m": {"min": 0.35, "max": 0.45}
  },
  "loads": {
    "static_nose_load_N": 4000,
    "static_main_load_N": 36000,
    "landing_energy_J": 8000,
    "required_avg_force_N": 40000
  },
  "checks": {
    "tip_back_margin": {"passed": true, "value": 0.15},
    "nose_over_margin": {"passed": true, "value": 0.12},
    "ground_clearance_ok": true
  },
  "explanation": [
    "Tricycle fixed gear selected for simplicity",
    "Track width sized for rollover stability",
    "..."
  ],
  "score": 0.82,
  "score_breakdown": {
    "robustness": 0.85,
    "low_drag": 0.70,
    "low_mass": 0.90,
    "simplicity": 0.95
  }
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
F_avg = E / stroke
```
Stroke is the shock absorber travel distance.

### Static Load Distribution (Tricycle)
```
R_nose = W × (x_main - x_cg) / (x_main - x_nose)
R_main = W - R_nose
```
Where x positions are measured from datum.

### Geometry Heuristics
- **Track**: 0.18–0.28 × estimated fuselage length
- **Wheelbase**: 0.25–0.35 × estimated fuselage length
- **Fuselage length estimate**: k × MTOW^(1/3), k ≈ 0.8 for GA aircraft

### Safety Checks
- **Tip-back**: CG must be forward of main gear by margin
- **Nose-over**: Under 0.4g braking, gear must not flip
- **Ground clearance**: Propeller and structure clearance

## Project Structure

```
gearrec/
├── __init__.py
├── __main__.py
├── models/           # Pydantic data models
│   ├── __init__.py
│   ├── inputs.py     # Aircraft input parameters
│   └── outputs.py    # Gear concept outputs
├── physics/          # Unit-aware calculations
│   ├── __init__.py
│   ├── units.py      # Pint unit registry
│   ├── energy.py     # Energy & force calculations
│   ├── loads.py      # Load distribution
│   └── geometry.py   # Geometry heuristics
├── generator/        # Candidate generation
│   ├── __init__.py
│   └── candidates.py
├── scoring/          # Scoring system
│   ├── __init__.py
│   └── scorer.py
├── cli/              # Command-line interface
│   ├── __init__.py
│   └── main.py
└── api/              # FastAPI web interface
    ├── __init__.py
    └── server.py
```

## Running Tests

```bash
pytest
pytest --cov=gearrec  # With coverage
```

## License

MIT License - See LICENSE file for details.

## Contributing

This is a conceptual tool for educational and preliminary design purposes. Contributions that improve the physics models, add configuration options, or enhance documentation are welcome.

