"""
Tire catalog loader.

Loads pre-parsed tire specifications and application data from JSON files.
"""

import json
from pathlib import Path
from typing import Optional

from gearrec.tire_catalog.models import TireSpec, ApplicationRow


# Default catalog paths relative to project root
DEFAULT_TIRES_PATH = "data/goodyear_2022_tires.json"
DEFAULT_APPS_PATH = "data/goodyear_2022_applications.json"


def get_project_root() -> Path:
    """Get the project root directory."""
    # Try to find project root by looking for pyproject.toml
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to current working directory
    return Path.cwd()


def catalog_exists(
    tires_path: Optional[str] = None,
    apps_path: Optional[str] = None,
) -> bool:
    """
    Check if tire catalog JSON files exist.
    
    Args:
        tires_path: Path to tires JSON (optional)
        apps_path: Path to applications JSON (optional)
        
    Returns:
        True if at least the tires file exists
    """
    root = get_project_root()
    
    if tires_path:
        tires_file = Path(tires_path)
    else:
        tires_file = root / DEFAULT_TIRES_PATH
    
    return tires_file.exists()


def load_tire_specs(
    path: Optional[str] = None,
) -> list[TireSpec]:
    """
    Load tire specifications from JSON file.
    
    Args:
        path: Path to JSON file. If None, uses default location.
        
    Returns:
        List of TireSpec objects
        
    Raises:
        FileNotFoundError: If catalog file doesn't exist
    """
    if path:
        file_path = Path(path)
    else:
        file_path = get_project_root() / DEFAULT_TIRES_PATH
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Tire catalog not found at {file_path}. "
            f"Run 'python -m gearrec import-tires' to generate it."
        )
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return [TireSpec(**item) for item in data]


def load_applications(
    path: Optional[str] = None,
) -> list[ApplicationRow]:
    """
    Load application charts from JSON file.
    
    Args:
        path: Path to JSON file. If None, uses default location.
        
    Returns:
        List of ApplicationRow objects
        
    Raises:
        FileNotFoundError: If catalog file doesn't exist
    """
    if path:
        file_path = Path(path)
    else:
        file_path = get_project_root() / DEFAULT_APPS_PATH
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Application charts not found at {file_path}. "
            f"Run 'python -m gearrec import-tires' to generate it."
        )
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return [ApplicationRow(**item) for item in data]


def load_all_catalogs(
    tires_path: Optional[str] = None,
    apps_path: Optional[str] = None,
) -> tuple[list[TireSpec], list[ApplicationRow]]:
    """
    Load both tire specs and application charts.
    
    Args:
        tires_path: Path to tires JSON (optional)
        apps_path: Path to applications JSON (optional)
        
    Returns:
        Tuple of (tire_specs, application_rows)
    """
    tires = load_tire_specs(tires_path)
    
    try:
        apps = load_applications(apps_path)
    except FileNotFoundError:
        apps = []  # Applications are optional
    
    return tires, apps

