import sys
import os
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

def get_figure_bbox(page, y_min, y_max, cap_bbox=None):
    """
    Finds the bounding box enclosing all drawing paths, image objects,
    and optionally the caption bounding box, in the vertical range [y_min, y_max] on the page.
    """
    drawings = page.get_drawings()
    image_info = page.get_image_info()
    
    x_min_all = page.rect.width
    y_min_all = page.rect.height
    x_max_all = 0
    y_max_all = 0
    found_any = False
    
    # Collect from drawings (vector graphics)
    for draw in drawings:
        rect = draw["rect"]
        # If it lies in the vertical range
        if rect.y1 > y_min and rect.y0 < y_max:
            # Avoid full-page border elements or running lines
            if rect.width > page.rect.width * 0.95 and rect.height < 5.0:
                continue # Skip horizontal running lines
            if rect.height > page.rect.height * 0.95 and rect.width < 5.0:
                continue # Skip vertical running lines
                
            x_min_all = min(x_min_all, rect.x0)
            y_min_all = min(y_min_all, rect.y0)
            x_max_all = max(x_max_all, rect.x1)
            y_max_all = max(y_max_all, rect.y1)
            found_any = True
            
    # Collect from images (raster graphics)
    for img in image_info:
        rect = fitz.Rect(img["bbox"])
        if rect.y1 > y_min and rect.y0 < y_max:
            x_min_all = min(x_min_all, rect.x0)
            y_min_all = min(y_min_all, rect.y0)
            x_max_all = max(x_max_all, rect.x1)
            y_max_all = max(y_max_all, rect.y1)
            found_any = True
            
    if not found_any:
        # Fallback to caption bounding box if available
        if cap_bbox is not None:
            x_min_all = cap_bbox[0]
            y_min_all = cap_bbox[1]
            x_max_all = cap_bbox[2]
            y_max_all = cap_bbox[3]
            found_any = True
        else:
            return None
            
    # Include caption bounding box in horizontal extent if provided
    if cap_bbox is not None:
        x_min_all = min(x_min_all, cap_bbox[0])
        x_max_all = max(x_max_all, cap_bbox[2])
        
    # Add a small padding margin
    pad = 5.0
    return fitz.Rect(
        max(0.0, x_min_all - pad),
        max(y_min, y_min_all - pad),
        min(page.rect.width, x_max_all + pad),
        y_max
    )

def is_body_text_block(block_text, bbox, page_width):
    """
    Determines if a block is standard body text or a heading (which we want to crop below),
    as opposed to drawing elements, math inline elements, or captions.
    """
    text = block_text.strip()
    if not text:
        return False
        
    text_lower = text.lower()
    if text_lower.startswith("figure") or text_lower.startswith("algorithm") or text_lower.startswith("table"):
        return False
        
    # Crop below any equations (which end with labels like (3) or (9))
    if re.search(r'\(\s*\d+\s*\)\s*$', text):
        return True
        
    # Standard body text/headings are aligned to the text column (x0 ≈ 166)
    is_aligned = 150.0 <= bbox[0] <= 180.0
    
    words = text.split()
    alpha_words = [w for w in words if w.isalpha() and len(w) > 2]
    
    # Body text has at least 5 alphabetical words OR is long
    is_text = len(alpha_words) >= 5 or len(text) > 40
    
    # Heading can be shorter but must be aligned and contain words or section numbers
    is_heading = is_aligned and (len(alpha_words) >= 3 or re.match(r'^\d+(\.\d+)*\b', text) is not None)
    
    if is_heading or is_text:
        return True
    return False

def get_body_text_bottom_above_caption(blocks, cap_bbox, y_min_start, page_width):
    """
    Finds the maximum bottom coordinate of all preceding body text/headings.
    Ensures we do not crop above standard page prose.
    """
    y_max_text = y_min_start
    for b in blocks:
        bbox = b[:4]
        text = b[4].strip()
        # If block is above the caption and below our y_min_start boundary
        if bbox[3] < cap_bbox[1] and bbox[1] >= y_min_start:
            if is_body_text_block(text, bbox, page_width):
                y_max_text = max(y_max_text, bbox[3])
    return y_max_text

