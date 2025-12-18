"""
Simple helper to bump the gearrec version in source and pyproject (if present).

Usage:
    python scripts/bump_version.py 0.1.0-beta
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = ROOT / "gearrec" / "__init__.py"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def replace_version_in_init(new_version: str) -> None:
    text = INIT_PATH.read_text()
    new_text, count = re.subn(r'__version__\s*=\s*"[^\"]+"', f'__version__ = "{new_version}"', text)
    if count == 0:
        raise SystemExit("Could not find __version__ in gearrec/__init__.py")
    INIT_PATH.write_text(new_text)


def replace_version_in_pyproject(new_version: str) -> None:
    """
    Update a static version in pyproject.toml if present.
    When using dynamic versioning, this is a no-op.
    """
    text = PYPROJECT_PATH.read_text()
    pattern = r'version\s*=\s*"[^\"]+"'
    if 'dynamic = ["version"]' in text:
        return
    new_text, count = re.subn(pattern, f'version = "{new_version}"', text, count=1)
    if count:
        PYPROJECT_PATH.write_text(new_text)


def main(new_version: str) -> None:
    replace_version_in_init(new_version)
    replace_version_in_pyproject(new_version)
    print(f"Bumped version to {new_version}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/bump_version.py <new-version>")
    main(sys.argv[1])
