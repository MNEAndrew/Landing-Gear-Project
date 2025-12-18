# Tire Catalog Data

This directory contains the parsed tire catalog data from Goodyear PDFs.

## Source PDFs

Place the following PDFs in this directory (or parent):

- `Data-Section-2022 (1).pdf` - Contains tire specifications (load ratings, dimensions, etc.)
- `Application-Charts-2022 (1).pdf` - Maps aircraft models to tire sizes

## Importing Data

Run the import command to parse the PDFs and generate JSON catalogs:

```bash
python -m gearrec import-tires \
    --data-section "Data-Section-2022 (1).pdf" \
    --app-charts "Application-Charts-2022 (1).pdf" \
    --output-dir data
```

This will generate:
- `data/goodyear_2022_tires.json` - Parsed tire specifications
- `data/goodyear_2022_applications.json` - Aircraft model -> tire mappings

## Generated Files

### goodyear_2022_tires.json

Array of tire specifications with fields:
- `source`: Data source identifier (e.g., "goodyear_2022")
- `size`: Tire size designation (e.g., "6.00-6")
- `ply_rating`: Ply rating (e.g., "6", "8")
- `tt_tl`: Tube type ("TT" or "TL")
- `rated_load_lbs`: Rated load capacity in pounds
- `rated_inflation_psi`: Rated inflation pressure in psi
- `max_braking_load_lbs`: Maximum braking load
- `max_bottoming_load_lbs`: Maximum bottoming load
- `outside_diameter_in`: Outside diameter in inches
- `section_width_in`: Section width in inches
- `raw_line`: Original text for traceability
- `page`: Source PDF page number

### goodyear_2022_applications.json

Array of aircraft application mappings:
- `manufacturer`: Aircraft manufacturer
- `model`: Aircraft model
- `main_tire_size`: Main gear tire size
- `aux_tire_size`: Nose/tail tire size
- `main_ply`: Main tire ply rating
- `aux_ply`: Auxiliary tire ply rating
- `raw_line`: Original text for traceability

## Usage

After importing, use the `--use-pdf-tires` flag with recommendations:

```bash
python -m gearrec recommend --input example_input.json --use-pdf-tires
```

Or via API:

```bash
curl -X POST "http://localhost:8000/recommend?use_pdf_tires=true" \
    -H "Content-Type: application/json" \
    -d @example_input.json
```

## Important Warning

**CONCEPTUAL SIZING ONLY - NOT FOR CERTIFICATION**

Application charts are general reference only. Always verify tire selections with:
- Airframe manufacturer
- Tire manufacturer
- Applicable airworthiness authorities

The parsed data may contain errors due to PDF parsing limitations. Always verify against the original PDFs.

