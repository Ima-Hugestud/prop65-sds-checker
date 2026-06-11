"""
reporter.py
Generates markdown reports from Prop 65 check results.
- master_summary.md: all products, flagged and clean
- by_product/{product}_analysis.md: only created when hits found
"""

from datetime import datetime
from pathlib import Path

from checker import CheckResult, ChemicalHit


# Why a product lands in the review bucket (shown in the report)
REVIEW_EXPLANATION = (
    "The SDS carries a Proposition 65 warning, but the manufacturer did not name "
    "the specific chemical or CAS number it applies to. The product is therefore "
    "not confirmed as containing a listed substance — yet the manufacturer has "
    "asserted a Prop 65 obligation. These need manual review against the full SDS "
    "and product formulation to identify the substance and determine the warning "
    "requirement. They are kept out of the Flagged bucket to avoid implying a "
    "confirmed chemical match."
)


def generate_reports(results: list[CheckResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_product_dir = output_dir / "by_product"
    by_product_dir.mkdir(exist_ok=True)

    summary_path = output_dir / "master_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(_render_master_summary(results))
    print(f"[reporter] Master summary -> {summary_path}")

    flagged = [r for r in results if r.flagged]
    for result in flagged:
        stem = Path(result.filename).stem
        report_path = by_product_dir / f"{stem}_analysis.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(_render_product_report(result))
        print(f"[reporter] Product report -> {report_path}")

    total = len(results)
    n_flagged = len(flagged)
    errors = [r for r in results if r.extraction_error]
    n_review = sum(1 for r in results if r.needs_review and not r.flagged)
    n_clean = total - n_flagged - n_review - len(errors)
    print(f"\n[reporter] Done. {total} products | {n_flagged} flagged | "
          f"{n_review} to review | {n_clean} clean | {len(errors)} errors")


def _render_master_summary(results: list[CheckResult]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    flagged = [r for r in results if r.flagged]
    review = [r for r in results if r.needs_review and not r.flagged]
    clean = [r for r in results
             if not r.flagged and not r.needs_review and not r.extraction_error]
    errors = [r for r in results if r.extraction_error]

    lines = [
        "# Prop 65 Batch Review — Master Summary",
        "",
        f"**Generated:** {now}  ",
        f"**Total PDFs processed:** {len(results)}  ",
        f"**Flagged (Prop 65 substances found):** {len(flagged)}  ",
        f"**Declarations to review (warning present, chemical not named):** {len(review)}  ",
        f"**Clean (no findings):** {len(clean)}  ",
        f"**Errors (extraction failed):** {len(errors)}  ",
        "",
        "> **Disclaimer:** This review is a screening tool, not a legal compliance determination.",
        "> CAS-based matches are high confidence. Name-based matches require human verification.",
        "> Always consult the current OEHHA Prop 65 list and qualified EHS counsel for compliance decisions.",
        "",
    ]

    if flagged:
        lines += [
            "---",
            "",
            "## Flagged Products",
            "",
            "| Product | Carcinogens | Repro Hazards | Total Hits | Confidence |",
            "|---------|-------------|---------------|------------|------------|",
        ]
        for r in sorted(flagged, key=lambda x: x.filename):
            high = sum(1 for h in r.hits if h.confidence == "high")
            med = sum(1 for h in r.hits if h.confidence == "medium")
            dec = sum(1 for h in r.hits if h.confidence == "declared")
            conf_str = f"{high} high / {med} medium"
            if dec:
                conf_str += f" / {dec} declared"
            lines.append(
                f"| [{r.filename}](by_product/{Path(r.filename).stem}_analysis.md) "
                f"| {len(r.carcinogens)} | {len(r.reproductive_hazards)} "
                f"| {len(r.substantive_hits)} | {conf_str} |"
            )
        lines.append("")

        for r in sorted(flagged, key=lambda x: x.filename):
            lines += _flagged_detail_block(r)

    if review:
        lines += [
            "---",
            "",
            "## Declarations to Review",
            "",
            f"> {REVIEW_EXPLANATION}",
            "",
        ]
        for r in sorted(review, key=lambda x: x.filename):
            endpoints = "; ".join(h.toxicity for h in r.review_hits)
            lines += [f"### {r.filename}", ""]
            lines.append(f"- **Declared endpoint(s):** {endpoints}")
            for h in r.review_hits:
                lines.append(f"- **Statement in SDS:**")
                lines.append(f"  > {h.matched_text}")
            lines.append("- [ ] Review full SDS Section 3 and Section 15 to identify the substance")
            lines.append("- [ ] Confirm against the current OEHHA list and product formulation")
            lines.append("")

    if clean:
        lines += [
            "---",
            "",
            "## Clean Products (No Prop 65 Findings)",
            "",
        ]
        for r in sorted(clean, key=lambda x: x.filename):
            lines.append(f"- {r.filename}")
        lines.append("")

    if errors:
        lines += [
            "---",
            "",
            "## Extraction Errors",
            "",
        ]
        for r in errors:
            lines.append(f"- **{r.filename}**: {r.extraction_error}")
        lines.append("")

    return "\n".join(lines)


def _flagged_detail_block(result: CheckResult) -> list[str]:
    lines = [f"### {result.filename}", ""]
    if result.carcinogens:
        lines.append(f"**Carcinogens ({len(result.carcinogens)}):**")
        for h in result.carcinogens:
            cas_str = f"CAS {h.cas}" if h.cas else "No CAS"
            lines.append(f"- {h.chemical_name} ({cas_str}) — {h.confidence} confidence [{h.match_method}]")
        lines.append("")
    if result.reproductive_hazards:
        lines.append(f"**Reproductive/Developmental Hazards ({len(result.reproductive_hazards)}):**")
        for h in result.reproductive_hazards:
            cas_str = f"CAS {h.cas}" if h.cas else "No CAS"
            lines.append(f"- {h.chemical_name} ({cas_str}) — {h.confidence} confidence [{h.match_method}]")
        lines.append("")
    return lines


def _render_product_report(result: CheckResult) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    stem = Path(result.filename).stem

    lines = [
        f"# Prop 65 Analysis — {stem}",
        "",
        f"**Source file:** {result.filename}  ",
        f"**Generated:** {now}  ",
        f"**Total Prop 65 findings:** {len(result.hits)}  ",
        f"**Carcinogens:** {len(result.carcinogens)}  ",
        f"**Reproductive/Developmental Hazards:** {len(result.reproductive_hazards)}  ",
        "",
        "> **Disclaimer:** Screening tool only. High-confidence matches are CAS-number based.",
        "> Medium-confidence matches are name-based and require human verification.",
        "> This is not a legal compliance determination.",
        "",
        "---",
        "",
    ]

    if result.cas_numbers_found:
        lines += ["## CAS Numbers Identified in Document", ""]
        for cas in sorted(result.cas_numbers_found):
            lines.append(f"- `{cas}`")
        lines.append("")

    high_hits = [h for h in result.hits if h.confidence == "high"]
    if high_hits:
        lines += [
            "## High Confidence Findings (CAS Match)",
            "",
            "| Chemical | CAS | Toxicity | Date Listed |",
            "|----------|-----|----------|-------------|",
        ]
        for h in high_hits:
            lines.append(f"| {h.chemical_name} | {h.cas} | {h.toxicity} | {h.date_listed} |")
        lines.append("")
        for h in high_hits:
            lines += [
                f"### {h.chemical_name}",
                f"- **CAS:** {h.cas}",
                f"- **Toxicity:** {h.toxicity}",
                f"- **Date Listed:** {h.date_listed}",
                f"- **Context in SDS:**",
                f"  > {h.matched_text}",
                "",
            ]

    med_hits = [h for h in result.hits if h.confidence == "medium"]
    if med_hits:
        lines += [
            "## Medium Confidence Findings (Name Match — Verify)",
            "",
            "| Chemical | CAS | Toxicity | Date Listed |",
            "|----------|-----|----------|-------------|",
        ]
        for h in med_hits:
            lines.append(f"| {h.chemical_name} | {h.cas or 'N/A'} | {h.toxicity} | {h.date_listed} |")
        lines.append("")
        for h in med_hits:
            lines += [
                f"### {h.chemical_name}",
                f"- **CAS:** {h.cas or 'Not available'}",
                f"- **Toxicity:** {h.toxicity}",
                f"- **Date Listed:** {h.date_listed}",
                f"- **Context in SDS:**",
                f"  > {h.matched_text}",
                "",
            ]

    dec_hits = [h for h in result.hits if h.confidence == "declared"]
    if dec_hits:
        lines += [
            "## Manufacturer-Declared Prop 65 (Not an OEHHA List Match)",
            "",
            "> These findings come from the manufacturer's own Proposition 65 "
            "statement in the SDS, **not** from a match against the OEHHA list. "
            "Treat as the manufacturer's assertion and verify independently.",
            "",
            "| Chemical | CAS | Declared Endpoint | Source |",
            "|----------|-----|-------------------|--------|",
        ]
        for h in dec_hits:
            lines.append(f"| {h.chemical_name} | {h.cas or 'N/A'} | {h.toxicity} | SDS (manufacturer-declared) |")
        lines.append("")
        for h in dec_hits:
            lines += [
                f"### {h.chemical_name}",
                f"- **CAS:** {h.cas or 'Not provided'}",
                f"- **Declared endpoint:** {h.toxicity}",
                f"- **Basis:** Manufacturer Prop 65 statement (not on OEHHA list)",
                f"- **Context in SDS:**",
                f"  > {h.matched_text}",
                "",
            ]

    rev_hits = [h for h in result.hits if h.confidence == "review"]
    if rev_hits:
        lines += [
            "## Declaration to Review (Chemical Not Named)",
            "",
            "> This product also carries a generic Prop 65 warning where the "
            "manufacturer did not identify the chemical. It does not confirm a "
            "listed substance — review the full SDS to identify what it refers to.",
            "",
        ]
        for h in rev_hits:
            lines += [
                f"- **Declared endpoint:** {h.toxicity}",
                f"- **Statement in SDS:**",
                f"  > {h.matched_text}",
                "",
            ]

    lines += [
        "---",
        "",
        "## Recommended Actions",
        "",
    ]
    if result.carcinogens:
        lines.append("- [ ] Verify carcinogen findings against full SDS Section 3 and Section 15")
        lines.append("- [ ] Assess exposure routes and quantities against NSRL thresholds")
        lines.append("- [ ] Determine if Prop 65 cancer warning is required")
    if result.reproductive_hazards:
        lines.append("- [ ] Verify reproductive hazard findings against full SDS Section 3 and Section 15")
        lines.append("- [ ] Assess exposure against MADL thresholds")
        lines.append("- [ ] Determine if Prop 65 reproductive toxicity warning is required")
    if dec_hits:
        lines.append("- [ ] Confirm the manufacturer's Prop 65 statement against the current OEHHA list and product formulation")
        lines.append("- [ ] Treat the declared chemical as in-scope for warning assessment even if absent from the OEHHA list")
    lines += [
        "- [ ] Cross-reference: https://oehha.ca.gov/proposition-65/proposition-65-list",
        "- [ ] Consult EHS counsel if warning obligation is unclear",
        "",
    ]

    return "\n".join(lines)
