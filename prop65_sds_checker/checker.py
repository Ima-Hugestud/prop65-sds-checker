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
    r"free\s+of|absence\s+of|to\s+the\s+best\s+of\s+our\s+knowledge|"
    r"no\s+chemicals\s+at|require\s+reporting\s+under|"
    r"no\s+.{0,20}(chemical|substance)s?\s+(known|listed))",
    re.IGNORECASE,
)

# --- Named-declaration capture (manufacturer names a chemical, CAS or not) ------

# OEHHA-standardized safe-harbor warning. Names the chemical and the endpoint
# independent of whether a CAS number was disclosed.
_SAFE_HARBOR = re.compile(
    r"expose you to .*?including\s*\[?(?P<chem>[^\]\.;]+?)\]?,?\s+"
    r"which (?:is|are) known to the State of California to cause\s+"
    r"(?P<endpoint>cancer|birth defects|reproductive harm)",
    re.IGNORECASE | re.DOTALL,
)

# "Proposition 65 - <Category> (>0.0%):" list. The body names the chemical unless
# it is the "no chemicals / to the best of our knowledge" boilerplate.
_P65_CATEGORY = re.compile(
    r"Proposition\s*65\s*[-\u2013]\s*"
    r"(?P<cat>Carcinogen|Developmental|Female\s+Repro|Male\s+Repro)"
    r"[^():]*\([^)]*\)\s*:?\s*(?P<body>.*?)"
    r"(?=Proposition\s*65|SECTION\s+16|$)",
    re.IGNORECASE | re.DOTALL,
)

_P65_BOILERPLATE = re.compile(
    r"to the best of our knowledge|no chemicals|not applicable|none\b",
    re.IGNORECASE,
)

_ENDPOINT_CANON = {
    "cancer": "cancer",
    "carcinogen": "cancer",
    "birth defects": "developmental/reproductive toxicity",
    "reproductive harm": "developmental/reproductive toxicity",
    "developmental": "developmental/reproductive toxicity",
    "female repro": "developmental/reproductive toxicity",
    "male repro": "developmental/reproductive toxicity",
}


def _clean_chem(raw: str) -> str:
    """Tidy a captured chemical name; reject sentence-length over-captures."""
    name = re.sub(r"\s+", " ", raw).strip(" .,:;[]")
    if not (3 <= len(name) <= 90):
        return ""
    return name


def _extract_named_declarations(text: str):
    """
    Yield (chemical_name, canonical_endpoint, source_label, snippet) for each
    chemical the manufacturer NAMES in a Prop 65 declaration -- via the safe-harbor
    warning or a '(>0.0%)' category list. Independent of CAS disclosure.
    """
    out = []
    for m in _SAFE_HARBOR.finditer(text):
        chem = _clean_chem(m.group("chem"))
        if not chem:
            continue
        endpoint = _ENDPOINT_CANON.get(m.group("endpoint").lower().strip(),
                                       "manufacturer-declared")
        snippet = "..." + re.sub(r"\s+", " ", m.group(0)).strip() + "..."
        out.append((chem, endpoint,
                    "SDS Section 15 \u00b7 Prop 65 safe-harbor warning", snippet))

    for m in _P65_CATEGORY.finditer(text):
        body = m.group("body").strip()
        if not body or _P65_BOILERPLATE.search(body):
            continue
        cat = m.group("cat").strip()
        endpoint = _ENDPOINT_CANON.get(cat.lower(), "manufacturer-declared")
        label = f"SDS Section 15 \u00b7 Prop 65 {cat} list (>0.0%)"
        for piece in re.split(r";|,(?=\s*[A-Z])", body):
            chem = _clean_chem(piece)
            if chem and not _P65_BOILERPLATE.search(chem):
                snippet = f"...Proposition 65 - {cat} (>0.0%): {chem}..."
                out.append((chem, endpoint, label, snippet))
    return out


@dataclass
class ChemicalHit:
    chemical_name: str
    cas: str
    toxicity: str
    date_listed: str
    match_method: str
    matched_text: str
    confidence: str
    source_location: str = ""   # where in the SDS this was found (for the report)


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
                    source_location="SDS Section 3 (composition) \u00b7 CAS match",
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
                source_location="SDS Section 3 (composition) \u00b7 name match",
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
    Capture the manufacturer's own Prop 65 declaration from the SDS, even when the
    chemical is not on the OEHHA list. Three tiers, most specific first:

      1. NAMED declaration -> confidence "declared" (FLAGS the product). The
         manufacturer names a chemical via the safe-harbor warning or a "(>0.0%)"
         category list. Fires even when the CAS is withheld/proprietary.
      2. CAS inside a Prop 65 window not already captured -> "declared".
      3. GENERIC statement, no chemical named anywhere -> "review" (does NOT flag),
         emitted only if tiers 1-2 found nothing, so a real finding is never buried.

    "does not contain ..." boilerplate is suppressed via negation detection.
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

    seen_names: set = set()

    # Tier 1: named declarations (flag even with a withheld CAS)
    for chem, endpoint, source, snippet in _extract_named_declarations(text):
        key = chem.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        hits.append(ChemicalHit(
            chemical_name=chem,
            cas="",
            toxicity=endpoint,
            date_listed="n/a (manufacturer-declared)",
            match_method="manufacturer_declared",
            matched_text=snippet,
            confidence="declared",
            source_location=source,
        ))

    # Tier 2: a CAS sitting in a Prop 65 window that Pass 1/2 didn't already catch
    for m in PROP65_DECLARATION.finditer(text):
        start = max(0, m.start() - window_chars)
        end = min(len(text), m.end() + window_chars)
        window = text[start:end]
        if _NEGATION.search(window):
            continue
        endpoints = [label for label, pat in _ENDPOINT_PATTERNS.items()
                     if pat.search(window)]
        toxicity = ", ".join(endpoints) if endpoints \
            else "manufacturer-declared (endpoint unspecified)"
        for cas in extract_cas_numbers(window):
            if cas in seen_cas:
                continue
            seen_cas.add(cas)
            hits.append(ChemicalHit(
                chemical_name="(manufacturer-declared Prop 65 chemical)",
                cas=cas,
                toxicity=toxicity,
                date_listed="n/a (not on OEHHA list)",
                match_method="manufacturer_declared",
                matched_text="..." + window.strip() + "...",
                confidence="declared",
                source_location="SDS Section 15 \u00b7 CAS within Prop 65 declaration",
            ))

    # Tier 3: generic statement with no chemical named anywhere -> review only
    if not hits:
        for m in PROP65_DECLARATION.finditer(text):
            start = max(0, m.start() - window_chars)
            end = min(len(text), m.end() + window_chars)
            window = text[start:end]
            if _NEGATION.search(window):
                continue
            endpoints = [label for label, pat in _ENDPOINT_PATTERNS.items()
                         if pat.search(window)]
            toxicity = ", ".join(endpoints) if endpoints \
                else "manufacturer-declared (endpoint unspecified)"
            hits.append(ChemicalHit(
                chemical_name="(unspecified \u2014 manufacturer Prop 65 statement)",
                cas="",
                toxicity=toxicity,
                date_listed="n/a (not on OEHHA list)",
                match_method="manufacturer_declared_generic",
                matched_text="..." + window.strip() + "...",
                confidence="review",
                source_location="SDS Section 15 \u00b7 generic Prop 65 statement",
            ))
            break

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
