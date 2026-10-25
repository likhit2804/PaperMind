import json
import os
import re
import sys
import fitz

try:
    from _bootstrap import *  # noqa: F403, F401
except ImportError:
    from pipeline.research_paper._bootstrap import *  # noqa: F403, F401

from concurrent.futures import ThreadPoolExecutor
from pipeline.research_paper.extract_paper_concepts import (
    parse_pdf_into_sections,
    clean_text,
    extract_paper_metadata_via_ai,
)
from pipeline.utils import (
    parse_json_robust,
    call_gemini_with_retry,
    get_gemini_model,
    get_pdf_title,
)
from pipeline.research_paper.pdf_utils import split_sentences
from pipeline.research_paper.tex_utils import extract_tex_sections, get_tex_title


def extract_grounded_sentences(raw_text, canonical_seeds, max_sentences=8):
    """
    Splits text into sentences, scores them using heuristic boosts for canonical seeds,
    and returns the top-scoring sentences as verified evidence.
    """
    sentences = split_sentences(clean_text(raw_text))
    scored_sentences = []

    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 25:
            continue

        # Heuristic scoring
        sent_lower = sent.lower()
        score = 0.0

        # Boost if containing canonical seeds
        for seed in canonical_seeds:
            if re.search(r"\b" + re.escape(seed.lower()) + r"\b", sent_lower):
                score += 3.0

        # Boost for normal word length (usually readable sentences)
        words = [w for w in sent_lower.split() if w.isalnum()]
        if 8 <= len(words) <= 35:
            score += 1.0

        # Penalize sentences containing too many math symbols or layout remnants
        if sent_lower.count("=") > 1 or any(
            c in sent_lower for c in ["+", "−", "∑", "⊕", "⊗", "|", "⟩", "⟨"]
        ):
            score -= 2.0

        # Penalize boilerplate patterns
        boilerplate_indicators = [
            "doi",
            "copyright",
            "entropy",
            "license",
            "http",
            "table",
            "figure",
        ]
        if any(ind in sent_lower for ind in boilerplate_indicators):
            score -= 1.5

        scored_sentences.append((sent, score))

    # Sort by score descending and return top sentences
    scored_sentences.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored_sentences[:max_sentences]]


def summarize_section_via_ai(section_label, evidence_sentences, title, model):
    """
    Queries Gemini to summarize a specific section based strictly on pre-extracted evidence.
    """
    if not evidence_sentences:
        return {
            "summary": "This section contains structural equations, mathematical proofs, or supplementary layout data with no narrative text.",
            "key_points": [],
        }

    evidence_text = "\n".join([f"- {s}" for s in evidence_sentences])
    prompt = f"""You are an expert scientific editor.
We are compiling study notes for a research paper titled "{title}".
We need to summarize the section: "{section_label}".

Here is a list of key evidence sentences extracted directly from this section:
{evidence_text}

Instructions:
1. Summarize the content of this section based strictly and only on the provided evidence sentences.
2. Synthesize a concise 2-4 sentence narrative summary.
3. Extract 2-4 key points/claims as a list of bullet points.
4. Keep the tone academic, formal, and free of emojis. Do not speculate or introduce outer knowledge.

Return your response strictly in JSON format matching this schema:
{{
  "summary": "Your narrative summary.",
  "key_points": [
    "Key point or contribution 1",
    "Key point or contribution 2"
  ]
}}
"""
    try:
        response = call_gemini_with_retry(
            model, prompt, generation_config={"response_mime_type": "application/json"}
        )
        data = parse_json_robust(response.text)
        return {"summary": data.get("summary", ""), "key_points": data.get("key_points", [])}
    except Exception as e:
        print(f"Warning: Failed to summarize section '{section_label}': {e}")
        return {"summary": f"Failed to generate summary. (Error: {e})", "key_points": []}


