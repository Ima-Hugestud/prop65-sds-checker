"""
checker.py
Cross-references extracted SDS text against the Prop 65 chemical list.
Uses CAS number matching (precise) and chemical name matching (fuzzy).
"""

import re
from dataclasses import dataclass, field

from pdf_extractor import SDSDocument, extract_cas_numbers
from prop65_list import build_lookup


# Manufacturer's own Prop 65 declaration (distinct from an OEHHA list match)
PROP65_DECLARATION = re.compile(
    r"(proposition\s*65|prop\.?\s*65|"
    r"known\s+to\s+the\s+state\s+of\s+california)",
    re.IGNORECASE,
)

# Toxicity endpoints the manufacturer may assert alongside the declaration
_ENDPOINT_PATTERNS = {
    "cancer": re.compile(r"cancer|carcinogen", re.IGNORECASE),
    "developmental/reproductive toxicity":
        re.compile(r"reproductive|developmental|birth\s+defect", re.IGNORECASE),
}

# If any of these sit near the declaration, treat it as "no Prop 65" boilerplate
_NEGATION = re.compile(
    r"(does\s+not\s+contain|do\s+not\s+contain|not\s+subject|not\s+applicable|"
    r"free\s+of|absence\s+of|no\s+.{0,20}(chemical|substance)s?\s+(known|listed))",
    re.IGNORECASE,
)


@dataclass
class ChemicalHit:
    chemical_name: str
    cas: str
    toxicity: str
    date_listed: str
    match_method: str
    matched_text: str
    confidence: str


@dataclass
class CheckResult:
    filename: str
    hits: list[ChemicalHit] = field(default_factory=list)
    cas_numbers_found: list[str] = field(default_factory=list)
    extraction_error: str | None = None

    # Substantive findings: OEHHA list matches, plus manufacturer declarations
    # that name a specific chemical/CAS. These flag the product.
    @property
    def substantive_hits(self) -> list[ChemicalHit]:
        return [h for h in self.hits
                if h.confidence in ("high", "medium", "declared")]

    # Generic manufacturer Prop 65 statements with no chemical identified.
    # These do NOT flag the product — they route to the review bucket.
    @property
    def review_hits(self) -> list[ChemicalHit]:
        return [h for h in self.hits if h.confidence == "review"]

    @property
    def flagged(self) -> bool:
        return len(self.substantive_hits) > 0

    @property
    def needs_review(self) -> bool:
        return len(self.review_hits) > 0

    @property
    def carcinogens(self) -> list[ChemicalHit]:
        return [h for h in self.substantive_hits if "cancer" in h.toxicity.lower()]

    @property
    def reproductive_hazards(self) -> list[ChemicalHit]:
        return [h for h in self.substantive_hits
                if "reproductive" in h.toxicity.lower()
                or "developmental" in h.toxicity.lower()]


