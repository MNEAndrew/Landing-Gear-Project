"""
Entry point for running gearrec as a module.

Usage:
    python -m gearrec recommend --input example.json
    python -m gearrec make-example
    python -m gearrec serve --port 8000
"""

from gearrec.cli.main import cli

if __name__ == "__main__":
    cli()