def synthesize_executive_summary_via_ai(sections_summary_data, title, model):
    """
    Performs final executive synthesis of all section summaries to build overall summary components.
    """
    # Compile a clear markdown list of section summaries to feed into the prompt
    summaries_list = []
    for sec in sections_summary_data:
        points_str = "\n".join([f"  * {p}" for p in sec["key_points"]])
        summaries_list.append(
            f"### Section: {sec['label']}\nSummary: {sec['summary']}\nKey Points:\n{points_str}"
        )
    sections_summary_text = "\n\n".join(summaries_list)

    prompt = f"""You are an expert computer scientist and research editor.
We are summarizing the research paper titled "{title}".
We have compiled summaries and key points for each section of the paper below.

=== SECTION SUMMARIES ===
{sections_summary_text}

=== INSTRUCTIONS ===
Using ONLY the section summaries above, generate an overall executive synthesis for the paper.
Do NOT invent details. Ground all claims strictly on the provided section summaries.
Return your response strictly in JSON format matching this schema:
{{
  "executive": "A 1-paragraph overview summarizing the paper's core ideas, novel methods, and results.",
  "research_question": "What is the primary problem or research question this paper aims to solve?",
  "contributions": [
    "Primary contribution 1",
    "Primary contribution 2"
  ],
  "limitations": "What are the limitations, baselines comparison challenges, or future work mentioned in the text?",
  "tldr": "A 2-3 sentence TL;DR summary."
}}
"""
    try:
        response = call_gemini_with_retry(
            model, prompt, generation_config={"response_mime_type": "application/json"}
        )
        return parse_json_robust(response.text)
    except Exception as e:
        print(f"Error generating executive synthesis: {e}")
        return {
            "executive": f"Failed to generate executive synthesis. (Error: {e})",
            "research_question": "",
            "contributions": [],
            "limitations": "",
            "tldr": "",
        }


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_paper_summary.py <pdf_path> <output_json>")
        sys.exit(1)

    pdf = sys.argv[1]
    output_json_path = sys.argv[2]

    if not os.path.exists(pdf):
        print(f"Error: PDF not found at: {pdf}")
        sys.exit(1)

    model, api_key = get_gemini_model()
    if not model:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    print("Step 1: Partitioning outline sections...")
    if pdf.lower().endswith(".tex"):
        sections = extract_tex_sections(pdf)
    else:
        sections = parse_pdf_into_sections(pdf, "")

    # Consolidate sections if there are too many to respect API rate limits (RPM <= 15)
    if len(sections) > 6:
        print(f"  - Too many sections ({len(sections)}). Consolidating sections...")
        grouped_sections = []
        chunk_size = (len(sections) + 4) // 5  # Group into max 5-6 chunks
        for i in range(0, len(sections), chunk_size):
            chunk = sections[i : i + chunk_size]
            label = " & ".join([c["label"] for c in chunk])
            if len(label) > 60:
                first_lbl = chunk[0]["label"]
                last_lbl = chunk[-1]["label"]
                if first_lbl != last_lbl:
                    label = f"{first_lbl} – {last_lbl}"
                else:
                    label = f"{first_lbl} (and sub-sections)"
            raw_text = "\n\n".join([c["raw_text"] for c in chunk])
            grouped_sections.append({"label": label, "raw_text": raw_text})
        sections = grouped_sections
        print(f"  - Consolidated into {len(sections)} sections.")

    print("Step 2: Extracting canonical seeds and title metadata...")
    intro_snippet = "\n".join([sec["raw_text"] for sec in sections[:2]])

    if pdf.lower().endswith(".tex"):
        with open(pdf, encoding="utf-8", errors="replace") as _f:
            _raw = _f.read()
        metadata_title = get_tex_title(_raw)
    else:
        doc = fitz.open(pdf)
        metadata_title = get_pdf_title(doc)
        doc.close()

    title, canonical_seeds = extract_paper_metadata_via_ai(intro_snippet, metadata_title)
    print(f"  - Paper Title: '{title}'")
    print(f"  - Canonical Seeds Count: {len(canonical_seeds)}")

    # Step 3: Local grounded sentence mining and summarization per section (in parallel)
    print("Step 3: Generating section-level summaries in parallel...")
    import time

    def process_section(item):
        idx, sec = item
        # Spread out concurrent starts to avoid triggering the 2 requests per second rate limit
        time.sleep(idx * 2.5)
        label = sec["label"]
        evidence = extract_grounded_sentences(sec["raw_text"], canonical_seeds)
        sec_summary = summarize_section_via_ai(label, evidence, title, model)
        return {
            "label": label,
            "summary": sec_summary["summary"],
            "key_points": sec_summary["key_points"],
        }

    try:
        max_workers = int(
            os.environ.get("MAX_WORKERS")
            or os.environ.get("PIPELINE_WORKERS")
            or os.environ.get("NUM_WORKERS")
            or 3
        )
        max_workers = max(1, max_workers)
    except (ValueError, TypeError):
        max_workers = 3

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        sections_summary_data = list(executor.map(process_section, enumerate(sections)))

    # Step 4: Executive synthesis
    print("Step 4: Compiling overall paper executive synthesis...")
    exec_synthesis = synthesize_executive_summary_via_ai(sections_summary_data, title, model)

    # Assemble final output JSON
    output_data = {
        "paper_title": title,
        "executive": exec_synthesis.get("executive", ""),
        "research_question": exec_synthesis.get("research_question", ""),
        "contributions": exec_synthesis.get("contributions", []),
        "limitations": exec_synthesis.get("limitations", ""),
        "tldr": exec_synthesis.get("tldr", ""),
        "sections": sections_summary_data,
    }

    # Write to file
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nSuccessfully wrote structured paper summary to: {output_json_path}")


if __name__ == "__main__":
    main()
