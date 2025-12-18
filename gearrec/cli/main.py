"""
Command-line interface for landing gear recommender.

Usage:
    python -m gearrec recommend --input example.json [--output results.json]
    python -m gearrec make-example [--output example_input.json]
    python -m gearrec sweep --input example.json [--output sweep_output.json]
    python -m gearrec serve [--port 8000]
"""

import argparse
import json
import sys
from pathlib import Path

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.generator.candidates import GearGenerator


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="gearrec",
        description="Landing Gear Recommender - Conceptual sizing tool for aircraft landing gear. "
                    "WARNING: For conceptual sizing only, NOT for certification.",
    )
    parser.add_argument("--version", action="version", version="gearrec 0.1.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # make-example command
    example_parser = subparsers.add_parser(
        "make-example",
        help="Generate an example input JSON file",
    )
    example_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("example_input.json"),
        help="Output path for example file (default: example_input.json)",
    )
    
    # recommend command
    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Generate landing gear recommendations",
    )
    recommend_parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Path to JSON input file with aircraft parameters",
    )
    recommend_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Path to save JSON output (prints to stdout if not specified)",
    )
    
    # sweep command
    sweep_parser = subparsers.add_parser(
        "sweep",
        help="Run sensitivity sweep across sink rates and CG positions",
    )
    sweep_parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Path to JSON input file with aircraft parameters",
    )
    sweep_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Path to save sweep results (prints to stdout if not specified)",
    )
    
    # serve command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the FastAPI web server",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    
    return parser


def cmd_make_example(args: argparse.Namespace) -> int:
    """Generate an example input JSON file."""
    example = AircraftInputs(
        aircraft_name="GA-2024 Trainer",
        mtow_kg=1200.0,
        mlw_kg=1140.0,
        cg_fwd_m=2.10,
        cg_aft_m=2.45,
        cg_height_m=1.10,
        fuselage_length_m=8.5,
        main_gear_attach_guess_m=2.55,
        nose_gear_attach_guess_m=0.80,
        landing_speed_mps=28.0,
        sink_rate_mps=2.0,
        runway=RunwayType.PAVED,
        retractable=False,
        prop_clearance_m=0.25,
        wing_low=True,
        tire_pressure_limit_kpa=None,
        max_gear_mass_kg=None,
        takeoff_distance_m=500.0,
        landing_distance_m=450.0,
        brake_decel_g=0.4,
        design_priorities=DesignPriorities(
            robustness=1.0,
            low_drag=0.5,
            low_mass=1.0,
            simplicity=1.5,
        ),
    )
    
    output_json = example.model_dump_json(indent=2)
    
    with open(args.output, "w") as f:
        f.write(output_json)
    
    print(f"Created example input file: {args.output}")
    print("\nRun recommendation with:")
    print(f"  python -m gearrec recommend --input {args.output}")
    
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    """Generate landing gear recommendations."""
    try:
        # Load input
        with open(args.input) as f:
            input_data = json.load(f)
        
        # Parse and validate
        inputs = AircraftInputs(**input_data)
        
        print(f"\nLanding Gear Recommender", file=sys.stderr)
        print(f"Aircraft: {inputs.aircraft_name}", file=sys.stderr)
        print(f"MTOW: {inputs.mtow_kg:.0f} kg | Landing Speed: {inputs.landing_speed_mps:.1f} m/s", file=sys.stderr)
        print("Generating concepts...", file=sys.stderr)
        
        # Generate recommendations
        generator = GearGenerator(inputs)
        result = generator.generate_result()
        
        # Output results
        output_json = result.model_dump_json(indent=2)
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(output_json)
            print(f"\nResults saved to {args.output}", file=sys.stderr)
        else:
            print(output_json)
        
        # Print summary to stderr
        print(f"\nSummary: Generated {len(result.concepts)} concepts", file=sys.stderr)
        passing = len([c for c in result.concepts if c.all_checks_passed])
        print(f"  Passing all checks: {passing}", file=sys.stderr)
        print(f"  Best score: {result.best_concept.score:.2f}", file=sys.stderr)
        
        if result.warnings:
            print("\nWarnings:", file=sys.stderr)
            for w in result.warnings:
                print(f"  - {w}", file=sys.stderr)
        
        return 0
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_sweep(args: argparse.Namespace) -> int:
    """Run sensitivity sweep."""
    try:
        # Load input
        with open(args.input) as f:
            input_data = json.load(f)
        
        inputs = AircraftInputs(**input_data)
        
        print(f"\nSensitivity Sweep", file=sys.stderr)
        print(f"Aircraft: {inputs.aircraft_name}", file=sys.stderr)
        print("Running sweep...", file=sys.stderr)
        
        # Run sweep
        generator = GearGenerator(inputs)
        result = generator.run_sweep()
        
        # Output results
        output_json = result.model_dump_json(indent=2)
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(output_json)
            print(f"\nSweep results saved to {args.output}", file=sys.stderr)
        else:
            print(output_json)
        
        # Print summary
        print(f"\nSweep Summary:", file=sys.stderr)
        print(f"  Sink rates: {result.sink_rates_swept}", file=sys.stderr)
        print(f"  CG positions: {[f'{x:.2f}' for x in result.cg_positions_swept]}", file=sys.stderr)
        print(f"  Most robust concept: {result.most_robust_concept}", file=sys.stderr)
        
        for cr in result.concept_results:
            print(f"  {cr.config.value} {cr.gear_type.value}: "
                  f"pass_rate={cr.pass_rate:.0%}, avg_score={cr.avg_score:.2f}", file=sys.stderr)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the FastAPI web server."""
    try:
        import uvicorn
        
        print(f"\nStarting Landing Gear Recommender API", file=sys.stderr)
        print(f"API: http://{args.host}:{args.port}/", file=sys.stderr)
        print(f"Docs: http://{args.host}:{args.port}/docs", file=sys.stderr)
        print(f"UI: http://{args.host}:{args.port}/", file=sys.stderr)
        print("\nPress Ctrl+C to stop\n", file=sys.stderr)
        
        uvicorn.run(
            "gearrec.api.server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0
        
    except ImportError as e:
        print(f"Error: Missing dependency: {e}", file=sys.stderr)
        print("Install with: pip install uvicorn fastapi", file=sys.stderr)
        return 1


def cli():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    commands = {
        "make-example": cmd_make_example,
        "recommend": cmd_recommend,
        "sweep": cmd_sweep,
        "serve": cmd_serve,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(cli())
