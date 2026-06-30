"""
pdf_extractor.py
Extracts text from SDS PDFs using PyMuPDF (fitz).
Parses into sections based on GHS SDS structure (Sections 1-16).
"""

import re
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF


# GHS SDS section headers we care about for Prop 65
PRIORITY_SECTIONS = {
    2: "composition",
    3: "hazards",
    8: "exposure_controls",
    11: "toxicological",
    15: "regulatory",
}

SECTION_PATTERN = re.compile(
    r"(?:^|\n)[\s=*#-]*(?:SECTION\s+)?(\d{1,2})[\s.:–\-]+([A-Z][^\n]{2,60})",
    re.IGNORECASE,
)


@dataclass
class SDSDocument:
    filename: str
    full_text: str
    sections: dict[int, str] = field(default_factory=dict)
    page_count: int = 0
    extraction_error: str | None = None

    @property
    def priority_text(self) -> str:
        """Concatenated text from Prop 65-relevant sections only."""
        parts = []
        for sec_num in PRIORITY_SECTIONS:
            if sec_num in self.sections:
                parts.append(self.sections[sec_num])
        return "\n".join(parts) if parts else self.full_text


def extract_sds(pdf_path: Path) -> SDSDocument:
    """
    Open a PDF and extract text. Returns an SDSDocument with:
      - full_text: all text concatenated
      - sections: dict of {section_number: text_content}
      - page_count
    """
    doc = SDSDocument(filename=pdf_path.name, full_text="")

    try:
        with fitz.open(str(pdf_path)) as pdf:
            doc.page_count = len(pdf)
            pages_text = []
            for page in pdf:
                pages_text.append(page.get_text())
            doc.full_text = "\n".join(pages_text)
    except Exception as e:
        doc.extraction_error = str(e)
        return doc

    doc.sections = _parse_sections(doc.full_text)
    return doc


# Leading keywords of the 16 standard GHS SDS section titles. A header match is
# only accepted if its title text contains one of these, which rejects page-footer
# dates ("8 December, 2025" -> bogus "Section 8") and digit-leading chemical names
# ("1-Chloro-..." -> bogus "Section 1") that otherwise masquerade as headers.
_GHS_TITLE_KEYWORDS = re.compile(
    r"identif|hazard|composition|ingredient|first|fire|accidental|release|"
    r"handling|storage|exposure|personal protection|physical|chemical propert|"
    r"stabilit|reactiv|toxicolog|ecolog|disposal|transport|regulator|other",
    re.IGNORECASE,
)


def _parse_sections(text: str) -> dict[int, str]:
    """
    Split SDS text into numbered sections.
    Returns {section_number: section_text}.

    Header matches are gated two ways so stray lines can't masquerade as section
    headers: (1) the title text must contain a real GHS section keyword, and
    (2) section numbers must increase monotonically (GHS sections 1..16 appear
    once, in order). Together these stop a date footer or a chemical name that
    begins with a digit from carving up a section.
    """
    sections = {}
    candidates = [m for m in SECTION_PATTERN.finditer(text)
                  if _GHS_TITLE_KEYWORDS.search(m.group(2))]

    accepted = []
    last_num = 0
    for m in candidates:
        sec_num = int(m.group(1))
        if 1 <= sec_num <= 16 and sec_num > last_num:
            accepted.append((sec_num, m.start()))
            last_num = sec_num

    for i, (sec_num, start) in enumerate(accepted):
        end = accepted[i + 1][1] if i + 1 < len(accepted) else len(text)
        sections[sec_num] = text[start:end].strip()

    return sections


def extract_cas_numbers(text: str) -> list[str]:
    """
    Extract CAS registry numbers from text.
    Format: XXXXXXX-XX-X (7 digits, dash, 2 digits, dash, 1 digit)
    """
    cas_pattern = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
    return list(set(cas_pattern.findall(text)))
