import json
import os
import re
import sys
import fitz

try:
    from _bootstrap import *  # noqa: F403, F401
except ImportError:
    from pipeline.research_paper._bootstrap import *  # noqa: F403, F401

from pipeline.research_paper.extract_paper_concepts import parse_pdf_into_sections, clean_text
from pipeline.utils import parse_json_robust, call_gemini_with_retry, get_gemini_model
from pipeline.research_paper.pdf_utils import split_sentences
from pipeline.research_paper.tex_utils import extract_tex_sections

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL PRE-EXTRACTION HELPERS
# These run entirely offline before any Gemini call. They mirror the approach
# used in generate_paper_notes.py (get_term_contexts), but extract evidence
# at the section level for architectural topics rather than per glossary term.
# ─────────────────────────────────────────────────────────────────────────────

# Architectural topics we want to mine evidence for — generic enough to work
# across any paper. Evidence sentences are retrieved locally from the PDF text.
ARCH_TOPICS = [
    "proposed method",
    "novel",
    "algorithm",
    "circuit",
    "module",
    "complexity",
    "threshold",
    "shift",
    "copy",
    "adder",
    "absolute value",
    "classification",
    "representation",
    "mask",
    "step",
    "baseline",
    "comparison",
    "classical",
    "quantum",
    "simulation",
]

def get_sentences_for_topic(sections, topic, max_sentences=6):
    """
    Locally scans all sections page-by-page, finds sentences that mention
    `topic`, and returns a list of dicts:
        { "sentence": ..., "page": N, "section": "..." }

    This is entirely offline — no LLM call — so every returned sentence is
    a verbatim excerpt from the source PDF with its exact page/section provenance.
    """
    topic_lower = topic.lower().strip()
    hits = []

    for sec in sections:
        sec_label = sec["label"]
        for page_num, page_text in sec["pages_data"]:
            page_clean = clean_text(page_text)
            # Split on sentence boundaries (heuristic, same as paper_notes.py)
            sentences = split_sentences(page_clean)
            for idx, sent in enumerate(sentences):
                if re.search(r'\b' + re.escape(topic_lower) + r'\b', sent.lower()):
                    # Include one sentence of context before and after
                    before = sentences[idx - 1] if idx > 0 else ""
                    after  = sentences[idx + 1] if idx < len(sentences) - 1 else ""
                    full   = " ".join(filter(None, [before, sent, after])).strip()
                    hits.append({
                        "sentence": full,
                        "page": page_num,
                        "section": sec_label,
                    })
                    if len(hits) >= max_sentences:
                        return hits
    return hits


def get_key_term_occurrences(sections, key_terms):
    """
    For each key term, finds its first occurrence (page + section) so we can
    report a verified source map even if Gemini misplaces a term.
    Returns: { term: [(page, section), ...] }
    """
    term_sources = {}
    for term in key_terms:
        term_lower = term.lower().strip()
        found = []
        for sec in sections:
            for page_num, page_text in sec["pages_data"]:
                page_clean = clean_text(page_text).lower()
                if re.search(r'\b' + re.escape(term_lower) + r'\b', page_clean):
                    entry = (page_num, sec["label"])
                    if entry not in found:
                        found.append(entry)
        term_sources[term] = found
    return term_sources


def build_grounded_evidence_block(sections, key_terms):
    """
    Pre-extracts two evidence layers entirely offline:
    1. Architectural topic sentences — verbatim sentences mentioning each of
       ARCH_TOPICS, tagged with page and section.
    2. Key term source map — which pages/sections each key term appears on.

    Returns a formatted string that is inserted into the Gemini prompt as the
    ONLY factual source Gemini is allowed to synthesize from.
    """
    print("  [Pre-extraction] Mining architectural topic sentences from PDF...")
    topic_evidence = {}
    for topic in ARCH_TOPICS:
        hits = get_sentences_for_topic(sections, topic, max_sentences=6)
        if hits:
            topic_evidence[topic] = hits

    print("  [Pre-extraction] Building key term source map from PDF...")
    term_sources = get_key_term_occurrences(sections, key_terms)

    # ── Format the evidence block ──────────────────────────────────────────
    lines = []
    lines.append("=== VERIFIED EVIDENCE EXTRACTED LOCALLY FROM PDF ===")
    lines.append("")
    lines.append("--- SECTION A: Architectural Topic Sentences ---")
    lines.append("(Each sentence below is a verbatim excerpt from the source PDF.)")
    lines.append("")

    for topic, hits in topic_evidence.items():
        lines.append(f"[Topic: \"{topic}\"]")
        for h in hits:
            lines.append(f"  • (Page {h['page']}, Section '{h['section']}'): {h['sentence']}")
        lines.append("")

    lines.append("--- SECTION B: Key Term Source Map ---")
    lines.append("(Lists verified pages/sections where each key term appears.)")
    lines.append("")
    for term in sorted(term_sources.keys()):
        sources = term_sources[term]
        if sources:
            src_str = "; ".join([f"Page {p} ('{s}')" for p, s in sources])
        else:
            src_str = "NOT FOUND in paper text"
        lines.append(f"  • \"{term}\": {src_str}")

    lines.append("")
    lines.append("=== END OF VERIFIED EVIDENCE ===")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI SYNTHESIS — ONLY CALLED AFTER LOCAL EVIDENCE IS READY
