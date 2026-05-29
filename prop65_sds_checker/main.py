"""
main.py
Batch Prop 65 checker for SDS PDFs.

Usage:
    python src/main.py                        # process all PDFs in input/
    python src/main.py --input /path/to/pdfs  # custom input directory
    python src/main.py --pdf file.pdf         # single file
    python src/main.py --output /path/to/out  # custom output directory
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from prop65_list import load_prop65_list
from pdf_extractor import extract_sds
from checker import check_sds
from reporter import generate_reports

import os
PROJECT_ROOT = Path(os.environ.get("PROP65_DIR", Path(__file__).parent.parent))
DEFAULT_INPUT = PROJECT_ROOT / "input"
DEFAULT_OUTPUT = PROJECT_ROOT / "output"

def main():
    parser = argparse.ArgumentParser(description="Batch Prop 65 SDS checker")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Directory containing SDS PDFs (default: input/)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output directory for reports (default: output/)")
    parser.add_argument("--pdf", type=Path, default=None,
                        help="Process a single PDF file")
    args = parser.parse_args()

    prop65_chemicals = load_prop65_list()
    print(f"[main] Loaded {len(prop65_chemicals)} Prop 65 chemicals\n")

    if args.pdf:
        pdf_files = [args.pdf]
    else:
        if not args.input.exists():
            print(f"[main] ERROR: Input directory not found: {args.input}")
            print(f"       Create it and drop SDS PDFs in, then re-run.")
            sys.exit(1)
        pdf_files = sorted(args.input.glob("*.pdf"))
        if not pdf_files:
            print(f"[main] No PDFs found in {args.input}")
            print(f"       Drop SDS PDFs into the 'input/' folder and re-run.")
            sys.exit(0)

    print(f"[main] Found {len(pdf_files)} PDF(s) to process\n")

    results = []
    for pdf_path in pdf_files:
        print(f"  -> {pdf_path.name}")
        doc = extract_sds(pdf_path)

        if doc.extraction_error:
            print(f"     ERROR: {doc.extraction_error}")
        else:
            print(f"     Pages: {doc.page_count} | Sections parsed: {len(doc.sections)}")

        result = check_sds(doc, prop65_chemicals)

        if result.flagged:
            print(f"     {len(result.hits)} Prop 65 finding(s) - report will be generated")
        elif not result.extraction_error:
            print(f"     No Prop 65 substances identified")

        results.append(result)

    print(f"\n[main] Generating reports...\n")
    generate_reports(results, args.output)


if __name__ == "__main__":
    main()
