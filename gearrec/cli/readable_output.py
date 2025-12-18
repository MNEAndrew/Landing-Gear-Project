"""
Helpers to turn JSON recommendation outputs into a compact, human-readable
console summary. Useful for quickly scanning example_output.json files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _fmt_range(range_dict: dict[str, Any] | None) -> str:
    """Format a {"min": x, "max": y} dict into a friendly string."""
    if not range_dict:
        return "n/a"
    try:
        r_min = float(range_dict["min"])
        r_max = float(range_dict["max"])
    except (KeyError, TypeError, ValueError):
        return "n/a"
    mid = (r_min + r_max) / 2
    return f"{r_min:.2f}-{r_max:.2f} (mid {mid:.2f})"


def _fmt_float(value: Any, unit: str = "", zero_default: str = "n/a") -> str:
    """Safely format a float with optional unit suffix."""
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return zero_default
    suffix = f" {unit}" if unit else ""
    if abs(fval) >= 100:
        return f"{fval:,.0f}{suffix}"
    return f"{fval:.2f}{suffix}"


def _all_checks_passed(checks: dict[str, Any] | None) -> bool:
    """Determine if all mandatory checks passed."""
    if not checks:
        return False
    return bool(
        checks.get("tip_back_margin", {}).get("passed")
        and checks.get("nose_over_margin", {}).get("passed")
        and checks.get("ground_clearance_ok", False)
        and checks.get("lateral_stability_ok", False)
        and checks.get("prop_clearance_ok", False)
    )


def _print_tire_section(tire: dict[str, Any], include_pdf_matches: bool, max_items: int) -> None:
    """Render tire suggestions and matches."""
    print(
        f"  Tires: static { _fmt_float(tire.get('required_static_load_per_wheel_N'), 'N') } | "
        f"dynamic { _fmt_float(tire.get('required_dynamic_load_per_wheel_N'), 'N') }"
    )
    print(
        f"         diameter { _fmt_range(tire.get('recommended_tire_diameter_range_m')) } m | "
        f"width { _fmt_range(tire.get('recommended_tire_width_range_m')) } m"
    )

    catalog = tire.get("matched_catalog_tires") or []
    if catalog:
        to_show = min(len(catalog), max_items)
        print(f"         catalog matches (showing {to_show} of {len(catalog)}):")
        for t in catalog[:max_items]:
            pressure = t.get("max_pressure_kpa")
            pressure_str = f"{_fmt_float(pressure, 'kPa')}" if pressure is not None else "n/a"
            print(
                f"           - {t.get('name', '?')}: "
                f"dia {_fmt_float(t.get('diameter_m'), 'm')}, "
                f"width {_fmt_float(t.get('width_m'), 'm')}, "
                f"load {_fmt_float(t.get('max_load_N'), 'N')}, "
                f"pressure {pressure_str}"
            )

    if include_pdf_matches:
        main_matches = tire.get("matched_main_tires") or []
        nose_matches = tire.get("matched_nose_or_tail_tires") or []
        if main_matches:
            print(f"         PDF main tires (top {min(len(main_matches), max_items)}):")
            for t in main_matches[:max_items]:
                print(
                    f"           - {t.get('size', '?')} "
                    f"({t.get('ply_rating', '?')} ply) "
                    f"margin { _fmt_float(t.get('margin_load') * 100 if t.get('margin_load') is not None else None, '%') } "
                    f"score { _fmt_float(t.get('score'), '') }"
                )
        if nose_matches:
            print(f"         PDF nose/tail tires (top {min(len(nose_matches), max_items)}):")
            for t in nose_matches[:max_items]:
                print(
                    f"           - {t.get('size', '?')} "
                    f"({t.get('ply_rating', '?')} ply) "
                    f"margin { _fmt_float(t.get('margin_load') * 100 if t.get('margin_load') is not None else None, '%') } "
                    f"score { _fmt_float(t.get('score'), '') }"
                )
        warnings = tire.get("tire_selection_warnings") or []
        for w in warnings:
            print(f"         ! {w}")


def print_readable_output(
    json_path: Path,
    include_pdf_matches: bool = False,
    max_tire_rows: int = 3,
) -> None:
    """
    Print a human-friendly summary of a recommendation JSON file.

    Args:
        json_path: Path to the JSON output file.
        include_pdf_matches: Whether to show PDF tire match details.
        max_tire_rows: Max number of tire entries to show per category.
    """
    data = json.loads(Path(json_path).read_text())
    concepts = data.get("concepts", [])

    print(f"Aircraft: {data.get('aircraft_name', '?')}")
    print(f"Concepts: {len(concepts)} | Assumptions: {len(data.get('assumptions', []))}")

    if concepts:
        best = max(concepts, key=lambda c: c.get("score", 0))
        print(
            f"Best: {best.get('config')}/{best.get('gear_type')} "
            f"score {_fmt_float(best.get('score'))}"
        )

    warnings = data.get("warnings") or []
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")

    for idx, concept in enumerate(concepts, 1):
        checks = concept.get("checks", {})
        loads = concept.get("loads", {})
        geom = concept.get("geometry", {})
        tires = concept.get("tire_suggestion", {})

        print(
            f"\n[{idx}] {concept.get('config', '?')}/{concept.get('gear_type', '?')} | "
            f"score {_fmt_float(concept.get('score'))} | "
            f"checks {'PASS' if _all_checks_passed(checks) else 'FAIL'}"
        )
        print(
            f"  Loads: main/wheel {_fmt_float(loads.get('static_main_load_per_wheel_N'), 'N')}, "
            f"nose frac {_fmt_float(loads.get('nose_load_fraction', 0) * 100, '%')}, "
            f"energy {_fmt_float(loads.get('landing_energy_J'), 'J')}"
        )
        print(
            f"  Geometry (m): track {_fmt_range(geom.get('track_m'))}; "
            f"wheelbase {_fmt_range(geom.get('wheelbase_m'))}; "
            f"stroke {_fmt_range(geom.get('stroke_m'))}"
        )
        _print_tire_section(tires, include_pdf_matches, max_tire_rows)

        tip = checks.get("tip_back_margin")
        nose_over = checks.get("nose_over_margin")
        rollover = _fmt_float(checks.get("rollover_angle_deg"), "deg")
        prop_margin = _fmt_float(checks.get("prop_clearance_margin_m"), "m")
        print(
            f"  Checks: tip-back {_fmt_float(tip.get('value') if tip else None)} "
            f"(limit {_fmt_float(tip.get('limit') if tip else None)}), "
            f"nose-over {_fmt_float(nose_over.get('value') if nose_over else None)} "
            f"(limit {_fmt_float(nose_over.get('limit') if nose_over else None)}), "
            f"rollover {rollover}, prop margin {prop_margin}"
        )

        explanation = concept.get("explanation") or []
        if explanation:
            print("  Notes:")
            for note in explanation:
                print(f"    - {note}")