# ─────────────────────────────────────────────────────────────────────────────

def generate_architecture_notes_via_ai(sections, title, key_terms):
    """
    Two-phase approach:
    1. Offline: pre-extract grounded evidence sentences from the PDF locally.
    2. Online: pass ONLY that evidence to Gemini and ask it to synthesize.

    Gemini never has to "search" the full text — it only arranges and rephrases
    sentences we already know are in the paper with their page citations.
    """
    model, api_key = get_gemini_model()
    if not model:
        return "Architecture notes not available (GEMINI_API_KEY not set)."

    try:

        # ── Phase 1: Build offline evidence block ─────────────────────────
        evidence_block = build_grounded_evidence_block(sections, key_terms)
        terms_str = ", ".join(key_terms)

        # ── Phase 2: Gemini synthesis from verified evidence only ──────────
        prompt = f"""You are an expert scientific editor and computer scientist.
We are compiling detailed technical architecture notes for a research paper titled "{title}".
The extracted key concepts/terms for this paper are: {terms_str}

IMPORTANT: You have been given a pre-verified evidence block below. This block contains:
  - Verbatim sentences extracted directly from each page of the source PDF, tagged with their exact page number and section name.
  - A key term source map showing which pages and sections each key term appears in.

You MUST synthesize your architecture notes exclusively from this evidence block.
Do NOT invent, assume, or recall any information not present in the evidence block below.

{evidence_block}

Using ONLY the evidence above, generate a comprehensive architectural write-up in clean,
premium GitHub-style markdown with the following sections:

1. **Executive Summary** — Concisely describe the paper's novel contribution, key advantages,
   and any performance claims. Every sentence must be traceable to a specific evidence entry.

2. **Proposed Core Architecture** — Explain the design principles and how the modules interact.
   For each design claim, cite the exact page and section from the evidence block.

3. **Novel Circuit/Structural Components** — Break down each custom module introduced by the
   authors (e.g. copy, double, shift, absolute value, threshold). For each module:
   - State what it does (from evidence sentences only).
   - Cite page and section: e.g., `(Page 4, Section 'Several Auxiliary Modules...')`.
   - If the evidence block does not describe a module's internal gate details, write:
     "Internal gate details not described in extracted evidence."

4. **Step-by-Step Processing Pipeline** — Walk through the algorithm steps in order.
   Each step must reference the page and section from Section B of the evidence block.

5. **Comparative Paradigm Matrix** — A markdown table comparing the proposed method vs
   baselines mentioned in the evidence sentences. Only include rows for methods explicitly
   named in the evidence. Do not add methods not found there.

Formatting rules:
- Bold each key term on its first appearance in a section.
- Every factual claim MUST end with a source citation, e.g., `(Page 5, Section '...')`.
- Do NOT speculate beyond what the evidence block contains.
- Keep the tone academic, clear, and emoji-free.

Return your response directly as markdown.
"""
        print("  [Gemini] Synthesizing architecture notes from pre-extracted evidence...")
        response = call_gemini_with_retry(model, prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating architecture notes: {e}")
        return f"Failed to generate architecture notes. (Error: {e})"


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print("Usage: python generate_architecture_notes.py <pdf_path> <concepts_json> <output_md_path>")
        sys.exit(1)

    pdf = sys.argv[1]
    concepts_json_path = sys.argv[2]
    output_md_path = sys.argv[3]

    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)

    if not os.path.exists(concepts_json_path):
        print(f"Error: Concepts JSON file not found at: {concepts_json_path}")
        sys.exit(1)

    print(f"Reading concept extractions from: {concepts_json_path}")
    with open(concepts_json_path, "r", encoding="utf-8") as f:
        concepts_data = json.load(f)

    title = concepts_data.get("paper_title", "Research Paper")
    unique_key_terms = concepts_data.get("unique_key_terms", [])

    if pdf.lower().endswith('.tex'):
        print("Parsing LaTeX sections...")
        sections = extract_tex_sections(pdf)
    else:
        print("Parsing PDF sections...")
        sections = parse_pdf_into_sections(pdf, "")

    print("Phase 1: Pre-extracting grounded evidence locally (no LLM)...")
    arch_notes_raw = generate_architecture_notes_via_ai(sections, title, unique_key_terms)

    print(f"Writing architecture notes to: {output_md_path}...")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(arch_notes_raw)

    print(f"\nSuccessfully wrote grounded architectural notes to: {output_md_path}")


if __name__ == "__main__":
    main()
