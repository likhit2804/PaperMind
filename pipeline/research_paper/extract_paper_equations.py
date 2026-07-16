import sys
import os
import json
import re
import fitz
import google.generativeai as genai
from dotenv import load_dotenv

# Enforce UTF-8 output encoding for Windows consoles
sys.stdout.reconfigure(encoding='utf-8')

# Ensure both workspace root and pipeline folder are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
pipeline_dir = os.path.dirname(current_dir)
workspace_root = os.path.dirname(pipeline_dir)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from pipeline.research_paper.extract_paper_concepts import clean_text
from pipeline.utils import parse_json_robust, call_gemini_with_retry, get_gemini_model, get_pdf_title
from pipeline.research_paper.pdf_utils import parse_toc, get_section_for_page
from pipeline.research_paper.tex_utils import extract_tex_equations, get_tex_title

# Load environment variables
load_dotenv(override=True)


def sort_blocks_naturally(blocks):
    """
    Sorts PyMuPDF blocks on a page to reconstruct natural reading order.
    Groups overlapping/aligned lines into rows and sorts each row horizontally.
    """
    sorted_by_top = sorted(blocks, key=lambda b: b[1])
    
    rows = []
    for b in sorted_by_top:
        y1, y2 = b[1], b[3]
        cy = (y1 + y2) / 2.0
        height = y2 - y1
        
        placed = False
        for row in rows:
            row_cy = row['cy']
            # If vertical distance between block center and row center is small
            max_dist = max(8.0, height * 0.7)
            if abs(cy - row_cy) < max_dist:
                row['blocks'].append(b)
                # Recalculate row center dynamically
                row['cy'] = sum((bl[1] + bl[3])/2.0 for bl in row['blocks']) / len(row['blocks'])
                placed = True
                break
        if not placed:
            rows.append({'cy': cy, 'blocks': [b]})
            
    for row in rows:
        row['blocks'].sort(key=lambda b: b[0])
        
    rows.sort(key=lambda r: r['cy'])
    
    flat_blocks = []
    for row in rows:
        flat_blocks.extend(row['blocks'])
    return flat_blocks

def block_has_label(text):
    """
    Checks if a block ends with an equation label like (1) or (14).
    """
    lines = text.split("\n")
    for line in lines:
        if re.search(r'\(\s*\d+\s*\)\s*$', line.strip()):
            return True
    return False

def is_plain_text_block(block_text):
    """
    Determines if a block is mostly plain text/prose or a caption, rather than math.
    Used to stop back-merging blocks into an equation.
    """
    text = block_text.strip()
    if not text:
        return True
        
    text_lower = text.lower()
    if text_lower.startswith("figure") or text_lower.startswith("algorithm") or text_lower.startswith("table"):
        return True
        
    has_math = any(c in text for c in ['=', '−', '∑', '|', '⟩', '⊕', '±', '×', '\\', '_', '^', '{', '}'])
    words = text.split()
    
    # Check for text words (alphabetical, length > 2)
    alpha_words = [w for w in words if w.isalpha() and len(w) > 2]
    if len(alpha_words) > 15:
        # If it has lots of standard english words, it's likely a sentence/paragraph
        return True
        
    return False

