import fitz
import os
import re
import sys

def sanitize_filename(name):
    """Remove invalid filename characters."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()

def detect_chapter_entry(toc, chapter_number):
    """
    Search TOC for an entry representing the requested chapter number.
    Matches various patterns: 'Chapter X', 'CHAPTER X', '19.', 'Unit X', 'X. Title'.
    """
    patterns = [
        # Match "Chapter 19", "CHAPTER 19", "Unit 19", "Part 19"
        rf'\b(?:Chapter|CHAPTER|Unit|Part|Section)\s+0*{chapter_number}\b',
        # Match leading numbered outlines like "19 ", "19. ", "19.1 "
        rf'^\s*0*{chapter_number}(?:\.|\b)'
    ]
    
    for idx, (level, title, page) in enumerate(toc):
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return idx, level, title, page
                
    return None, None, None, None

def extract_chapter(pdf_path, chapter_number, out_dir="Chapters"):
    """
    Extracts a specific chapter from a PDF using hierarchical TOC boundary matching.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    total_pages = len(doc)

    if not toc:
        raise RuntimeError("PDF does not contain a Table of Contents (outline). Cannot split automatically.")

    # 1. Find the starting chapter entry
    chapter_index, start_level, chapter_title, start_page = detect_chapter_entry(toc, chapter_number)

    if start_page is None:
        # Fallback: list available level-1 or level-2 titles to help the user
        toc_samples = [title for _, title, _ in toc[:15]]
        raise RuntimeError(
            f"Chapter '{chapter_number}' not found in TOC.\n"
            f"First few TOC entries found: {toc_samples}"
        )

    print(f"Found starting outline: '{chapter_title}' (Level {start_level}) at page {start_page}")

    # 2. Determine end page by scanning for the next outline item at the same or higher hierarchy level
    # (E.g. if start level is 2, the chapter ends when we encounter another level 2 or level 1 heading)
    end_page = None
    for level, title, page in toc[chapter_index + 1:]:
        if level <= start_level:
            end_page = page - 1
            print(f"Detected boundary outline: '{title}' (Level {level}) at page {page}")
            break

    if end_page is None:
        end_page = total_pages

    # Guard bounds
    start_page = max(1, min(start_page, total_pages))
    end_page = max(start_page, min(end_page, total_pages))

    os.makedirs(out_dir, exist_ok=True)

    new_doc = fitz.open()
    new_doc.insert_pdf(
        doc,
        from_page=start_page - 1,
        to_page=end_page - 1
    )

    filename = sanitize_filename(chapter_title) + ".pdf"
    out_path = os.path.join(out_dir, filename)

    new_doc.save(out_path)
    new_doc.close()
    doc.close()

    print(f"Saved: {out_path} (Pages {start_page} to {end_page})")
    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python chapter_splitter.py <pdf_path> <chapter_number> [out_dir]")
        sys.exit(1)
        
    pdf = sys.argv[1]
    ch_num = int(sys.argv[2])
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "Chapters"
    
    try:
        extract_chapter(pdf, ch_num, output_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)