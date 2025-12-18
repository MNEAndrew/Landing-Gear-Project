"""
Quick formatter for example_output.json to make it easier to skim.

Usage:
    python pretty_example_output.py
    python pretty_example_output.py --input path/to/result.json --max-tires 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gearrec.cli.readable_output import print_readable_output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a readable summary of example_output.json"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("example_output.json"),
        help="Path to a recommendation JSON file (default: example_output.json)",
    )
    parser.add_argument(
        "--max-tires",
        type=int,
        default=3,
        help="Max tire matches to show per category",
    )
    args = parser.parse_args()

    print_readable_output(
        json_path=args.input,
        include_pdf_matches=False,
        max_tire_rows=args.max_tires,
    )


if __name__ == "__main__":
    main()
