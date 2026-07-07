import sys
import os
import json
import re
import fitz
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

# No pipeline.utils required for offline algorithms

# Load environment variables
load_dotenv(override=True)

def get_section_for_page(page_num, valid_toc, total_pages, first_terminal_page):
    """
    Determines which outline section a page number belongs to.
    """
    if page_num >= first_terminal_page:
        return "References/Appendix"
        
    current_sec = "Introduction"
    for level, heading, start_page in valid_toc:
        if page_num >= start_page:
            current_sec = heading
        else:
            break
            
    return current_sec

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
            max_dist = max(8.0, height * 0.7)
            if abs(cy - row_cy) < max_dist:
                row['blocks'].append(b)
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

def is_plain_text_block(block_text):
    """
    Determines if a block is mostly plain text/prose or a caption, rather than math/pseudocode.
    Used to stop forward-merging blocks into an algorithm.
    """
    text = block_text.strip()
    if not text:
        return True
        
    # If it starts with a step number (e.g. "1. Input", "10. Shift"), it's part of the algorithm
    if re.match(r'^\s*\d+\.\s*', text):
        return False
        
    text_lower = text.lower()
    if text_lower.startswith("figure") or text_lower.startswith("algorithm") or text_lower.startswith("table"):
        return True
        
    # Check if it has section numbering
    if re.match(r'^\s*\d+(\.\d+)+\b', text):
        return True
        
    has_math = any(c in text for c in ['=', '−', '∑', '|', '⟩', '⊕', '±', '×', '\\', '_', '^', '{', '}'])
    words = text.split()
    
    # Check for text words (alphabetical, length > 2)
    alpha_words = [w for w in words if w.isalpha() and len(w) > 2]
    if len(alpha_words) > 15:
        return True
        
    return False

def clean_algorithm_text(text):
    """
    Replaces layout-specific characters (e.g. form feeds) with proper symbols,
    collapses excessive spaces, and removes running headers/footers.
    """
    # Replace PyMuPDF character glitches
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

