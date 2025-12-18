# Testing Guide

This guide covers how to test the codebase and verify that tire selection works correctly.

## Running Tests

### Run All Tests

```bash
# Run all tests with verbose output
pytest

# Run with coverage report
pytest --cov=gearrec --cov-report=html

# Run specific test file
pytest tests/test_tire_catalog.py
```

### Run Specific Test Categories

```bash
# Run only tire catalog tests
pytest tests/test_tire_catalog.py -v

# Run only API tests
pytest tests/test_api.py -v

# Run only physics/calculation tests
pytest tests/test_physics.py -v

# Run only generator tests
pytest tests/test_generator.py -v
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_tire_catalog.py::TestTireMatching -v

# Run a specific test function
pytest tests/test_tire_catalog.py::TestTireMatching::test_match_selects_adequate_load -v
```

## Testing Tire Selection

There are two tire catalog systems:

1. **Internal catalog** (always available): Basic tire catalog in `gearrec/physics/tire_catalog.py`
2. **PDF-based catalog** (Goodyear 2022): Full catalog parsed from PDF files

### Testing Internal Tire Catalog

The internal catalog is used automatically when generating recommendations:

```bash
# Generate recommendations (uses internal catalog automatically)
python -m gearrec recommend --input example_input.json --output test_output.json

# Check output - should include matched_catalog_tires in each concept
python -c "import json; data = json.load(open('test_output.json')); print(json.dumps(data['concepts'][0]['tire_suggestion'], indent=2))"
```

### Testing PDF-Based Tire Catalog

The PDF-based catalog provides more comprehensive tire matching with application chart support.

#### Step 1: Import Tire Catalog from PDFs

First, you need to parse the PDF files and create the JSON catalog:

```bash
# Make sure PDFs are in the project directory
# - Application-Charts-2022 (1).pdf
# - Data-Section-2022 (1).pdf

# Import the tire data
python -m gearrec import-tires \
    --data-section "Data-Section-2022 (1).pdf" \
    --app-charts "Application-Charts-2022 (1).pdf" \
    --output-dir data
```

This will generate:
- `data/goodyear_2022_tires.json` - Parsed tire specifications
- `data/goodyear_2022_applications.json` - Aircraft model to tire mappings

#### Step 2: Verify Import Worked

Check that the catalog files were created:

```bash
# Check if catalog exists
python -c "from gearrec.tire_catalog.loader import catalog_exists; print('Catalog exists:', catalog_exists())"

# Count imported tires
python -c "from gearrec.tire_catalog.loader import load_tire_specs; specs = load_tire_specs(); print(f'Loaded {len(specs)} tire specs')"

# Count imported applications
python -c "from gearrec.tire_catalog.loader import load_applications; apps = load_applications(); print(f'Loaded {len(apps)} applications')"
```

#### Step 3: Generate Recommendations with PDF Tire Matching

```bash
# Generate recommendations using PDF tire catalog
python -m gearrec recommend \
    --input example_input.json \
    --output test_output_with_pdf_tires.json \
    --use-pdf-tires
```

#### Step 4: Verify Tire Selection in Output

Check that the output includes matched tires from the PDF catalog:

