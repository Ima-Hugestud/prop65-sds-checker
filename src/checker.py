"""
checker.py
Cross-references extracted SDS text against the Prop 65 chemical list.
Uses CAS number matching (precise) and chemical name matching (fuzzy).
"""

import re
from dataclasses import dataclass, field

from pdf_extractor import SDSDocument, extract_cas_numbers
from prop65_list import build_lookup


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

    @property
    def flagged(self) -> bool:
        return len(self.hits) > 0

    @property
    def carcinogens(self) -> list[ChemicalHit]:
        return [h for h in self.hits if "cancer" in h.toxicity.lower()]

    @property
    def reproductive_hazards(self) -> list[ChemicalHit]:
        return [h for h in self.hits if "reproductive" in h.toxicity.lower()
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

    result.hits.sort(key=lambda h: (0 if h.match_method == "cas" else 1, h.chemical_name))
    return result


def _get_snippet(text: str, term: str, context_chars: int = 120) -> str:
    """Return a short snippet of text around the matched term."""
    idx = text.lower().find(term.lower())
    if idx == -1:
        return ""
    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(term) + context_chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    return f"...{snippet}..."
