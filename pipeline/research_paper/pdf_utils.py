"""
pdf_utils.py — Shared PDF helpers for the research_paper pipeline.

Centralises three patterns that were copy-pasted across every script:
  • TERMINAL_KEYWORDS / TOC parsing   → parse_toc()
  • Section lookup by page number     → get_section_for_page()
  • Heuristic sentence splitting      → split_sentences()
"""

import re
from typing import Any

import fitz

# Section headings that mark the end of the paper body
TERMINAL_KEYWORDS: list[str] = ["references", "bibliography", "acknowledgments", "appendix"]


def parse_toc(doc: Any) -> tuple[list[tuple[int, str, int]], int]:
    """
    Parse a PyMuPDF document's table of contents.

    Returns
    -------
    valid_toc : list of (level, heading, page) tuples
        Outline entries up to depth 2, stopping before any terminal section.
        Already sorted by page number.
    first_terminal_page : int
        1-based page where References/Appendix begins.
        Equals ``len(doc) + 1`` when no terminal section is found in the TOC.
    """
    total_pages: int = len(doc)
    toc = doc.get_toc()
    first_terminal_page: int = total_pages + 1
    valid_toc: list[tuple[int, str, int]] = []

    if toc:
        for level, title, page in toc:
            title_lower: str = str(title).lower().strip()
            if any(kw in title_lower for kw in TERMINAL_KEYWORDS):
                first_terminal_page = min(first_terminal_page, int(page))
                break
            if level <= 2:
                valid_toc.append((int(level), str(title).strip(), int(page)))

    # Fallback heuristic: If no terminal section was found in metadata TOC,
    # scan for standalone References / Bibliography heading lines.
    if first_terminal_page > total_pages:
        for p in range(min(10, total_pages - 1), total_pages):
            page_txt = doc[p].get_text("text")
            for line in page_txt.split("\n"):
                line_clean = line.strip().lower()
                if line_clean in TERMINAL_KEYWORDS or any(
                    line_clean == kw
                    or re.match(rf"^(?:\d+\.?\s+)?{kw}\b", line_clean)
                    for kw in TERMINAL_KEYWORDS
                ):
                    first_terminal_page = p + 1
                    break
            if first_terminal_page <= total_pages:
                break

    valid_toc.sort(key=lambda x: x[2])
    return valid_toc, first_terminal_page


def get_section_for_page(
    page_num: int,
    valid_toc: list[tuple[int, str, int]],
    total_pages: int,
    first_terminal_page: int,
) -> str:
    """
    Return the section heading that contains the given 1-based ``page_num``.
    Falls back to ``"Introduction"`` for pages before the first TOC entry and
    returns ``"References/Appendix"`` for pages at or after the terminal page.
    """
    if page_num >= first_terminal_page:
        return "References/Appendix"
    current_sec: str = "Introduction"
    for _level, heading, start_page in valid_toc:
        if page_num >= start_page:
            current_sec = heading
        else:
            break
    return current_sec


def split_sentences(text: str) -> list[str]:
    """
    Split *text* into sentences using a heuristic boundary regex that avoids
    splitting on common abbreviations such as ``Dr.``, ``e.g.``, or ``U.S.``.
    """
    return [s for s in re.split(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s", text) if s]


def clean_page_text(text: str, title_clean: str = "") -> str:
    """Strip common academic boilerplate, margins, citations, and math-only lines."""
    boilerplate_patterns = [
        r"entropy\s+\d{4}", r"doi\.org", r"distributed\s+under\s+the\s+terms",
        r"creativecommons\.org", r"citation:", r"academic\s+editors",
        r"received:", r"revised:", r"accepted:", r"published:", r"copyright:",
        r"college\s+of\s+science", r"university", r"correspondence:",
    ]
    cleaned_lines = []
    for line in text.split("\n"):
        line_strip = line.strip()
        if not line_strip or line_strip.isdigit():
            continue
        if any(re.search(pattern, line_strip, re.IGNORECASE) for pattern in boilerplate_patterns):
            continue
        if "@" in line_strip and any(domain in line_strip for domain in (".edu", ".com", ".org")):
            continue
        line_strip = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", line_strip)
        line_strip = re.sub(r"\|[^>⟩]+[>⟩]", " ", line_strip)
        line_strip = re.sub(r"[\$\\#_\^\{\}]", " ", line_strip)
        if "=" in line_strip and any(c in line_strip for c in ["+", "-", "*", "/", "⟩", "|", "cos", "sin"]):
            continue
        cleaned_lines.append(line_strip)
    return "\n".join(cleaned_lines)


def extract_clean_text_from_page(page: Any, title_clean: str = "") -> str:
    """Extract page text while skipping blocks rendered in monospace fonts."""
    blocks_text = []
    try:
        layout = page.get_text("dict")
        for block in layout.get("blocks", []):
            if block.get("type") != 0:
                continue
            block_lines = []
            for line in block.get("lines", []):
                line_spans = []
                is_code_line = False
                for span in line.get("spans", []):
                    font_name = span.get("font", "").lower()
                    if any(marker in font_name for marker in ("courier", "mono", "consolas", "lucida", "crd", "tele", "code", "terminal")):
                        is_code_line = True
                        break
                    line_spans.append(span.get("text", ""))
                if not is_code_line:
                    block_lines.append("".join(line_spans))
            blocks_text.append("\n".join(block_lines))
    except Exception:
        return clean_page_text(page.get_text("text"), title_clean)
    return clean_page_text("\n".join(blocks_text), title_clean)


def parse_pdf_into_sections(pdf_path: str, title_clean: str = "") -> list[dict[str, Any]]:
    """Chunk PDF text by TOC sections while excluding references and appendices."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    valid_toc, first_terminal_page = parse_toc(doc)
    first_terminal_page = min(first_terminal_page, total_pages + 1)
    if not valid_toc:
        for page in range(1, min(14, total_pages + 1)):
            valid_toc.append((1, f"Section Page {page}", page))

    sections = []
    for index, (_level, heading, start_page) in enumerate(valid_toc):
        next_page = valid_toc[index + 1][2] if index + 1 < len(valid_toc) else first_terminal_page
        end_page = min(total_pages, next_page - 1)
        pages_data = []
        raw_text = ""
        for page_index in range(start_page - 1, end_page):
            page_text = extract_clean_text_from_page(doc[page_index], title_clean)
            pages_data.append((page_index + 1, page_text))
            raw_text += page_text + "\n"
        sections.append({"label": heading, "raw_text": raw_text, "page_start": start_page, "pages_data": pages_data})
    doc.close()
    return sections
