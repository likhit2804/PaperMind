import sys
import os
import json
import re
import subprocess
from knowledge_base.ingestion.chapter_splitter import extract_chapter

def main():
    pdf_path = "OS_main.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: Textbook {pdf_path} not found.")
        sys.exit(1)
        
    out_dir = "Chapters"
    concepts_dir = "extracted_concepts"
    os.makedirs(concepts_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    
    chapters = range(1, 21)
    
    print("Starting key term extraction for all 20 chapters of the textbook...")
    
    for ch_num in chapters:
        print(f"\n========================================")
        print(f"Processing Chapter {ch_num}...")
        print(f"========================================")
        
        # 1. Split chapter PDF if not already present
        ch_pdf_path = None
        for filename in os.listdir(out_dir):
            # Handle exact boundary cases like "Chapter 5 Deadlocks.pdf" or "Chapter 05 "
            if re.match(rf'^Chapter\s+0*{ch_num}\b', filename, re.IGNORECASE) and filename.endswith(".pdf"):
                ch_pdf_path = os.path.join(out_dir, filename)
                break
                
        if not ch_pdf_path:
            print(f"Splitting Chapter {ch_num} from {pdf_path}...")
            try:
                ch_pdf_path = extract_chapter(pdf_path, ch_num, out_dir)
            except Exception as e:
                print(f"Skipping Chapter {ch_num}: Split failed with error: {e}")
                continue
        else:
            print(f"Found existing split chapter PDF: {ch_pdf_path}")
            
        # 2. Execute concept extraction for this chapter
        output_json = os.path.join(concepts_dir, f"chapter_{ch_num}.json")
        print(f"Running key term extraction for Chapter {ch_num}...")
        
        try:
            cmd = ["python", "pipeline/extract_concepts.py", ch_pdf_path, str(ch_num), output_json]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            
            if result.returncode == 0:
                print(f"Success! Output written to {output_json}")
                with open(output_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    unique_count = len(data.get("unique_key_terms", []))
                    print(f"Extracted {unique_count} unique key terms for Chapter {ch_num}.")
            else:
                print(f"Error extracting Chapter {ch_num}: {result.stderr}")
                
        except Exception as e:
            print(f"Exception during extraction for Chapter {ch_num}: {e}")

    print("\nAll 20 chapters processed successfully!")

if __name__ == "__main__":
    main()
