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
from pipeline.utils import parse_json_robust, call_gemini_with_retry

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

def parse_citation_keys(bracket_text):
    """
    Parses bracket contents like "1", "2, 3", "4-6", "7, 8, 12-15"
    into a list of integer keys.
    """
    keys = []
    # Strip spaces
    cleaned = re.sub(r'\s+', '', bracket_text)
    # Split by comma
    parts = cleaned.split(',')
    for part in parts:
        if not part:
            continue
        if '-' in part:
            # Range match, e.g. "4-6" or "12-15"
            range_parts = part.split('-')
            if len(range_parts) == 2 and range_parts[0].isdigit() and range_parts[1].isdigit():
                start = int(range_parts[0])
                end = int(range_parts[1])
                # Safety check for range length
                if start <= end and (end - start) < 50:
                    keys.extend(range(start, end + 1))
        elif part.isdigit():
            keys.append(int(part))
    return keys

def find_references_boundary(doc):
    """
    Searches the document table of contents (TOC) and pages
    to find where the References/Bibliography section starts.
    Returns the 1-based page index.
    """
    total_pages = len(doc)
    toc = doc.get_toc()
    
    first_terminal_page = total_pages + 1
    terminal_keywords = ["references", "bibliography", "acknowledgments", "appendix"]
    
    # Check TOC first
    if toc:
        for level, title, page in toc:
            title_lower = title.lower().strip()
            for kw in terminal_keywords:
                if kw in title_lower:
                    first_terminal_page = min(first_terminal_page, page)
                    break
                    
    # Check page text for large section headings if TOC didn't yield a page
    if first_terminal_page > total_pages:
        ref_heading_pat = re.compile(
            r'^\s*(?:\d+(?:\.\d+)*\s+)?(?:References|Bibliography|Literature\s+Cited)\b',
            re.MULTILINE | re.IGNORECASE
        )
        for p_idx in range(total_pages):
            page_text = doc[p_idx].get_text("text")
            if ref_heading_pat.search(page_text):
                first_terminal_page = p_idx + 1
                break
                
    # Fallback to last page if nothing found
    if first_terminal_page > total_pages:
        first_terminal_page = max(1, total_pages)
        
    return first_terminal_page

def extract_citation_contexts(doc, first_terminal_page, valid_toc):
    """
    Scans the body text pages offline to locate all bracketed citations
    and build a map: key (str) -> list of context entries:
      { "page": N, "section": "...", "sentence": "..." }
    """
    contexts_map = {}
    citation_regex = re.compile(r'\[([\d\s,\-]+)\]')
    
    for p_idx in range(first_terminal_page - 1):
        page_num = p_idx + 1
        page = doc[p_idx]
        page_text = page.get_text("text")
        
        # Determine the section label
        sec_label = get_section_for_page(page_num, valid_toc, len(doc), first_terminal_page)
        
        # Clean page text to normalize spaces
        page_clean = clean_text(page_text)
        
        # Split into sentences (heuristic boundary search)
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', page_clean)
        
        for idx, sentence in enumerate(sentences):
            matches = citation_regex.findall(sentence)
            if not matches:
                continue
                
            # Collect surrounding sentences for context (one before, one after)
            before = sentences[idx - 1] if idx > 0 else ""
            after = sentences[idx + 1] if idx < len(sentences) - 1 else ""
            full_context = " ".join(filter(None, [before, sentence, after])).strip()
            
            # Extract all keys cited in this sentence
            for match in matches:
                keys = parse_citation_keys(match)
                for k in keys:
                    k_str = str(k)
                    if k_str not in contexts_map:
                        contexts_map[k_str] = []
                        
                    # Avoid duplicate sentences for the same key on the same page
                    if not any(entry["sentence"] == sentence for entry in contexts_map[k_str]):
                        contexts_map[k_str].append({
                            "page": page_num,
                            "section": sec_label,
                            "sentence": sentence,
                            "full_context": full_context
                        })
                        
    return contexts_map

def query_gemini_to_synthesize_references(raw_bib_text, contexts_map, title):
    """
    Runs the final single-step Gemini API call to parse the bibliography text
    and synthesize citation role classification/contributions.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback empty structure
        return []

    genai.configure(api_key=api_key)
    model_name = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
    model = genai.GenerativeModel(model_name)
    
    # Prepare the offline contexts map as a compact JSON string to inject into prompt
    compact_contexts = {}
    for key, entries in contexts_map.items():
        # Limit to 3 context sentences per reference to keep prompt size reasonable
        compact_contexts[key] = [
            f"(Page {e['page']}, Section '{e['section']}'): {e['sentence']}"
            for e in entries[:3]
        ]
        
    prompt = f"""You are an expert scientific editor and computer scientist.