def clean_equation_text(text):
    """
    Replaces layout-specific characters (e.g. form feeds) with proper symbols,
    collapses excessive spaces, and removes running headers/footers.
    """
    # Replace PyMuPDF absolute value character glitches (form feeds mapping to vertical bars)
    text = text.replace('\x0c', '|')
    text = text.replace('\f', '|')
    text = text.replace('\x0b', '|')
    text = text.replace('\x12', '[')
    text = text.replace('\x13', ']')
    
    # Remove any other non-printable/control chars except newlines
    text = ''.join(c if (ord(c) >= 32 or c == '\n') else ' ' for c in text)
    
    # Collapse consecutive horizontal spaces
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Filter running headers/footers
    lines = [line.strip() for line in text.split('\n')]
    cleaned_lines = []
    for line in lines:
        if re.match(r'^entropy\s+\d+,\s+\d+,\s+\d+$', line.lower()):
            continue
        if re.match(r'^\d+\s+of\s+\d+$', line.lower()):
            continue
        cleaned_lines.append(line)
        
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def scan_equations_via_blocks(pdf_path):
    """
    Opens the PDF, maps page numbers to sections, and scans blocks.
    When an equation label is found, it merges it with preceding blocks on the same page.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    valid_toc, first_terminal_page = parse_toc(doc)
    
    candidates = []
    
    for p_idx in range(total_pages):
        page_num = p_idx + 1
        if page_num >= first_terminal_page:
            continue
            
        sec_label = get_section_for_page(page_num, valid_toc, total_pages, first_terminal_page)
        page = doc[p_idx]
        raw_blocks = page.get_text("blocks")
        
        # Sort blocks in natural reading order
        blocks = sort_blocks_naturally(raw_blocks)
        
        for b_idx, block in enumerate(blocks):
            text = block[4].strip()
            if not text:
                continue
                
            # Check if this block contains an equation label at the end of a line
            lines = text.split("\n")
            has_label = False
            label_val = None
            for line in lines:
                m = re.search(r'\(\s*(\d+)\s*\)\s*$', line.strip())
                if m:
                    has_label = True
                    label_val = f"Equation ({m.group(1)})"
                    break
                    
            if has_label:
                # Merge with preceding blocks on the same page to reconstruct full equation
                merged_blocks = [text]
                
                # Go backwards and collect preceding blocks of the equation
                for i in range(b_idx - 1, -1, -1):
                    prev_text = blocks[i][4].strip()
                    if not prev_text:
                        continue
                    
                    # Stop if we hit another equation label
                    if block_has_label(prev_text):
                        break
                        
                    # Stop if we hit a text paragraph/caption
                    if is_plain_text_block(prev_text):
                        break
                        
                    # Keep going, add block to the front
                    merged_blocks.insert(0, prev_text)
                    
                    # Safety check: do not merge more than 20 blocks total
                    if len(merged_blocks) >= 20:
                        break
                        
                full_raw_text = "\n".join(merged_blocks)
                
                # Clean the text using our cleanup rules (reconstruct kets, delimiters, absolute values)
                cleaned_raw_text = clean_equation_text(full_raw_text)
                
                # Check if the block has any mathematical operators to filter out false positive outline lists
                has_math_operators = any(c in cleaned_raw_text for c in ['=', '−', '∑', '|', '⟩', '⊕', '±', '×'])
                if not has_math_operators:
                    continue
                
                # Context is the neighboring blocks
                context_blocks = []
                start_ctx = max(0, b_idx - 5)
                end_ctx = min(len(blocks), b_idx + 3)
                for i in range(start_ctx, end_ctx):
                    # Exclude the blocks that are part of the equation itself
                    if blocks[i][4].strip() not in merged_blocks:
                        context_blocks.append(blocks[i][4].strip())
                context = " ".join([b.replace("\n", " ").strip() for b in context_blocks if b.strip()])
                context = clean_equation_text(context)
                
                candidates.append({
                    "label": label_val,
                    "raw_text": cleaned_raw_text,
                    "page": page_num,
                    "section": sec_label,
                    "context": context
                })
                
    doc.close()
    return candidates

def format_equations_via_ai(candidates, title):
    """
    Sends the list of candidate equations to Gemini in a single call to typeset them into LaTeX and write descriptions.
    """
    model, api_key = get_gemini_model("gemini-3.1-flash-lite")
    if not model:
        return {c["label"]: {"latex": f"$${c['raw_text']}$$", "description": "GEMINI_API_KEY not set."} for c in candidates}

    try:
        
        prompt_list = []
        for idx, c in enumerate(candidates):
            prompt_list.append(
                f"--- Item {idx+1} ---\n"
                f"Label: {c['label']}\n"
                f"Page: {c['page']} | Section: {c['section']}\n"
                f"Raw Split Text:\n{c['raw_text']}\n"
                f"Context: {c['context']}"
            )
            
        consolidated_input = "\n\n".join(prompt_list)
        
        prompt = f"""You are an expert mathematical typesetter and scientific annotator.
We are compiling a mathematical reference for a research paper titled "{title}".
We have extracted several raw equation blocks and their local context sentences.

{consolidated_input}

Instructions for each item:
1. **Clean & Convert to LaTeX**: Reconstruct the split raw text blocks into a single mathematically correct, standard LaTeX expression. Format it as a display math block enclosed in double dollar signs (e.g. $$\\mathbf{{M}} = \\sum ...$$). Correct any OCR glitches, brackets, subscripts, and symbols.
- Translate Dirac ket notations correctly (e.g., use `|\\psi\\rangle` or `\\left|\\psi\\right\\rangle` instead of random single vertical lines or letters like `E` or `\\rangle`).
- Translate absolute values correctly (e.g. if the expression represents an absolute value or edge magnitude, use `\\left| ... \\right|` or standard vertical bars surrounding the term). E.g., for equations 10, 11, 12, 13, the LHS has absolute value lines like E^L_{{YX}} = | ... |. Make sure the LHS and RHS have correct absolute values.
- Note that the character `E` in raw expressions like `2q-1E` or at the end of state descriptions is often a font glitch representing a right angle bracket `\\rangle`. E.g., `2q-1E` represents the state ket `|2^q-1\\rangle` or `|2^q-1\\rangle`. Make sure to reconstruct this correctly as a state ket, e.g. `|2^q-1\\rangle` (which has q qubits, i.e., 2^q - 1).
- Ensure proper spacing and LaTeX formatting.
2. **Contextual Explanation**: Analyze the context text provided to generate a clear, 1-sentence description explaining what this equation computes or defines (e.g. "Equation (5) defines the overall NEQR quantum state representing the coordinates and gray-scale values of all pixels.").
3. Maintain an academic, professional, and emoji-free tone.

