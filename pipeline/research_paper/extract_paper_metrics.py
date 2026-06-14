import sys
import os
import json
import re
import fitz

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

def extract_table_dynamically(page, caption_y1, gap_threshold=10.0):
    """
    Extracts a borderless table on the page following the caption y1 coordinate.
    Uses horizontal whitespace projection to align cells into columns.
    """
    words = page.get_text("words")
    if not words:
        return "", 0
        
    # 1. Group words into rows
    rows_map = []
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        cy = (y0 + y1) / 2.0
        
        placed = False
        for row in rows_map:
            if abs(cy - row["cy"]) < 4.0:
                row["words"].append(w)
                row["y0"] = min(row["y0"], y0)
                row["y1"] = max(row["y1"], y1)
                row["cy"] = (row["y0"] + row["y1"]) / 2.0
                placed = True
                break
        if not placed:
            rows_map.append({
                "y0": y0,
                "y1": y1,
                "cy": cy,
                "words": [w]
            })
            
    rows_map.sort(key=lambda r: r["cy"])
    
    # Filter rows that start after the caption bottom
    candidate_rows = [r for r in rows_map if r["cy"] > caption_y1]
    
    table_lines = []
    max_y = caption_y1
    
    # Scan rows downwards
    for idx, row in enumerate(candidate_rows):
        cy = row["cy"]
        
        # Stop if there is a large vertical gap between consecutive rows
        if table_lines:
            prev_row_cy = table_lines[-1][0]["cy"]
            y_diff = cy - prev_row_cy
            if y_diff > 25.0:
                break
                
        row_words = sorted(row["words"], key=lambda w: w[0])
        
        # Split row into cells based on horizontal distance
        cells = []
        current_cell = []
        for j, w in enumerate(row_words):
            if not current_cell:
                current_cell.append(w)
            else:
                prev_w = row_words[j - 1]
                gap = w[0] - prev_w[2]
                if gap > gap_threshold:
                    cells.append({
                        "x0": current_cell[0][0],
                        "x1": current_cell[-1][2],
                        "text": " ".join([word[4] for word in current_cell]),
                        "cy": cy
                    })
                    current_cell = [w]
                else:
                    current_cell.append(w)
        if current_cell:
            cells.append({
                "x0": current_cell[0][0],
                "x1": current_cell[-1][2],
                "text": " ".join([word[4] for word in current_cell]),
                "cy": cy
            })
            
        row_text = " ".join([w["text"] for w in cells]).strip()
        
        # Stop if we hit a section heading
        if re.match(r'^\s*\d+(\.\d+)*\s+[A-Z]', row_text):
            break
            
        # Stop if this row has only 1 column and is long (typical prose paragraph)
        if len(cells) == 1 and len(row_text.split()) > 10:
            break
            
        if len(cells) >= 1:
            table_lines.append(cells)
            max_y = max(max_y, cy + 10.0) # estimate row height
            
    if not table_lines:
        return "", max_y
        
    # Reconstruct columns
    x_starts = []
    for row in table_lines:
        for cell in row:
            x_starts.append(cell["x0"])
    x_starts.sort()
    
    # Cluster column starts (distance < 15.0)
    col_starts = []
    for x in x_starts:
        placed = False
        for col in col_starts:
            if abs(x - col["val"]) < 15.0:
                col["sum"] += x
                col["count"] += 1
                col["val"] = col["sum"] / col["count"]
                placed = True
                break
        if not placed:
            col_starts.append({"sum": x, "count": 1, "val": x})
            
    col_starts.sort(key=lambda c: c["val"])
    col_positions = [c["val"] for c in col_starts]
    num_cols = len(col_positions)
    
    markdown_rows = []
    for row in table_lines:
        row_cells = [""] * num_cols
        for cell in row:
            closest_idx = 0
            min_dist = float("inf")
            for idx, col_x in enumerate(col_positions):
                dist = abs(cell["x0"] - col_x)
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx
            row_cells[closest_idx] = cell["text"]
        markdown_rows.append(row_cells)
        
    lines = []
    # Merge headers if the first rows look like headers
    # Usually in layout-aligned borderless tables, headers might occupy the first 2 rows.
    # We will insert a markdown separator after the first header line (or second if multiple words match)
    has_inserted_sep = False
    
    for idx, r in enumerate(markdown_rows):
        lines.append("| " + " | ".join(r) + " |")
        
        # Insert header separator after first row containing typical header keys or after index 0
        if not has_inserted_sep and idx == 0:
            lines.append("| " + " | ".join(["---"] * num_cols) + " |")
            has_inserted_sep = True
            
    return "\n".join(lines), max_y