def scan_algorithms_via_blocks(pdf_path):
    """
    Opens the PDF, maps pages to sections, and scans blocks for algorithm listings.
    Once an algorithm label block is found, it merges forward until a section title or body text is encountered.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    toc = doc.get_toc()
    
    # Identify terminal page
    first_terminal_page = total_pages + 1
    terminal_keywords = ["references", "bibliography", "acknowledgments", "appendix"]
    valid_toc = []
    
    if toc:
        for level, title, page in toc:
            title_lower = title.lower().strip()
            is_terminal = False
            for kw in terminal_keywords:
                if kw in title_lower:
                    is_terminal = True
                    break
            if is_terminal:
                first_terminal_page = min(first_terminal_page, page)
                break
            if level <= 2:
                valid_toc.append((level, title.strip(), page))
                
    valid_toc.sort(key=lambda x: x[2])
    
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
                
            # Check if this block defines an algorithm listing (starts with Algorithm X)
            m = re.search(r'^\s*(Algorithm\s+\d+)\b', text, re.IGNORECASE)
            if m:
                label_val = m.group(1).title()
                
                # Merge forward to capture the full algorithm body
                merged_blocks = [text]
                for i in range(b_idx + 1, len(blocks)):
                    next_text = blocks[i][4].strip()
                    if not next_text:
                        continue
                        
                    # Stop if we hit another algorithm
                    if re.match(r'^\s*(Algorithm|Procedure|Pseudocode)\s+\d+', next_text, re.IGNORECASE):
                        break
                        
                    # Stop if we hit a text paragraph or figure caption
                    if is_plain_text_block(next_text):
                        break
                        
                    merged_blocks.append(next_text)
                    
                    # Safety check: limit algorithm body size
                    if len(merged_blocks) >= 150:
                        break
                        
                full_raw_text = "\n".join(merged_blocks)
                cleaned_raw_text = clean_algorithm_text(full_raw_text)
                
                candidates.append({
                    "label": label_val,
                    "raw_text": cleaned_raw_text,
                    "page": page_num,
                    "section": sec_label
                })
                
    doc.close()
    return candidates

def format_algorithms_locally(candidates):
    """
    Cleans raw algorithm text, groups split text lines by step prefixes (e.g. 1., 2.),
    and formats them as a clean pseudocode block locally.
    """
    result = {}
    for c in candidates:
        raw_text = c["raw_text"]
        
        # Normalize layout characters
        text_norm = raw_text.replace('\x0c', '|').replace('\f', '|').replace('\x0b', '|')
        text_norm = text_norm.replace('\x12', '[').replace('\x13', ']')
        
        # Split into lines
        lines = [line.strip() for line in text_norm.split('\n') if line.strip()]
        
        # Group by step numbers
        steps = []
        current_step = []
        title_words = []
        
        for line in lines:
            if re.match(r'^\d+\.\s*', line):
                if current_step:
                    steps.append(" ".join(current_step))
                current_step = [line]
            else:
                if current_step:
                    current_step.append(line)
                else:
                    title_words.append(line)
                    
        if current_step:
            steps.append(" ".join(current_step))
            
        title = " ".join(title_words).strip()
        title_clean = re.sub(r'^(Algorithm|Procedure|Pseudocode)\s+\d+\b\s*', '', title, flags=re.IGNORECASE)
        title_clean = re.sub(r'^[:\-\s]+', '', title_clean).strip()
        if not title_clean:
            title_clean = "Extracted Algorithm"
            
        formatted_steps = []
        for step in steps:
            step_clean = re.sub(r'\s+', ' ', step).strip()
            # Normalize spacing around absolute value and ket brackets
            step_clean = step_clean.replace(' | ', '|').replace(' |', '|').replace('| ', '|')
            formatted_steps.append(step_clean)
            
        inputs = []
        outputs = []
        description = f"Local offline extraction of {c['label']}."
        
        for step in formatted_steps:
            # Extract inputs and outputs dynamically if defined in steps
            match_in = re.match(r'^\d+\.\s*Input\s*[:\-\s]+(.*)$', step, re.IGNORECASE)
            if match_in:
                inputs.append(match_in.group(1).strip())
            match_out = re.match(r'^\d+\.\s*Output\s*[:\-\s]+(.*)$', step, re.IGNORECASE)
            if match_out:
                outputs.append(match_out.group(1).strip())
                
        pseudocode = "```text\n" + "\n".join(formatted_steps) + "\n```"
        
        result[c["label"]] = {
            "title": title_clean,
            "inputs": inputs,
            "outputs": outputs,
            "code": pseudocode,
            "description": description
        }
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_algorithms.py <pdf_path> <output_md>")
        sys.exit(1)
        
    pdf = sys.argv[1]
    output_md_path = sys.argv[2]
    
    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)
        
    doc = fitz.open(pdf)
    title = doc.metadata.get("title") if hasattr(doc, 'metadata') else "Research Paper"
    doc.close()
    if not title or len(title.strip()) < 3:
         title = "Quantum Image Processing Algorithm Using Line Detection Mask Based on NEQR"
         
    print("Scanning PDF layout locally for algorithm listings...")
    candidates = scan_algorithms_via_blocks(pdf)
    print(f"Detected {len(candidates)} candidate algorithms locally.")
    
    if not candidates:
        print("No algorithms detected.")
        sys.exit(0)
        
    print("Formatting pseudocode and generating annotations locally...")
    formatted_results = format_algorithms_locally(candidates)
        
    print(f"Compiling final algorithmic reference at: {output_md_path}")
    
    markdown_output = []
    markdown_output.append(f"# Algorithmic Reference: {title}\n")
    markdown_output.append("This document compiles and defines the algorithmic pseudo-code listings presented in this research publication.\n")
    
    for idx, alg in enumerate(candidates):
        label = alg["label"]
        res = formatted_results.get(label, {
            "title": "Algorithm",
            "inputs": [],
            "outputs": [],
            "code": f"```text\n{alg['raw_text']}\n```",
            "description": "Failed to format."
        })
        
        markdown_output.append(f"\n## {label}: {res['title']}")
        markdown_output.append(f"*   **Location**: Page {alg['page']} | Section: {alg['section']}")
        markdown_output.append(f"*   **Goal**: {res['description']}")
        
        if res['inputs']:
            markdown_output.append(f"*   **Inputs**: " + ", ".join([f"`{i}`" for i in res['inputs']]))
        if res['outputs']:
            markdown_output.append(f"*   **Outputs**: " + ", ".join([f"`{o}`" for o in res['outputs']]))
            
        markdown_output.append("\n" + res['code'].strip() + "\n")
        markdown_output.append(f"\n*   **Raw text block context**:\n```text\n{alg['raw_text']}\n```\n")
        markdown_output.append("---")
        
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_output))
        
    print(f"\nSuccessfully wrote algorithmic reference to: {output_md_path}")

if __name__ == "__main__":
    main()
