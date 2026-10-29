import json
import os
import re
import sys
import fitz

try:
    from _bootstrap import *  # noqa: F403, F401
except ImportError:
    from pipeline.research_paper._bootstrap import *  # noqa: F403, F401

from pipeline.utils import (
    parse_json_robust,
    call_gemini_with_retry,
    get_gemini_model,
    get_pdf_title,
)
from pipeline.research_paper.tex_utils import extract_tex_notations, get_tex_title

# Standard structural English stopwords
STANDARD_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "those",
    "using",
    "used",
    "some",
    "such",
    "both",
    "either",
    "neither",
    "each",
    "every",
    "other",
    "another",
    "would",
    "could",
    "should",
    "shall",
    "will",
    "been",
    "have",
    "has",
    "had",
    "were",
    "was",
    "are",
    "they",
    "them",
    "their",
    "our",
    "your",
    "its",
    "her",
    "his",
    "she",
    "him",
    "who",
    "whom",
    "whose",
    "what",
    "which",
    "where",
    "when",
    "why",
    "how",
    "but",
    "not",
    "only",
    "about",
    "above",
    "below",
    "after",
    "before",
    "into",
    "onto",
    "upon",
}


def extract_lines_from_words(page):
    """
    Groups words on a page by their vertical coordinates to reconstruct visual lines.
    Detects table column boundaries to ignore side columns in multi-column layouts.
    """
    raw_words = page.get_text(
        "words"
    )  # list of: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
    if not raw_words:
        return []

    table_x_min = 0
    symbols_keywords = ["symbol", "symbols", "notation", "notations", "nomenclature"]
    for w in raw_words:
        x0, y0, x1, y1, text = w[:5]
        text_clean = text.lower().rstrip(":;,.")
        if text_clean in symbols_keywords:
            table_x_min = x0 - 15
            break

    words = []
    for w in raw_words:
        x0, y0, x1, y1, text = w[:5]
        if table_x_min > 0 and x1 < table_x_min:
            continue
        words.append(w)

    lines_dict = {}
    for w in words:
        x0, y0, x1, y1, text = w[:5]
        cy = (y0 + y1) / 2.0

        found = False
        for line_y in lines_dict:
            if abs(cy - line_y) < 5.0:
                lines_dict[line_y].append(w)
                found = True
                break
        if not found:
            lines_dict[cy] = [w]

    sorted_y = sorted(lines_dict.keys())

    reconstructed_lines = []
    for y in sorted_y:
        line_words = sorted(lines_dict[y], key=lambda w: w[0])
        line_text = " ".join(w[4] for w in line_words)
        reconstructed_lines.append(line_text)

    return reconstructed_lines


def is_valid_symbol(symbol):
    """
    Validates if a parsed string looks like a mathematical symbol/variable based on structural rules.
    """
    symbol_strip = symbol.strip()
    if not symbol_strip or len(symbol_strip) > 15:
        return False

    symbol_lower = symbol_strip.lower()

    # 1. Reject standard structural English stopwords
    if symbol_lower in STANDARD_STOPWORDS:
        return False

    # 2. Reject section numbers or bullet prefixes (e.g. "1.", "a.", "iv.")
    if re.match(r"^(?:[a-zA-Z]|\d+|[ivxIVX]+)\.$", symbol_strip):
        return False

    words = symbol_strip.split()
    if len(words) > 3:
        return False

    if all(w.lower() in STANDARD_STOPWORDS for w in words):
        return False

    has_math_char = any(
        c in symbol_strip
        for c in [
            "_",
            "^",
            "(",
            ")",
            "[",
            "]",
            "|",
            "⟩",
            "⟨",
            ">",
            "<",
            "=",
            "+",
            "−",
            "*",
            "/",
            "⊕",
            "⊗",
            "·",
            "′",
            "'",
            "’",
            "∈",
            "⊂",
            "⊃",
            "⊆",
            "⊇",
            "∩",
            "∪",
            "√",
            "∞",
            "≈",
            "≠",
            "≡",
            "∝",
            "\\",
        ]
    )
    has_greek = any(c in symbol_strip for c in "αβγδεζηθικλμνξοπρστυφχψωϵ")

    # A) Valid if contains structural math decorators or Greek letters (e.g. W_i, \alpha, f(x), S')
    if has_math_char or has_greek:
        return True

    # B) Valid if single-letter variable or short symbol (e.g. x, y, n, K, S)
    if len(symbol_strip) <= 3:
        return True

    # C) Valid if uppercase matrix / acronym operator (e.g. CNOT, MAJ, UMA, RES)
    if symbol_strip.isupper() and len(symbol_strip) <= 6:
        return True

    # D) Reject 4+ letter lowercase words with NO math decorators (e.g. "security", "protocol", "performance")
    if len(symbol_strip) >= 4 and symbol_strip.islower() and not has_math_char:
        return False

    if re.match(r"^[a-zA-Z]+[0-9a-zA-Z_]*$", symbol_strip):
        if len(symbol_strip) <= 8:
            return True

    return False