def parse_evaluation_content(pdf_path):
    """
    Locates sections related to simulation, results, evaluation, or complexity,
    extracts the text blocks naturally, filters out table boxes, and formats Markdown report.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    toc = doc.get_toc()
    
    # Keywords indicating evaluation / simulation sections
    eval_keywords = ["simulation", "result", "performance", "evaluation", "complexity", "comparison"]
    
    # 1. Map headings to pages
    eval_sections = []
    first_terminal_page = total_pages + 1
    terminal_keywords = ["references", "bibliography", "acknowledgments", "appendix"]
    
    # Map page indices for headings
    headings = []
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
                headings.append({
                    "title": title.strip(),
                    "page": page,
                    "level": level
                })
                
    # Fallback text heading scanner if TOC is empty
    if not headings:
        heading_pat = re.compile(r'^\s*(\d+(\.\d+)*\s+[A-Z][A-Za-z0-9\s,\-\:\(\)]+)', re.MULTILINE)
        for p_idx in range(total_pages):
            page_text = doc[p_idx].get_text("text")
            for m in heading_pat.finditer(page_text):
                title = m.group(1).strip()
                title_lower = title.lower()
                
                is_terminal = False
                for kw in terminal_keywords:
                    if kw in title_lower:
                        is_terminal = True
                        break
                if is_terminal:
                    first_terminal_page = min(first_terminal_page, p_idx + 1)
                    break
                    
                headings.append({
                    "title": title,
                    "page": p_idx + 1,
                    "level": len(title.split('.')) # estimate level
                })
                
    headings.sort(key=lambda h: h["page"])
    
    # Determine which headings are evaluation headings
    eval_headings = []
    for h in headings:
        title_lower = h["title"].lower()
        if any(kw in title_lower for kw in eval_keywords):
            eval_headings.append(h)
            
    # If no evaluation headings found, we scan page range 9 to 13 as a standard fallback
    page_ranges = []
    if eval_headings:
        for eh in eval_headings:
            start_page = eh["page"]
            # Find next heading page
            end_page = total_pages + 1
            for h in headings:
                if h["page"] > start_page:
                    end_page = h["page"]
                    break
            # Adjust to terminal page limit (exclude next heading page to prevent overlaps)
            end_page = min(end_page - 1, first_terminal_page - 1)
            if start_page <= end_page:
                page_ranges.append((start_page, end_page, eh["title"]))
    else:
        # Fallback: scan last 30% of pages preceding terminal pages
        start = max(1, int(first_terminal_page * 0.7))
        end = first_terminal_page - 1
        if start <= end:
            page_ranges.append((start, end, "Evaluation & Simulation Analysis"))
            
    print(f"Targeted page ranges for evaluation metrics extraction:")
    for start, end, label in page_ranges:
        print(f"  - Section '{label}' mapping to PDF Pages {start} to {end}")
        
    extracted_content = []
    
    # Track extracted table bounds on each page to avoid duplication/overlapping
    extracted_table_bounds = {} # page_num -> list of (y0, y1)
    
    for start, end, section_title in page_ranges:
        extracted_content.append(f"\n# {section_title}\n")
        
        for p_num in range(start, end + 1):
            page = doc[p_num - 1]
            page_height = page.rect.height
            margin_top = page_height * 0.08
            margin_bottom = page_height * 0.92
            
            # Fetch all text blocks and sort them naturally
            raw_blocks = page.get_text("blocks")
            sorted_blocks = sort_blocks_naturally(raw_blocks)
            
            # 1. Extract any tables dynamically first
            if p_num not in extracted_table_bounds:
                extracted_table_bounds[p_num] = []
                
            for block in sorted_blocks:
                rect = block[:4]
                text = block[4].strip()
                
                # Check for table caption
                if re.match(r'^Table\s+\d+\b', text, re.IGNORECASE):
                    # Check if already processed
                    if any(abs(rect[1] - y0) < 5.0 for y0, y1 in extracted_table_bounds[p_num]):
                        continue
                        
                    caption_y1 = rect[3]
                    print(f"Found Table Caption on Page {p_num} at y={rect[1]:.1f}: '{text[:50]}...'")
                    
                    table_md, table_max_y = extract_table_dynamically(page, caption_y1)
                    if table_md:
                        extracted_content.append(f"\n### {text}\n")
                        extracted_content.append(table_md + "\n")
                        extracted_table_bounds[p_num].append((rect[1], table_max_y))
                        
            # 2. Extract standard prose and equations
            for block in sorted_blocks:
                rect = block[:4]
                text = block[4].strip()
                
                # Filter running headers/footers
                if rect[1] < margin_top or rect[3] > margin_bottom:
                    continue
                    
                # Skip if block falls inside an extracted table boundary
                in_table = False
                for y0, y1 in extracted_table_bounds[p_num]:
                    if y0 - 10.0 <= rect[1] <= y1 + 10.0:
                        in_table = True
                        break
                if in_table:
                    continue
                    
                # Skip table captions as they are already printed above
                if re.match(r'^Table\s+\d+\b', text, re.IGNORECASE):
                    continue
                    
                # Format math display blocks (equations)
                # If a line contains equation labels e.g. (14)
                if re.search(r'\(\d+\)\s*$', text):
                    # Format equation cleanly
                    eq_lines = [l.strip() for l in text.split('\n')]
                    eq_label = eq_lines[-1]
                    eq_body = " ".join(eq_lines[:-1])
                    
                    # Clean brackets and operators
                    eq_body = eq_body.replace('\x0c', '|').replace('\f', '|')
                    
                    extracted_content.append(f"\n$$ {eq_body} \\quad {eq_label} $$\n")
                else:
                    # Clean standard paragraph text
                    clean_p = text.replace('\n', ' ')
                    clean_p = re.sub(r'\s+', ' ', clean_p).strip()
                    # Resolve common ligatures
                    clean_p = clean_p.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
                    
                    # Ensure section heading formatting
                    if re.match(r'^\d+(\.\d+)*\s+[A-Z]', clean_p):
                        extracted_content.append(f"\n## {clean_p}\n")
                    else:
                        extracted_content.append(clean_p + "\n")
                        
    doc.close()
    return "\n".join(extracted_content)

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_metrics.py <pdf_path> <output_md>")
        sys.exit(1)
        
    pdf = sys.argv[1]
    output_md_path = sys.argv[2]
    
    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)
        
    print(f"Starting offline evaluation metric and table extraction on: {pdf}...")
    metrics_report = parse_evaluation_content(pdf)
    
    print(f"Writing metrics report to: {output_md_path}...")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("# Quantitative Evaluation Metrics & Experimental Results\n")
        f.write("This document compiles the quantitative performance metrics, complexity analyses, and comparison tables extracted locally from the research publication.\n\n")
        f.write(metrics_report)
        
    print(f"\nSuccessfully completed metrics extraction! Output file: {output_md_path}")

if __name__ == "__main__":
    main()
