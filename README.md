# Prop 65 SDS Batch Checker

Batch processes Safety Data Sheet (SDS) PDFs against the official California Proposition 65 chemical list published by OEHHA. Generates individual reports only for products where Prop 65 substances are identified, plus a master summary across all processed PDFs.

---

## Quick Install (Mac/Linux)

```bash
pip3 install pipx
pipx install git+https://github.com/Ima-Hugestud/prop65-sds-checker
pipx ensurepath
mkdir -p ~/prop65-checker/input ~/prop65-checker/output ~/prop65-checker/docs
echo 'export PROP65_DIR=~/prop65-checker' >> ~/.bash_profile
source ~/.bash_profile
```

Then download the Prop 65 list (see First Run below) and run:
```bash
prop65-checker
```

---

## Quick Install (Windows)

Open Command Prompt as Administrator:

pip install pipx
pipx install git+https://github.com/Ima-Hugestud/prop65-sds-checker
pipx ensurepath

Restart terminal, then:

mkdir %USERPROFILE%\prop65-checker\input
mkdir %USERPROFILE%\prop65-checker\output
mkdir %USERPROFILE%\prop65-checker\docs
setx PROP65_DIR "%USERPROFILE%\prop65-checker"

Restart terminal again, then download the Prop 65 list (see First Run below) and run:

prop65-checker

---

## First Run

The OEHHA website blocks automated downloads. Before running, manually download the Prop 65 chemical list:

1. Go to: https://oehha.ca.gov/proposition-65/proposition-65-list
2. Download the CSV file
3. Place it at:
   - Mac/Linux: ~/prop65-checker/docs/p65chemicalslist.csv
   - Windows: %USERPROFILE%\prop65-checker\docs\p65chemicalslist.csv
4. Rename if needed — must be exactly p65chemicalslist.csv

The tool caches the parsed list for 30 days. Delete prop65_cache.json to force a fresh parse.

---

## Usage

```bash
prop65-checker                              # process all PDFs in input/
prop65-checker --pdf /path/to/file.pdf     # single file
prop65-checker --input /path/to/pdfs       # custom input directory
prop65-checker --output /path/to/reports   # custom output directory
```

> Always activate pipx PATH before running. If prop65-checker is not found, run pipx ensurepath and restart your terminal.

---

## Output

~/prop65-checker/
├── input/                         # Drop SDS PDFs here
├── output/
│   ├── master_summary.md          # All products: flagged, clean, errors
│   └── by_product/
│       └── product_analysis.md    # Only created when Prop 65 chemicals found
└── docs/
└── p65chemicalslist.csv       # OEHHA list — download manually

---

## How It Works

1. Loads the OEHHA Prop 65 list from local CSV (or 30-day cache)
2. Extracts text from each PDF using PyMuPDF
3. Parses GHS SDS sections — prioritizes Sections 2, 3, 8, 11, 15
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

## Updating the Prop 65 List

OEHHA updates the list periodically. To refresh:
1. Download the new CSV from https://oehha.ca.gov/proposition-65/proposition-65-list
2. Replace the existing p65chemicalslist.csv in your docs/ folder
3. Delete prop65_cache.json from the docs/ folder
4. Run prop65-checker

---

## Limitations

- Scanned/image PDFs are not supported — requires machine-readable text
- Medium-confidence name matches require human verification
- Not a legal compliance determination — consult qualified EHS counsel
- OEHHA list must be manually downloaded and updated

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| prop65-checker: command not found | Run pipx ensurepath and restart terminal |
| Prop 65 chemical list not found | Download CSV and place in docs/ folder |
| ModuleNotFoundError: fitz | Reinstall: pipx install git+https://... --force |
| No PDFs found | Drop SDS PDFs into the input/ folder |

---

## Disclaimer

This tool is intended for internal EHS screening purposes only. Results are not a substitute for professional legal or regulatory review. Always verify findings against the current OEHHA Prop 65 list and consult qualified EHS counsel before making compliance decisions.
