
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

## Updating the Tool

The screener installs via pipx. After changes are merged, pull the latest:

    pipx install git+https://github.com/Ima-Hugestud/prop65-sds-checker --force

To install from a local working copy (e.g. testing a branch before merge):

    cd ~/prop65-sds-checker
    pipx install . --force

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
4. Three-pass matching:
   - Pass 1 — CAS number match against OEHHA list (high confidence)
   - Pass 2 — Chemical name match, word-boundary regex (medium confidence)
   - Pass 3 — Manufacturer-declared Prop 65 statement in the SDS (declared) —
     captures chemicals the manufacturer themselves flags under Proposition 65,
     even when the substance is **not** on the OEHHA list
5. Generates reports only for flagged products

---

## Confidence Levels

| Level | Method | Recommended Action |
|-------|--------|--------------------|
| High | CAS number match against OEHHA list | Assess warning obligation against NSRL/MADL thresholds |
| Medium | Chemical name match against OEHHA list | Verify manually against SDS before acting |
| Declared | Manufacturer names a specific chemical/CAS under Prop 65 (not an OEHHA list match) | Treat as the manufacturer's assertion; confirm against the current OEHHA list and product formulation |
| Review | Manufacturer makes a generic Prop 65 warning but names no chemical | Routed to a separate **Declarations to Review** bucket (not flagged); identify the substance by hand against the full SDS |

**On the Declared/Review tiers:** the trigger is an explicit Proposition 65 declaration by
the manufacturer (e.g. a "California Proposition 65" subsection in Section 15, or
a "known to the State of California to cause..." warning), **not** a generic
carcinogenicity statement. A manufacturer calling something carcinogenic (IARC/NTP/GHS
H350) is not the same as a Prop 65 declaration and does not trigger this pass.

When the declaration **names a chemical/CAS**, it is recorded as a `declared` finding
and the product is flagged. When the declaration is **generic** (a Prop 65 warning with
no chemical identified), the product is *not* flagged — it is routed to a separate
**Declarations to Review** bucket, because the manufacturer has asserted an obligation
but no specific substance is confirmed. This keeps unconfirmed statements from implying
a chemical match while still surfacing them for manual review.

Common "this product does not contain a Prop 65 chemical" boilerplate is suppressed
via negation detection. Where negation language sits near a declaration, the pass
errs toward suppression — a rare real positive with negation words nearby may be
missed, which is the intended tradeoff for a screening tool.

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
- Declared findings reflect the manufacturer's own statement and are only as
  reliable as the SDS; the parser may miss declarations with unusual phrasing,
  and suppresses declarations near "does not contain" boilerplate
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