```bash
# View tire suggestions for first concept
python -c "
import json
with open('test_output_with_pdf_tires.json') as f:
    data = json.load(f)
concept = data['concepts'][0]
tire_sug = concept['tire_suggestion']

print('Required loads:')
print(f'  Static: {tire_sug[\"required_static_load_per_wheel_N\"]:.0f} N')
print(f'  Dynamic: {tire_sug[\"required_dynamic_load_per_wheel_N\"]:.0f} N')
print()

if 'matched_main_tires' in tire_sug and tire_sug['matched_main_tires']:
    print('Matched Main Tires:')
    for tire in tire_sug['matched_main_tires'][:3]:
        print(f'  {tire[\"size\"]} ({tire[\"ply_rating\"]} ply)')
        print(f'    Load capacity: {tire[\"rated_load_lbs\"]} lbs')
        print(f'    Pressure: {tire[\"rated_inflation_psi\"]} psi')
        print(f'    Score: {tire.get(\"score\", \"N/A\")}')
        print(f'    Margin: {tire.get(\"margin_load\", 0)*100:.1f}%')
        print()
else:
    print('No matched main tires found')

if 'matched_nose_or_tail_tires' in tire_sug and tire_sug['matched_nose_or_tail_tires']:
    print('Matched Nose/Tail Tires:')
    for tire in tire_sug['matched_nose_or_tail_tires'][:3]:
        print(f'  {tire[\"size\"]} ({tire[\"ply_rating\"]} ply)')
        print(f'    Load capacity: {tire[\"rated_load_lbs\"]} lbs')
        print()
"

# View any warnings or notes
python -c "
import json
with open('test_output_with_pdf_tires.json') as f:
    data = json.load(f)
concept = data['concepts'][0]
tire_sug = concept['tire_suggestion']

if 'tire_selection_warnings' in tire_sug:
    print('Warnings:')
    for warning in tire_sug['tire_selection_warnings']:
        print(f'  - {warning}')

if 'tire_selection_notes' in tire_sug:
    print('Notes:')
    for note in tire_sug['tire_selection_notes']:
        print(f'  - {note}')
"
```

### Testing Tire Matching Logic

Run the dedicated tire catalog tests:

```bash
# Run all tire catalog tests
pytest tests/test_tire_catalog.py -v

# Test specific functionality
pytest tests/test_tire_catalog.py::TestTireMatching -v
pytest tests/test_tire_catalog.py::TestUnitConversions -v
pytest tests/test_tire_catalog.py::TestPDFParsing -v
```

Key tests to verify:
- **TestTireMatching::test_match_selects_adequate_load** - Ensures tires meet load requirements
- **TestTireMatching::test_pressure_limit_filters_tires** - Verifies pressure limits work
- **TestTireMatching::test_grass_runway_prefers_wider_tires** - Checks runway-specific preferences
- **TestTireMatching::test_application_chart_bonus** - Verifies application chart matching

### Testing via API

You can also test tire selection via the web API:

```bash
# Start the API server
python -m gearrec serve --port 8000

# In another terminal, test with PDF tires
curl -X POST "http://localhost:8000/recommend?use_pdf_tires=true" \
    -H "Content-Type: application/json" \
    -d @example_input.json \
    | python -m json.tool > api_output.json

# Check tire catalog status
curl http://localhost:8000/tire-catalog-status | python -m json.tool
```

## Expected Tire Selection Behavior

When tire selection works correctly, you should see:

1. **Matched tires** in the output with:
   - Tire size (e.g., "6.00-6")
   - Ply rating (e.g., "6")
   - Rated load capacity (lbs)
   - Rated inflation pressure (psi)
   - Load margin (percentage above required)
   - Score (0.0 to 1.0, higher is better)
   - Reasons why the tire was selected

2. **Safety factors** applied based on runway type:
   - Paved: 1.10× (10% margin)
   - Grass: 1.20× (20% margin)
   - Gravel: 1.25× (25% margin)

3. **Warnings** included (always):
   - Reminder that tire selection is for conceptual sizing only
   - Instructions to verify with manufacturers

4. **Application chart matching** (if aircraft name matches):
   - Bonus scoring for tires used on similar aircraft
   - Additional reasons explaining the match

## Troubleshooting

### Catalog Not Found Error

```
Error: Tire catalog not found. Run 'python -m gearrec import-tires' first.
```

**Solution:** Import the tire catalog from PDFs first (see Step 1 above).

### No Matched Tires

If no tires are matched, possible reasons:
- Required load is too high (no tires in catalog meet requirements)
- Pressure limit is too restrictive
- Check the output for specific error messages

### Import Errors

If PDF import fails:
- Ensure `pdfplumber` is installed: `pip install pdfplumber`
- Verify PDF files exist and are readable
- Check that PDF files are the correct format (Goodyear 2022 format)

## Continuous Testing

For development, you can run tests in watch mode:

```bash
# Install pytest-watch (optional)
pip install pytest-watch

# Run tests automatically on file changes
ptw tests/
```