Return your response strictly in JSON format matching this schema:
{{
  "equations": [
    {{
      "label": "Original label here (e.g., Equation (14))",
      "latex_equation": "$$ clean LaTeX equation block here $$",
      "explanation": "1-sentence contextual description here"
    }}
  ]
}}
"""
        response = call_gemini_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = parse_json_robust(response.text)
        eq_list = data.get("equations", [])
        
        result = {}
        for c in candidates:
            label = c["label"]
            found = False
            for res in eq_list:
                if res.get("label", "").strip().lower() == label.strip().lower():
                    result[label] = {
                        "latex": res.get("latex_equation", ""),
                        "description": res.get("explanation", "")
                    }
                    found = True
                    break
            if not found:
                result[label] = {"latex": f"$${c['raw_text']}$$", "description": "LaTeX generation failed."}
        return result
    except Exception as e:
        print(f"Warning: Failed to generate LaTeX for batch: {e}")
        return {c["label"]: {"latex": f"$${c['raw_text']}$$", "description": f"Error: {e}"} for c in candidates}

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_equations.py <pdf_or_tex_path> <output_md>")
        sys.exit(1)

    input_path     = sys.argv[1]
    output_md_path = sys.argv[2]

    if not os.path.exists(input_path):
        print(f"Error: input file not found at: {input_path}")
        sys.exit(1)

    # ------------------------------------------------------------------ .tex path
    if input_path.lower().endswith('.tex'):
        print(f"[.tex mode] Extracting equations locally from LaTeX source: {input_path}")
        with open(input_path, encoding='utf-8', errors='replace') as _f:
            _raw = _f.read()
        title      = get_tex_title(_raw)
        candidates = extract_tex_equations(input_path)
        print(f"Detected {len(candidates)} candidate equations from .tex source.")
        if not candidates:
            print("No equations detected.")
            sys.exit(0)
    else:
        # ---------------------------------------------------------------- PDF path
        pdf = input_path
        doc   = fitz.open(pdf)
        title = get_pdf_title(doc, fallback="Quantum Image Processing Algorithm Using Line Detection Mask Based on NEQR")
        doc.close()
        print("Scanning PDF layout locally for block equations...")
        candidates = scan_equations_via_blocks(pdf)
        print(f"Detected {len(candidates)} candidate equations locally.")
        if not candidates:
            print("No equations detected.")
            sys.exit(0)
        
    # 2. Query Gemini in a single batched API call
    print("Formatting equations to LaTeX and generating annotations via a single Gemini batch call...")
    formatted_results = format_equations_via_ai(candidates, title)
        
    # 3. Compile output file
    if output_md_path.endswith(".json"):
        print(f"Compiling final mathematical reference JSON at: {output_md_path}")
        json_output = []
        for idx, eq in enumerate(candidates):
            label = eq["label"]
            res = formatted_results.get(label, {"latex": f"$${eq['raw_text']}$$", "description": "Failed to format."})
            json_output.append({
                "label": label,
                "latex": res["latex"],
                "description": res["description"],
                "page": eq["page"],
                "section": eq["section"],
                "raw_text": eq["raw_text"]
            })
        
        with open(output_md_path, "w", encoding="utf-8") as f:
            json.dump({"equations": json_output}, f, indent=2)
            
        print(f"\nSuccessfully wrote mathematical reference JSON to: {output_md_path}")
    else:
        print(f"Compiling final mathematical reference Markdown at: {output_md_path}")
        markdown_output = []
        markdown_output.append(f"# Mathematical Reference: {title}\n")
        markdown_output.append("This document compiles and defines the core mathematical expressions, state representations, and circuit parameters presented in this research publication.\n")
        
        current_section = None
        for idx, eq in enumerate(candidates):
            label = eq["label"]
            res = formatted_results.get(label, {"latex": f"$${eq['raw_text']}$$", "description": "Failed to format."})
            
            # Section header boundary
            if eq["section"] != current_section:
                current_section = eq["section"]
                markdown_output.append(f"\n## {current_section}\n")
                
            markdown_output.append(f"### Equation Reference {idx+1}: {label}")
            markdown_output.append(f"*   **Location**: Page {eq['page']}")
            markdown_output.append(f"*   **Equation Context**: {res['description']}\n")
            
            # Ensure LaTeX formula formatting is clean
            latex_formula = res['latex'].strip()
            markdown_output.append(latex_formula)
            markdown_output.append(f"\n*   **Raw text block context**:\n```text\n{eq['raw_text']}\n```\n")
            markdown_output.append("---")
            
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(markdown_output))
            
        print(f"\nSuccessfully wrote mathematical reference to: {output_md_path}")

if __name__ == "__main__":
    main()
