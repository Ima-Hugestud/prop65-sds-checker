# Prop 65 SDS Batch Checker

Batch processes Safety Data Sheet (SDS) PDFs against the official California Proposition 65 chemical list published by OEHHA. Generates individual reports only for products where Prop 65 substances are identified, plus a master summary across all processed PDFs.

---

## Requirements

- Python 3.10+
- PyMuPDF (`pymupdf`)
- The OEHHA Prop 65 CSV list (see [First Run](#first-run) below)

---

## Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/prop65-sds-checker.git
cd prop65-sds-checker

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## First Run

The OEHHA website blocks automated downloads. Before running, manually download the Prop 65 chemical list:

1. Go to: https://oehha.ca.gov/proposition-65/proposition-65-list
2. Download the CSV file
3. Place it at: `docs/p65chemicalslist.csv`

The tool caches the parsed list to `docs/prop65_cache.json` on first run. The cache is valid for 30 days.

---

## Usage

```bash
# Activate virtual environment first
source .venv/bin/activate

# Process all PDFs in input/ folder
python src/main.py

# Process a single PDF
python src/main.py --pdf input/product_sds.pdf

# Force refresh of cached Prop 65 list
python src/main.py --refresh-list

# Custom input/output directories
python src/main.py --input /path/to/pdfs --output /path/to/reports
```

---

## Output

# Install dependencies
pip install -r requirements.txt
```

---

## First Run

The OEHHA website blocks automated downloads. Before running, manually download the Prop 65 chemical list:

1. Go to: https://oehha.ca.gov/proposition-65/proposition-65-list
2. Download the CSV file
3. Place it at: `docs/p65chemicalslist.csv`

The tool caches the parsed list to `docs/prop65_cache.json` on first run. The cache is valid for 30 days.

---

## Usage

```bash
# Activate virtual environment first
source .venv/bin/activate

# Process all PDFs in input/ folder
python src/main.py

# Process a single PDF
python src/main.py --pdf input/product_sds.pdf

# Force refresh of cached Prop 65 list
python src/main.py --refresh-list

# Custom input/output directories
python src/main.py --input /path/to/pdfs --output /path/to/reports
```

---

## Output

output/
├── master_summary.md              # All products: flagged, clean, and errors
└── by_product/
└── product_name_analysis.md   # Only created when Prop 65 chemicals found

---

## How It Works

1. Loads the OEHHA Prop 65 list from local CSV (or cache)
2. Extracts text from each PDF using PyMuPDF
3. Parses GHS SDS sections — prioritizes Sections 2, 3, 8, 11, 15 to reduce noise
4. Two-pass matching:
   - Pass 1 — CAS number match (high confidence)
   - Pass 2 — Chemical name match, word-boundary regex (medium confidence)
5. Generates reports only for flagged products

---

## Confidence Levels

| Level | Method | Recommended Action |
|-------|--------|--------------------|
| High | CAS number match | Assess warning obligation against NSRL/MADL thresholds |
| Medium | Chemical name match | Verify manually against SDS before acting |

---

## Limitations

- Scanned/image PDFs are not supported — text extraction requires machine-readable PDFs
- Older MSDS formats with non-GHS section numbering may have section mapping issues
- Medium-confidence name matches require human verification
- Not a legal compliance determination — consult qualified EHS counsel
- Re-download the CSV and delete `docs/prop65_cache.json` periodically to refresh the list

---

## Disclaimer

This tool is intended for internal EHS screening purposes only. Results are not a substitute for professional legal or regulatory review. Always verify findings against the current OEHHA Prop 65 list and consult qualified EHS counsel before making compliance decisions.
