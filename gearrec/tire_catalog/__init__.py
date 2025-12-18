"""
Tire catalog module for PDF-driven tire selection.

Provides parsing of Goodyear tire data PDFs and matching logic
to select appropriate tires for landing gear concepts.

WARNING: This is for CONCEPTUAL SIZING ONLY, NOT certification.
Verify all tire selections with airframe manufacturer and tire manufacturer.
"""

from gearrec.tire_catalog.models import TireSpec, ApplicationRow, MatchedTire
from gearrec.tire_catalog.loader import load_tire_specs, load_applications, catalog_exists
from gearrec.tire_catalog.matcher import (
    choose_tires_for_concept,
    n_to_lbf,
    lbf_to_n,
    TireMatchResult,
)

__all__ = [
    "TireSpec",
    "ApplicationRow",
    "MatchedTire",
    "TireMatchResult",
    "load_tire_specs",
    "load_applications",
    "catalog_exists",
    "choose_tires_for_concept",
    "n_to_lbf",
    "lbf_to_n",
]

