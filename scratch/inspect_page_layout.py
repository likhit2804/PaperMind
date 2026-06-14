import fitz
import sys

# Enforce UTF-8 output encoding for Windows consoles
sys.stdout.reconfigure(encoding='utf-8')

doc = fitz.open("entropy-25-00738-v2.pdf")

# Page numbers in PDF: Figure 1 and 2 are on page 3 (index 2)
for p_idx in [2]: # page 3 (index 2)
    print(f"\n=== PAGE {p_idx + 1} ===")
    page = doc[p_idx]
    
    print("\n--- TEXT BLOCKS ---")
    blocks = page.get_text("blocks")
    for b in blocks:
        bbox = b[:4]
        text = b[4].strip().replace('\n', ' ')
        print(f"Bbox: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}) | Text: {text[:100]}")
        
    print("\n--- IMAGES ---")
    images = page.get_image_info()
    for img in images:
        bbox = img["bbox"]
        print(f"Bbox: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")
        
    print("\n--- DRAWINGS ---")
    drawings = page.get_drawings()
    print(f"Total drawings: {len(drawings)}")
    for i, draw in enumerate(drawings[:10]):
        rect = draw["rect"]
        print(f"Drawing {i} Bbox: ({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f})")
    if len(drawings) > 10:
        print(f"... and {len(drawings) - 10} more drawings")