def check_sds(doc: SDSDocument, prop65_chemicals: list[dict]) -> CheckResult:
    """
    Check a single SDS document against the Prop 65 list.
    Returns a CheckResult with all matches found.
    """
    result = CheckResult(filename=doc.filename)

    if doc.extraction_error:
        result.extraction_error = doc.extraction_error
        return result

    cas_lookup, name_lookup = build_lookup(prop65_chemicals)

    search_text = doc.priority_text
    search_text_lower = search_text.lower()

    seen_chemicals = set()

    # Pass 1: CAS number matching (high confidence)
    cas_numbers = extract_cas_numbers(search_text)
    result.cas_numbers_found = cas_numbers

    for cas in cas_numbers:
        if cas in cas_lookup:
            chem = cas_lookup[cas]
            key = chem["name_lower"]
            if key not in seen_chemicals:
                seen_chemicals.add(key)
                snippet = _get_snippet(search_text, cas)
                result.hits.append(ChemicalHit(
                    chemical_name=chem["name"],
                    cas=cas,
                    toxicity=chem["toxicity"],
                    date_listed=chem["date_listed"],
                    match_method="cas",
                    matched_text=snippet,
                    confidence="high",
                ))

    # Pass 2: Chemical name matching (medium confidence)
    for chem in prop65_chemicals:
        key = chem["name_lower"]
        if key in seen_chemicals:
            continue
        if len(key) < 5:
            continue
        import re
        if re.search(r'\\b' + re.escape(key) + r'\\b', search_text_lower):
            seen_chemicals.add(key)
            snippet = _get_snippet(search_text_lower, key)
            result.hits.append(ChemicalHit(
                chemical_name=chem["name"],
                cas=chem["cas"],
                toxicity=chem["toxicity"],
                date_listed=chem["date_listed"],
                match_method="name",
                matched_text=snippet,
                confidence="medium",
            ))

    # Pass 3: manufacturer-declared Prop 65 (may not be on the OEHHA list)
    seen_cas = {h.cas for h in result.hits if h.cas}
    result.hits.extend(_find_declared_prop65(doc, seen_cas))

    result.hits.sort(key=lambda h: (
        {"cas": 0, "name": 1, "manufacturer_declared": 2}.get(h.match_method, 3),
        h.chemical_name,
    ))
    return result


def _find_declared_prop65(doc: SDSDocument, seen_cas: set,
                          window_chars: int = 220) -> list[ChemicalHit]:
    """
    Capture the manufacturer's own Prop 65 declaration from the SDS, even when
    the chemical is not on the OEHHA list. Records named chemicals/CAS when
    present, otherwise a single product-level declaration. Suppresses the common
    "does not contain a Prop 65 chemical" boilerplate via negation detection.
    """
    hits: list[ChemicalHit] = []

    text = ""
    for sec in (15, 2):                       # regulatory first, then warning
        if sec in doc.sections:
            text += "\n" + doc.sections[sec]
    if not text.strip():
        text = doc.full_text

    # Collapse whitespace so wrapped lines don't defeat the phrase patterns
    text = re.sub(r"\s+", " ", text)

    emitted_generic = False
    for m in PROP65_DECLARATION.finditer(text):
        start = max(0, m.start() - window_chars)
        end = min(len(text), m.end() + window_chars)
        window = text[start:end]

        if _NEGATION.search(window):
            continue                          # "does not contain..." boilerplate

        endpoints = [label for label, pat in _ENDPOINT_PATTERNS.items()
                     if pat.search(window)]
        toxicity = ", ".join(endpoints) if endpoints \
            else "manufacturer-declared (endpoint unspecified)"
        snippet = "..." + window.strip() + "..."

        raw_cas = extract_cas_numbers(window)
        new_cas = [c for c in raw_cas if c not in seen_cas]
        if new_cas:
            for cas in new_cas:
                seen_cas.add(cas)
                hits.append(ChemicalHit(
                    chemical_name="(manufacturer-declared Prop 65 chemical)",
                    cas=cas,
                    toxicity=toxicity,
                    date_listed="n/a (not on OEHHA list)",
                    match_method="manufacturer_declared",
                    matched_text=snippet,
                    confidence="declared",
                ))
        elif raw_cas:
            # Every CAS in this declaration was already captured by Pass 1/2;
            # the declaration adds nothing new, so don't emit a generic hit.
            continue
        elif not emitted_generic:
            emitted_generic = True
            hits.append(ChemicalHit(
                chemical_name="(unspecified — manufacturer Prop 65 statement)",
                cas="",
                toxicity=toxicity,
                date_listed="n/a (not on OEHHA list)",
                match_method="manufacturer_declared_generic",
                matched_text=snippet,
                confidence="review",
            ))

    return hits


def _get_snippet(text: str, term: str, context_chars: int = 120) -> str:
    """Return a short snippet of text around the matched term."""
    idx = text.lower().find(term.lower())
    if idx == -1:
        return ""
    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(term) + context_chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    return f"...{snippet}..."