def split_symbol_description(line):
    """
    Heuristically splits a visual line into a symbol and its description.
    """
    line = re.sub(r"\s+", " ", line).strip()
    words = line.split()
    if len(words) < 2:
        return None

    split_idx = -1
    for i in range(1, len(words)):
        word = words[i]
        has_math = any(
            c in word
            for c in [
                "=",
                "+",
                "−",
                "*",
                "/",
                "<",
                ">",
                "≤",
                "≥",
                "∑",
                "⊕",
                "⊗",
                "|",
                "⟩",
                "⟨",
                "\\",
            ]
        )
        if word[0].isupper() and len(word) > 2 and not has_math:
            split_idx = i
            break

    if split_idx != -1:
        symbol = " ".join(words[:split_idx]).strip()
        description = " ".join(words[split_idx:]).strip()
        symbol = re.sub(r"^[•\-\*]\s*", "", symbol)
        symbol = symbol.rstrip(",.:; ")
        if is_valid_symbol(symbol) and len(description) > 3:
            return symbol, description

    if len(words[0]) <= 5 and is_valid_symbol(words[0]):
        symbol = words[0].rstrip(",.:; ")
        description = " ".join(words[1:])
        return symbol, description

    return None


def extract_notations_manually(page, page_num):
    """
    Offline fallback rule-based extractor.
    """
    lines = extract_lines_from_words(page)
    notations = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip or len(line_strip) < 5:
            continue
        if "table" in line_strip.lower() and (
            "description" in line_strip.lower() or "symbol" in line_strip.lower()
        ):
            continue

        res = split_symbol_description(line_strip)
        if res:
            symbol, description = res
            notations.append(
                {
                    "symbol": symbol,
                    "meaning": description,
                    "anchors": [
                        {
                            "section": "Description of Used Symbols Table",
                            "subsection": "",
                            "page": page_num,
                            "anchor_text": line_strip,
                        }
                    ],
                }
            )
    return notations


