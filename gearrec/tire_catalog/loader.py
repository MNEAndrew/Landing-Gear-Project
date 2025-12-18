"""
Tire catalog loader.

Loads pre-parsed tire specifications and application data from JSON files.
"""

import json
import importlib.resources as resources
from pathlib import Path
from typing import Optional

from gearrec.tire_catalog.models import TireSpec, ApplicationRow


# Default catalog filenames
DEFAULT_TIRES_NAME = "goodyear_2022_tires.json"
DEFAULT_APPS_NAME = "goodyear_2022_applications.json"
DEFAULT_TIRES_PATH = f"data/{DEFAULT_TIRES_NAME}"
DEFAULT_APPS_PATH = f"data/{DEFAULT_APPS_NAME}"


def get_project_root() -> Path:
    """Get the project root directory."""
    # Try to find project root by looking for pyproject.toml
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to current working directory
    return Path.cwd()


def _resource_path(filename: str) -> Optional[Path]:
    """
    Resolve a packaged data file inside gearrec.data.
    
    Returns a filesystem path (even when running from a zip/pyinstaller)
    or None if the resource is unavailable.
    """
    try:
        resource = resources.files("gearrec.data").joinpath(filename)
        if resource.is_file():
            with resources.as_file(resource) as tmp_path:
                return Path(tmp_path)
    except Exception:
        return None
    return None


def _resolve_catalog_file(filename: str) -> Path:
    """Find the best available path for a catalog file."""
    candidates = [
        get_project_root() / "data" / filename,  # project / editable install
        Path.cwd() / "data" / filename,          # current working dir
    ]

    pkg_path = _resource_path(filename)
    if pkg_path:
        candidates.append(pkg_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Default to first candidate for error reporting
    return candidates[0]


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
    if tires_path:
        tires_file = Path(tires_path)
    else:
        tires_file = _resolve_catalog_file(DEFAULT_TIRES_NAME)
    
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
        file_path = _resolve_catalog_file(DEFAULT_TIRES_NAME)
    
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
        file_path = _resolve_catalog_file(DEFAULT_APPS_NAME)
    
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