def main():
    if len(sys.argv) < 4:
        print("Usage: python extract_paper_images.py <pdf_path> <output_dir> <output_md>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]
    output_md_path = sys.argv[3]
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at: {pdf_path}")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
    
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
    
    # First pass: gather all figures across all pages
    figures_list = []
    
    for p_idx in range(total_pages):
        page_num = p_idx + 1
        if page_num >= first_terminal_page:
            continue
            
        sec_label = get_section_for_page(page_num, valid_toc, total_pages, first_terminal_page)
        page = doc[p_idx]
        blocks = page.get_text("blocks")
        
        # Collect figure captions on this page
        page_captions = []
        for block in blocks:
            text = block[4].strip()
            if not text:
                continue
            m = re.search(r'^\s*(Figure\s+(\d+))\b', text, re.IGNORECASE)
            if m:
                # Save caption with num, text, and bbox rect
                page_captions.append({
                    "num": int(m.group(2)),
                    "label": m.group(1).title(),
                    "caption_text": text.replace('\n', ' ').strip(),
                    "bbox": block[:4],
                    "page_num": page_num,
                    "section": sec_label,
                    "page_obj": page
                })
                
        # Sort captions on page vertically by y0 (top coordinate)
        page_captions.sort(key=lambda c: c["bbox"][1])
        
        # Process each caption to extract figure bbox and render PNG
        for idx, cap in enumerate(page_captions):
            # Include the description/caption line inside the cropped image itself
            y_max = cap["bbox"][3] + 5.0 # Crop down to the bottom of the caption block
            
            # Vertical partitioning to isolate figure from preceding figures
            if idx == 0:
                y_min_start = 70.0 # Exclude page running header
            else:
                y_min_start = page_captions[idx - 1]["bbox"][3] + 10.0 # Crop below previous caption bottom
                
            # Filter out preceding body text paragraphs/headings
            y_min = get_body_text_bottom_above_caption(blocks, cap["bbox"], y_min_start, cap["page_obj"].rect.width)
                
            bbox = get_figure_bbox(cap["page_obj"], y_min, y_max, cap_bbox=cap["bbox"])
            
            # Fallback if no drawing paths or images are detected
            if bbox is None:
                print(f"Warning: No graphics detected above '{cap['label']}' on Page {page_num}. Applying fallback crop.")
                x0 = max(0.0, cap["bbox"][0] - 10.0)
                x1 = min(cap["page_obj"].rect.width, cap["bbox"][2] + 10.0)
                # If caption width is very small, expand to standard column width
                if (x1 - x0) < 300.0:
                    x0 = 150.0
                    x1 = 570.0
                bbox = fitz.Rect(
                    x0,
                    y_min,
                    x1,
                    y_max
                )
                
            # Verify coordinates are valid
            if bbox.width > 0 and bbox.height > 0:
                # Render region at 144 DPI (Matrix 2x zoom) for high resolution
                pix = cap["page_obj"].get_pixmap(clip=bbox, matrix=fitz.Matrix(2.0, 2.0))
                file_name = f"figure_{cap['num']}.png"
                file_path = os.path.join(output_dir, file_name)
                pix.save(file_path)
                
                cap["image_file"] = os.path.join(os.path.basename(output_dir), file_name).replace('\\', '/')
                figures_list.append(cap)
                print(f"Extracted {cap['label']} on Page {page_num} to {file_path} (bbox: {bbox.x0:.1f}, {bbox.y0:.1f}, {bbox.x1:.1f}, {bbox.y1:.1f})")
            else:
                print(f"Error: Invalid crop coordinates for {cap['label']} on Page {page_num}.")
                
    doc.close()
    
    # Sort final figures numerically
    figures_list.sort(key=lambda f: f["num"])
    
    # Generate Markdown Reference Sheet
    print(f"Compiling visual reference sheet at: {output_md_path}")
    
    markdown_output = []
    markdown_output.append("# Visual Figures Reference Sheet\n")
    markdown_output.append("This document compiles all figure representations, diagrams, and circuit designs extracted from the publication.\n")
    
    for cap in figures_list:
        markdown_output.append(f"## {cap['label']}")
        markdown_output.append(f"*   **Location**: Page {cap['page_num']} | Section: {cap['section']}")
        markdown_output.append(f"*   **Caption**: {cap['caption_text']}\n")
        
        # Embed the image using local path relative to the md file
        markdown_output.append(f"![{cap['label']}]({cap['image_file']})\n")
        markdown_output.append("---")
        
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_output))
        
    print(f"\nSuccessfully wrote visual reference sheet to: {output_md_path}")

if __name__ == "__main__":
    main()
