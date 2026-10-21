"""
pdf_utils.py — Shared PDF helpers for the research_paper pipeline.

Centralises three patterns that were copy-pasted across every script:
  • TERMINAL_KEYWORDS / TOC parsing   → parse_toc()
  • Section lookup by page number     → get_section_for_page()
  • Heuristic sentence splitting      → split_sentences()
"""
import re
from typing import Any

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
    return [s for s in re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text) if s]