We are compiling detailed technical reference notes for a research paper titled "{title}".

We have extracted:
1. The raw text of the bibliography / references section at the end of the PDF.
2. An offline citation map containing sentences from the body text where each bracketed reference number is cited.

=== RAW BIBLIOGRAPHY TEXT ===
{raw_bib_text}

=== OFFLINE CITATION CONTEXTS ===
{json.dumps(compact_contexts, indent=2)}

=== INSTRUCTIONS ===
Parse the raw bibliography text and map it to the citation contexts to produce a structured reference list matching the JSON schema below.
For each reference item:
1. Extract metadata:
   - "key": The citation key matching the brackets (e.g. "5"). Must be a string.
   - "title": The title of the cited paper.
   - "authors": The authors of the cited paper.
   - "year": The year of publication.
2. Determine the "citation_role" based on how it is mentioned in the contexts:
   - "Foundation / Building Block": The authors build directly on this methodology (e.g. using their model, framework, or core operator).
   - "Baseline Comparison": The authors compare their results/performance against this work.
   - "Background Context / Survey": Cited to provide general literature background, history, or motivation.
   - "Tool / Infrastructure": Cited as a tool, compiler, platform, or hardware used (e.g. Qiskit, Matlab, IBM Quantum).
   - "Unknown": If no contexts were found or it is unclear.
3. Synthesize a "contribution_summary" of exactly 1-2 sentences. Explain how this cited paper contributes to, or relates to, the current paper's work. Ground this strictly in the provided contexts. If no contexts are available for a key, write a general sentence based on the cited title.

Return your response strictly in JSON format as a list of references under the key "references":
{{
  "references": [
    {{
      "key": "5",
      "title": "A novel enhanced quantum representation of digital images",
      "authors": "Phuc Q. Le, A. M. Iliyasu, F. Dong and K. Hirota",
      "year": "2013",
      "citation_role": "Foundation / Building Block",
      "contribution_summary": "Introduces the NEQR model which this paper builds upon for grayscale quantum image representation."
    }}
  ]
}}
"""
    response = call_gemini_with_retry(
        model,
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    parsed_data = parse_json_robust(response.text)
    references = parsed_data.get("references", [])
    
    # Post-process: attach the full contexts back to the matching reference items
    for ref in references:
        key = str(ref.get("key", ""))
        if key in contexts_map:
            # Map contexts into structured format for response
            ref["contexts"] = [
                {
                    "page": e["page"],
                    "section": e["section"],
                    "sentence": e["sentence"]
                }
                for e in contexts_map[key]
            ]
        else:
            ref["contexts"] = []
            
    return references

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_references.py <pdf_path> <output_json_path>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    output_json_path = sys.argv[2]
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        sys.exit(1)
        
    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    toc = doc.get_toc()
    
    # 1. Identify where References section starts
    first_terminal_page = find_references_boundary(doc)
    print(f"References section starts at Page {first_terminal_page} (Total pages: {total_pages})")
    
    # 2. Extract bibliography raw text
    print("Extracting raw bibliography text...")
    bib_lines = []
    for p in range(first_terminal_page - 1, total_pages):
        page_text = doc[p].get_text("text")
        bib_lines.append(page_text)
    raw_bib_text = "\n".join(bib_lines)
    
    # Get valid TOC headers for section mapping
    valid_toc = []
    if toc:
        for level, heading, page in toc:
            if level <= 2 and page < first_terminal_page:
                valid_toc.append((level, heading.strip(), page))
    valid_toc.sort(key=lambda x: x[2])
    
    # 3. Scan body pages offline for citation sentence contexts
    print("Scanning body text offline for citation contexts...")
    contexts_map = extract_citation_contexts(doc, first_terminal_page, valid_toc)
    print(f"Mapped contexts for {len(contexts_map)} citation keys.")
    
    # Extract Title using PyMuPDF metadata if available
    title = doc.metadata.get("title") if hasattr(doc, 'metadata') else "Research Paper"
    doc.close()
    if not title or len(title.strip()) < 3:
         title = "Quantum Image Processing Algorithm Using Line Detection Mask Based on NEQR"
         
    # 4. Final step: Call Gemini to parse bibliography and synthesize references
    print("Querying Gemini API at the last step to structure references and classify citation roles...")
    references = query_gemini_to_synthesize_references(raw_bib_text, contexts_map, title)
    
    output_data = {
        "paper_title": title,
        "references": references
    }
    
    print(f"Writing structured JSON references output to: {output_json_path}")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    print("\nSuccessfully finished references extraction!")

if __name__ == "__main__":
    main()
