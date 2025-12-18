"""
Command-line interface for landing gear recommender.

Usage:
    python -m gearrec recommend --input example.json [--output results.json]
    python -m gearrec make-example [--output example_input.json]
    python -m gearrec serve [--port 8000]
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from gearrec.models.inputs import AircraftInputs, RunwayType, DesignPriorities
from gearrec.generator.candidates import GearGenerator

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="gearrec")
def cli():
    """
    Landing Gear Recommender - Conceptual sizing tool for aircraft landing gear.
    
    WARNING: This tool provides rough conceptual estimates only.
    Not for certification or detailed design purposes.
    """
    pass


@cli.command()
@click.option(
    "--input", "-i",
    "input_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to JSON input file with aircraft parameters",
)
@click.option(
    "--output", "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional path to save JSON output",
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="json",
    help="Output format (json or table)",
)
def recommend(input_file: Path, output_file: Path | None, output_format: str):
    """
    Generate landing gear recommendations from input parameters.
    
    Reads aircraft parameters from a JSON file and outputs 3-6 candidate
    gear configurations with geometry, loads, and scoring.
    """
    try:
        # Load input
        with open(input_file) as f:
            input_data = json.load(f)
        
        # Parse and validate
        inputs = AircraftInputs(**input_data)
        
        console.print(f"\n[bold blue]Landing Gear Recommender[/bold blue]")
        console.print(f"Aircraft: [bold]{inputs.aircraft_name}[/bold]")
        console.print(f"MTOW: {inputs.mtow_kg:.0f} kg | Landing Speed: {inputs.landing_speed_mps:.1f} m/s")
        console.print()
        
        # Generate recommendations
        with console.status("[bold green]Generating gear concepts..."):
            generator = GearGenerator(inputs)
            result = generator.generate_result()
        
        # Output results
        if output_format == "table":
            _print_table_output(result)
        else:
            output_json = result.model_dump_json(indent=2)
            
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output_json)
                console.print(f"\n[green]Results saved to {output_file}[/green]")
            else:
                print(output_json)
        
        # Print summary
        console.print(f"\n[bold]Summary:[/bold] Generated {len(result.concepts)} concepts")
        passing = len([c for c in result.concepts if c.all_checks_passed])
        console.print(f"  Passing all checks: {passing}")
        console.print(f"  Best score: {result.best_concept.score:.2f}")
        
        if result.warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for w in result.warnings:
                console.print(f"  • {w}")
        
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid JSON in {input_file}: {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


def _print_table_output(result):
    """Print results as formatted tables."""
    from gearrec.models.outputs import RecommendationResult
    
    # Summary table
    console.print("\n[bold]Gear Concepts[/bold]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Config", width=12)
    table.add_column("Type", width=12)
    table.add_column("Wheels", width=8)
    table.add_column("Track (m)", width=10)
    table.add_column("Wheelbase (m)", width=12)
    table.add_column("Score", width=8)
    table.add_column("Checks", width=8)
    
    for i, concept in enumerate(result.concepts, 1):
        checks_status = "✓ Pass" if concept.all_checks_passed else "✗ Fail"
        checks_style = "green" if concept.all_checks_passed else "red"
        
        table.add_row(
            str(i),
            concept.config.value.title(),
            concept.gear_type.value.title(),
            f"{concept.wheel_count_main}M/{concept.wheel_count_nose_or_tail}N",
            f"{concept.geometry.track_m.min:.2f}-{concept.geometry.track_m.max:.2f}",
            f"{concept.geometry.wheelbase_m.min:.2f}-{concept.geometry.wheelbase_m.max:.2f}",
            f"{concept.score:.2f}",
            Text(checks_status, style=checks_style),
        )
    
    console.print(table)
    
    # Detailed view of best concept
    best = result.best_concept
    console.print(f"\n[bold]Best Concept Details ({best.config.value.title()} {best.gear_type.value.title()})[/bold]")
    
    details_table = Table(show_header=False, box=None, padding=(0, 2))
    details_table.add_column("Parameter", style="cyan")
    details_table.add_column("Value")
    
    details_table.add_row("Track", f"{best.geometry.track_m.min:.2f} - {best.geometry.track_m.max:.2f} m")
    details_table.add_row("Wheelbase", f"{best.geometry.wheelbase_m.min:.2f} - {best.geometry.wheelbase_m.max:.2f} m")
    details_table.add_row("Main Strut", f"{best.geometry.main_strut_length_m.min:.2f} - {best.geometry.main_strut_length_m.max:.2f} m")
    details_table.add_row("Stroke", f"{best.geometry.stroke_m.min:.2f} - {best.geometry.stroke_m.max:.2f} m")
    details_table.add_row("", "")
    details_table.add_row("Static Main Load", f"{best.loads.static_main_load_total_N:.0f} N")
    details_table.add_row("Per-Wheel Load", f"{best.loads.static_main_load_per_wheel_N:.0f} N")
    details_table.add_row("Landing Energy", f"{best.loads.landing_energy_J:.0f} J")
    details_table.add_row("", "")
    details_table.add_row("Tire Diameter", f"{best.tire_suggestion.recommended_tire_diameter_range_m.min:.2f} - {best.tire_suggestion.recommended_tire_diameter_range_m.max:.2f} m")
    
    console.print(details_table)
    
    # Explanation
    console.print("\n[bold]Explanation:[/bold]")
    for point in best.explanation:
        console.print(f"  • {point}")
    
    # Assumptions
    console.print("\n[bold dim]Assumptions:[/bold dim]")
    for assumption in result.assumptions[:4]:  # Show first 4
        console.print(f"  [dim]• {assumption}[/dim]")


@cli.command("make-example")
@click.option(
    "--output", "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=Path("example_input.json"),
    help="Output path for example input file",
)
def make_example(output_file: Path):
    """
    Generate an example input JSON file.
    
    Creates a sample input file with typical GA aircraft parameters
    that can be modified and used with the recommend command.
    """
    example = AircraftInputs(
        aircraft_name="GA-2024 Trainer",
        mtow_kg=1200.0,
        mlw_kg=1140.0,
        cg_fwd_m=2.10,
        cg_aft_m=2.45,
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
        design_priorities=DesignPriorities(
            robustness=1.0,
            low_drag=0.5,
            low_mass=1.0,
            simplicity=1.5,
        ),
    )
    
    # Convert to dict and write
    output_json = example.model_dump_json(indent=2)
    
    with open(output_file, "w") as f:
        f.write(output_json)
    
    console.print(f"[green]Created example input file: {output_file}[/green]")
    console.print("\nExample contents:")
    console.print(Panel(output_json, title="example_input.json", border_style="blue"))
    console.print("\n[dim]Edit this file and run:[/dim]")
    console.print(f"  python -m gearrec recommend --input {output_file}")


@cli.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to",
)
@click.option(
    "--port", "-p",
    default=8000,
    help="Port to listen on",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)
def serve(host: str, port: int, reload: bool):
    """
    Start the FastAPI web server.
    
    Provides a REST API for gear recommendations at http://host:port/
    API documentation available at http://host:port/docs
    """
    try:
        import uvicorn
        from gearrec.api.server import app
        
        console.print(f"\n[bold blue]Starting Landing Gear Recommender API[/bold blue]")
        console.print(f"API: http://{host}:{port}/")
        console.print(f"Docs: http://{host}:{port}/docs")
        console.print("\nPress Ctrl+C to stop\n")
        
        uvicorn.run(
            "gearrec.api.server:app",
            host=host,
            port=port,
            reload=reload,
        )
    except ImportError as e:
        console.print(f"[bold red]Error:[/bold red] Missing dependency: {e}")
        console.print("Install with: pip install uvicorn fastapi")
        sys.exit(1)


if __name__ == "__main__":
    cli()

