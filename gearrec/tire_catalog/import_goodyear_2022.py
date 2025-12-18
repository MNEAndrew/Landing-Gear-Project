"""
PDF importer for Goodyear 2022 tire data.

Parses the Data Section and Application Charts PDFs to extract
tire specifications and aircraft application mappings.

Usage:
    python -m gearrec.tire_catalog.import_goodyear_2022 \\
        --data-section "data/Data-Section-2022 (1).pdf" \\
        --app-charts "data/Application-Charts-2022 (1).pdf"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from gearrec.tire_catalog.models import TireSpec, ApplicationRow


# Regex patterns for tire size detection
# Matches patterns like: 24x7.25-10, 6.00-6, 15X6.0-6, 8.50-10, etc.
TIRE_SIZE_PATTERN = re.compile(
    r'^([A-Z]?\d+(?:\.\d+)?[xX]\d+(?:\.\d+)?-\d+(?:\.\d+)?)\s+',
    re.IGNORECASE
)

# Alternative pattern for sizes like "6.00-6" (no x dimension)
TIRE_SIZE_ALT_PATTERN = re.compile(
    r'^(\d+\.\d+-\d+)\s+',
    re.IGNORECASE
)

# Pattern for metric sizes like "380x150-6"
TIRE_SIZE_METRIC_PATTERN = re.compile(
    r'^(\d{3}[xX]\d{2,3}-\d+)\s+',
    re.IGNORECASE
)


def parse_number(s: str) -> Optional[float]:
    """Parse a string to float, returning None if invalid."""
    if not s:
        return None
    s = s.strip().replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None


def parse_tire_data_line(line: str, page: int) -> Optional[TireSpec]:
    """
    Parse a single line from the tire data section.
    
    Expected format (columns may vary):
    <Size> <Ply> <TT/TL> <Speed> <RatedLoad> <Inflation> <MaxBraking> <MaxBottoming> ... 
    <PartNumber> ... <OD> <...> <SectionWidth> ...
    
    Returns TireSpec if valid line, None otherwise.
    """
    line = line.strip()
    if not line:
        return None
    
    # Try to match tire size at start
    size_match = (
        TIRE_SIZE_PATTERN.match(line) or 
        TIRE_SIZE_ALT_PATTERN.match(line) or
        TIRE_SIZE_METRIC_PATTERN.match(line)
    )
    
    if not size_match:
        return None
    
    size = size_match.group(1).upper()
    remainder = line[size_match.end():].strip()
    
    # Split remaining tokens
    tokens = remainder.split()
    
    if len(tokens) < 3:
        return None
    
    # Try to extract values from tokens
    # Common patterns in tire tables:
    # Ply, TT/TL, Speed, RatedLoad, Inflation, BrakingLoad, BottomingLoad, ...
    
    ply_rating = None
    tt_tl = None
    rated_speed = None
    rated_load = None
    rated_inflation = None
    max_braking = None
    max_bottoming = None
    outside_diameter = None
    section_width = None
    part_number = None
    
    # Look for ply rating (usually first, single digit or like "6PR")
    idx = 0
    if idx < len(tokens):
        token = tokens[idx]
        if re.match(r'^\d{1,2}(PR)?$', token, re.IGNORECASE):
            ply_rating = token.replace('PR', '').strip()
            idx += 1
    
    # Look for TT/TL
    if idx < len(tokens):
        token = tokens[idx].upper()
        if token in ('TT', 'TL', 'TT/TL'):
            tt_tl = token
            idx += 1
    
    # Try to find numeric values for speed, load, inflation, etc.
    # These are typically in sequence after TT/TL
    numbers = []
    part_nums = []
    
    for i in range(idx, len(tokens)):
        token = tokens[i]
        num = parse_number(token)
        if num is not None:
            numbers.append((i, num))
        elif re.match(r'^[A-Z0-9]{5,}', token, re.IGNORECASE):
            # Might be part number
            part_nums.append(token)
    
    # Assign numbers based on typical column order
    # Usually: Speed (mph), Load (lbs), Inflation (psi), Braking, Bottoming, ...
    # then later OD, Width, etc.
    
    if len(numbers) >= 1:
        # First number could be speed (if < 300) or load (if > 300)
        first_val = numbers[0][1]
        num_idx = 0
        
        if first_val < 300:  # Likely speed
            rated_speed = first_val
            num_idx = 1
        
        # Next should be rated load (typically 500-50000 range)
        if num_idx < len(numbers):
            val = numbers[num_idx][1]
            if 100 < val < 100000:
                rated_load = val
                num_idx += 1
        
        # Next should be inflation pressure (typically 20-500 psi)
        if num_idx < len(numbers):
            val = numbers[num_idx][1]
            if 10 < val < 600:
                rated_inflation = val
                num_idx += 1
        
        # Next could be braking load
        if num_idx < len(numbers):
            val = numbers[num_idx][1]
            if 100 < val < 200000:
                max_braking = val
                num_idx += 1
        
        # Next could be bottoming load
        if num_idx < len(numbers):
            val = numbers[num_idx][1]
            if 100 < val < 200000:
                max_bottoming = val
                num_idx += 1
        
        # Look for OD (typically 5-50 inches) later in the sequence
        for i in range(num_idx, len(numbers)):
            val = numbers[i][1]
            if 5 < val < 60 and outside_diameter is None:
                outside_diameter = val
            elif 2 < val < 20 and section_width is None and outside_diameter is not None:
                section_width = val
    
    if part_nums:
        part_number = part_nums[0]
    
    # Must have at least rated load to be valid
    if rated_load is None:
        return None
    
    return TireSpec(
        source="goodyear_2022",
        size=size,
        ply_rating=ply_rating,
        tt_tl=tt_tl,
        rated_speed_mph=rated_speed,
        rated_load_lbs=rated_load,
        rated_inflation_psi=rated_inflation,
        max_braking_load_lbs=max_braking,
        max_bottoming_load_lbs=max_bottoming,
        outside_diameter_in=outside_diameter,
        section_width_in=section_width,
        part_number=part_number,
        raw_line=line,
        page=page,
    )


def parse_application_line(line: str, page: int) -> Optional[ApplicationRow]:
    """
    Parse a single line from the application charts.
    
    Expected format (varies):
    <Model> <MainTire> <MainPly> <TT/TL> <AuxTire> <AuxPly> <TT/TL>
    or
    <Manufacturer> <Model> <MainTire> ...
    
    Returns ApplicationRow if valid, None otherwise.
    """
    line = line.strip()
    if not line:
        return None
    
    # Skip header lines and notes
    if any(skip in line.upper() for skip in [
        'AIRCRAFT', 'MODEL', 'MAIN', 'NOSE', 'TAIL', 'AUX', 
        'NOTE:', 'WARNING', 'TIRE SIZE', 'PLY', '---', '==='
    ]):
        return None
    
    tokens = line.split()
    if len(tokens) < 2:
        return None
    
    # Try to find tire size patterns in the line
    tire_sizes = []
    tire_indices = []
    
    for i, token in enumerate(tokens):
        if (TIRE_SIZE_PATTERN.match(token + ' ') or 
            TIRE_SIZE_ALT_PATTERN.match(token + ' ') or
            TIRE_SIZE_METRIC_PATTERN.match(token + ' ')):
            tire_sizes.append(token.upper())
            tire_indices.append(i)
    
    if not tire_sizes:
        return None
    
    # Model is typically before the first tire size
    first_tire_idx = tire_indices[0] if tire_indices else len(tokens)
    model_parts = tokens[:first_tire_idx]
    
    if not model_parts:
        return None
    
    # Determine manufacturer vs model
    manufacturer = None
    model = ' '.join(model_parts)
    
    # Common manufacturers
    manufacturers = [
        'CESSNA', 'PIPER', 'BEECH', 'BEECHCRAFT', 'MOONEY', 'CIRRUS',
        'DIAMOND', 'GRUMMAN', 'BELLANCA', 'MAULE', 'VANS', "VAN'S",
        'AMERICAN CHAMPION', 'AVIAT', 'EXTRA', 'PITTS', 'AERONCA',
        'BOEING', 'AIRBUS', 'EMBRAER', 'BOMBARDIER', 'PILATUS'
    ]
    
    for mfr in manufacturers:
        if model.upper().startswith(mfr):
            manufacturer = mfr
            model = model[len(mfr):].strip()
            break
    
    main_tire = tire_sizes[0] if len(tire_sizes) >= 1 else None
    aux_tire = tire_sizes[1] if len(tire_sizes) >= 2 else None
    
    # Try to find ply ratings near tire sizes
    main_ply = None
    aux_ply = None
    
    for i, idx in enumerate(tire_indices):
        if idx + 1 < len(tokens):
            next_token = tokens[idx + 1]
            if re.match(r'^\d{1,2}(PR)?$', next_token, re.IGNORECASE):
                if i == 0:
                    main_ply = next_token.replace('PR', '')
                elif i == 1:
                    aux_ply = next_token.replace('PR', '')
    
    # Look for TT/TL codes
    code_parts = []
    for token in tokens:
        if token.upper() in ('TT', 'TL'):
            code_parts.append(token.upper())
    code = '/'.join(code_parts) if code_parts else None
    
    return ApplicationRow(
        manufacturer=manufacturer,
        model=model,
        main_tire_size=main_tire,
        aux_tire_size=aux_tire,
        main_ply=main_ply,
        aux_ply=aux_ply,
        code=code,
        page=page,
        raw_line=line,
    )


def import_data_section(pdf_path: str) -> list[TireSpec]:
    """
    Import tire specifications from the Data Section PDF.
    
    Args:
        pdf_path: Path to the Data Section PDF
        
    Returns:
        List of TireSpec objects
    """
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber is required. Install with: pip install pdfplumber")
        sys.exit(1)
    
    specs = []
    seen_sizes = set()  # Track unique size+ply combinations
    
    print(f"Parsing Data Section PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split('\n'):
                spec = parse_tire_data_line(line, page_num)
                if spec:
                    # Deduplicate by size + ply
                    key = f"{spec.size}_{spec.ply_rating}"
                    if key not in seen_sizes:
                        seen_sizes.add(key)
                        specs.append(spec)
    
    print(f"  Parsed {len(specs)} unique tire specifications")
    return specs


def import_application_charts(pdf_path: str) -> list[ApplicationRow]:
    """
    Import application charts from the Application Charts PDF.
    
    Args:
        pdf_path: Path to the Application Charts PDF
        
    Returns:
        List of ApplicationRow objects
    """
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber is required. Install with: pip install pdfplumber")
        sys.exit(1)
    
    apps = []
    seen_models = set()
    
    print(f"Parsing Application Charts PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split('\n'):
                app = parse_application_line(line, page_num)
                if app:
                    key = f"{app.model}_{app.main_tire_size}"
                    if key not in seen_models:
                        seen_models.add(key)
                        apps.append(app)
    
    print(f"  Parsed {len(apps)} application rows")
    return apps


def run_import(
    data_section_path: str,
    app_charts_path: str,
    output_dir: str = "data",
) -> tuple[Path, Path]:
    """
    Run the full import process.
    
    Args:
        data_section_path: Path to Data Section PDF
        app_charts_path: Path to Application Charts PDF
        output_dir: Directory for output JSON files
        
    Returns:
        Tuple of (tires_json_path, applications_json_path)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Import tire specs
    specs = import_data_section(data_section_path)
    tires_path = output_path / "goodyear_2022_tires.json"
    with open(tires_path, 'w') as f:
        json.dump([s.model_dump() for s in specs], f, indent=2)
    print(f"Wrote {len(specs)} tires to {tires_path}")
    
    # Import application charts
    apps = import_application_charts(app_charts_path)
    apps_path = output_path / "goodyear_2022_applications.json"
    with open(apps_path, 'w') as f:
        json.dump([a.model_dump() for a in apps], f, indent=2)
    print(f"Wrote {len(apps)} applications to {apps_path}")
    
    return tires_path, apps_path


def main():
    """CLI entry point for tire import."""
    parser = argparse.ArgumentParser(
        description="Import Goodyear 2022 tire data from PDFs"
    )
    parser.add_argument(
        "--data-section",
        required=True,
        help="Path to Data-Section-2022 PDF"
    )
    parser.add_argument(
        "--app-charts",
        required=True,
        help="Path to Application-Charts-2022 PDF"
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory for JSON files (default: data)"
    )
    
    args = parser.parse_args()
    
    # Validate inputs exist
    if not Path(args.data_section).exists():
        print(f"Error: Data section PDF not found: {args.data_section}")
        sys.exit(1)
    if not Path(args.app_charts).exists():
        print(f"Error: Application charts PDF not found: {args.app_charts}")
        sys.exit(1)
    
    run_import(args.data_section, args.app_charts, args.output_dir)
    print("\nImport complete!")


if __name__ == "__main__":
    main()