def extract_notations_via_ai(page_text, page_num, title, log_dir=None):
    """
    Extracts notations using Gemini API focusing purely on the table page.
    """
    # Setup log file
    log_file = None
    if log_dir is not None:
        log_file = os.path.join(log_dir, "notations_extraction.log")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"--- AI Extraction Attempt on Page {page_num} ---\n")
            lf.write(f"GEMINI_API_KEY present: {bool(os.environ.get('GEMINI_API_KEY'))}\n")

    model, _ = get_gemini_model()
    if not model:
        if log_file:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write("Error: GEMINI_API_KEY env var is not set.\n")
        return None

    if log_file:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"Using model: {os.environ.get('LLM_MODEL', 'gemini-3.7-flash')}\n")

    try:
        prompt = f"""You are an expert scientific peer reviewer and technical editor.
We have extracted the text of a page from a research paper titled "{title}". This page contains a "Description of Used Symbols" or "Nomenclature" table.

=== PAGE TEXT ===
{page_text}

=== INSTRUCTIONS ===
Extract the entire table of mathematical symbols/notations and their descriptions from this page.
- You MUST exhaustively extract EVERY single symbol listed in the table (e.g. S, n, t, p, f(x), a1, ..., at-1, xi, f(xi), Vi, T, si, S', IDi, k, ke, Xi, Xi1,e, Xi1,a, Xi2, X"i2, N, H(.), H_S, H(S'), e_th, P_detect, \\eta, \\eta_Gao, I, Y, C, QC, CC, M_X, etc.).
- Do not omit, group, or summarize any symbols. If they are in the table, list them as separate items.
- For each notation, extract:
  1. The exact symbol (e.g. "S", "f(x)", "\\eta_Gao", "Xi1,e").
  2. The exact description/meaning from the table.
- Do not include standard section headings, boilerplate text, or paragraphs surrounding the table as notations. Only extract rows of the nomenclature/symbols table.

Return your response strictly in JSON format matching this schema:
{{
  "notations": [
    {{
      "symbol": "S",
      "meaning": "Traffic-status secret, S ∈ Zp"
    }}
  ]
}}
"""
        response = call_gemini_with_retry(
            model, prompt, generation_config={"response_mime_type": "application/json"}
        )
        data = parse_json_robust(response.text)
        notations_list = data.get("notations", [])

        if log_file:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(
                    f"Successfully received response from Gemini. Extracted {len(notations_list)} items.\n"
                )

        # Add anchors
        notations = []
        for item in notations_list:
            symbol = item.get("symbol", "").strip()
            meaning = item.get("meaning", "").strip()
            if symbol and meaning:
                # Find an anchor sentence in page text
                anchor_text = ""
                for line in page_text.split("\n"):
                    if symbol in line and len(line.strip()) > 5:
                        anchor_text = line.strip()
                        break
                if not anchor_text:
                    anchor_text = f"{symbol}: {meaning}"

                notations.append(
                    {
                        "symbol": symbol,
                        "meaning": meaning,
                        "anchors": [
                            {
                                "section": "Description of Used Symbols Table",
                                "subsection": "",
                                "page": page_num,
                                "anchor_text": anchor_text,
                            }
                        ],
                    }
                )
        return notations
    except Exception as e:
        print(f"Warning: AI notations extraction failed: {e}")
        if log_file:
            import traceback

            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Exception raised: {e}\n")
                lf.write(traceback.format_exc() + "\n")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_notations_local.py <pdf_or_tex_path> <output_json_path>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_json_path = sys.argv[2]

    if not os.path.exists(input_path):
        print(f"Error: input file not found at {input_path}")
        sys.exit(1)

    # ------------------------------------------------------------------ .tex path
    if input_path.lower().endswith(".tex"):
        print(f"[.tex mode] Extracting notations locally from LaTeX source: {input_path}")
        title = get_tex_title(open(input_path, encoding="utf-8", errors="replace").read())
        notations = extract_tex_notations(input_path)
        print(f"Extracted {len(notations)} notations total from .tex source.")
        output_data = {"notations": notations}
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"Successfully wrote notations JSON output to: {output_json_path}")
        return

    # ------------------------------------------------------------------ PDF path
    pdf_path = input_path
    print(f"Starting notations extraction for {pdf_path}...")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    notations = []

    symbols_keywords = [
        "symbol",
        "notation",
        "nomenclature",
        "used symbols",
        "description of used symbols",
    ]
    desc_keywords = ["description", "meaning", "definition"]

    # Get paper title for AI prompt
    title = get_pdf_title(
        doc,
        fallback="A Single-Photon Threshold Quantum Secret Sharing Protocol for Secure Vehicular Communication",
    )

    force_manual = "--manual" in sys.argv or "--offline" in sys.argv
    if force_manual:
        print("Forcing local manual rule-based extraction (API bypassed).")

    for p_idx in range(total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        page_text = page.get_text("text")
        page_text_lower = page_text.lower()

        has_symbols = any(kw in page_text_lower for kw in symbols_keywords)
        has_desc = any(kw in page_text_lower for kw in desc_keywords)

        if not (has_symbols and has_desc):
            continue

        print(f"Detected potential symbols table on Page {page_num}...")

        # Try AI extraction first if key is present and manual mode is not forced
        ai_notations = None
        if not force_manual:
            ai_notations = extract_notations_via_ai(
                page_text, page_num, title, log_dir=os.path.dirname(output_json_path)
            )

        if ai_notations:
            print("Extracted notations via Gemini API table parsing.")
            notations.extend(ai_notations)
        else:
            if not force_manual:
                print(
                    "Gemini extraction failed or skipped. Falling back to local rule-based coordinate extraction."
                )
            else:
                print("Running local rule-based coordinate extraction.")
            manual_notations = extract_notations_manually(page, page_num)
            notations.extend(manual_notations)

    doc.close()

    print(f"Extracted {len(notations)} notations total.")
    output_data = {"notations": notations}
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully wrote notations JSON output to: {output_json_path}")


if __name__ == "__main__":
    main()
