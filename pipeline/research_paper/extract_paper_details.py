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
load_dotenv()

def find_references_boundary(doc):
    """
    Finds where the References/Bibliography section starts.
    """
    total_pages = len(doc)
    toc = doc.get_toc()
    first_terminal_page = total_pages + 1
    terminal_keywords = ["references", "bibliography", "acknowledgments", "appendix"]
    
    if toc:
        for level, title, page in toc:
            title_lower = title.lower().strip()
            for kw in terminal_keywords:
                if kw in title_lower:
                    first_terminal_page = min(first_terminal_page, page)
                    break
                    
    if first_terminal_page > total_pages:
        ref_heading_pat = re.compile(
            r'^\s*(?:\d+(?:\.\d+)*\s+)?(References|Bibliography|Literature\s+Cited)\b',
            re.MULTILINE | re.IGNORECASE
        )
        for p_idx in range(total_pages):
            page_text = doc[p_idx].get_text("text")
            if ref_heading_pat.search(page_text):
                first_terminal_page = p_idx + 1
                break
                
    if first_terminal_page > total_pages:
        first_terminal_page = max(1, total_pages)
        
    return first_terminal_page

def get_outline_for_page(page_num, valid_toc):
    """
    Given a page number, looks up the preceding Level 1 heading (section)
    and Level 2 heading (subsection) from the table of contents.
    """
    active_section = "Introduction"
    active_subsection = ""
    for level, heading, start_page in valid_toc:
        if page_num >= start_page:
            if level == 1:
                active_section = heading
                active_subsection = ""
            elif level == 2:
                active_subsection = heading
        else:
            break
    return active_section, active_subsection

def extract_candidate_sentences(doc, first_terminal_page, valid_toc):
    """
    Scans the body pages offline to gather candidate sentences for:
      - Assumptions & scope limitations (sentences containing keywords like assume, limit, requires)
      - Future work directions (sentences containing keywords like future, extend, ongoing)
    """
    assumption_sentences = []
    future_sentences = []
    
    # High-recall assumptions keywords
    assumption_pat = re.compile(
        r'\b(assum|limit|constraint|restrict|bound|criteria|ideal|unless|condition|depend|requir|hypoth|presum|suppos)\w*\b',
        re.IGNORECASE
    )
    
    # High-recall future work keywords
    future_pat = re.compile(
        r'\b(future|extend|next\s+step|outlook|further|ongoing|promis|investigat|follow\s*\-*\s*up|later)\w*\b',
        re.IGNORECASE
    )
    
    for p_idx in range(first_terminal_page - 1):
        page_num = p_idx + 1
        page = doc[p_idx]
        page_text = page.get_text("text")
        
        # Determine active section/subsection structurally
        sec_label, sub_label = get_outline_for_page(page_num, valid_toc)
        
        # Clean page text to normalize spaces
        page_clean = clean_text(page_text)
        
        # Split into sentences
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', page_clean)
        
        for sentence in sentences:
            sentence_strip = sentence.strip()
            if not sentence_strip or len(sentence_strip) < 15:
                continue
                
            sentence_data = {
                "page": page_num,
                "section": sec_label,
                "subsection": sub_label,
                "sentence": sentence_strip
            }
                
            # Check Assumption & Limitation Candidates
            if assumption_pat.search(sentence_strip):
                assumption_sentences.append(sentence_data)
                
            # Check Future Work Candidates
            if future_pat.search(sentence_strip):
                future_sentences.append(sentence_data)
                
    return assumption_sentences, future_sentences

def query_gemini_to_synthesize_details(assumption_candidates, future_candidates, title):
    """
    Calls Gemini in a single final batch call to:
      1. Identify the true assumptions and scope limitations.
      2. Synthesize future work directions.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"assumptions_and_limitations": [], "future_work": []}

    genai.configure(api_key=api_key)
    model_name = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
    model = genai.GenerativeModel(model_name)
    
    # Format candidates compactly for the prompt. Limit lists to avoid token limits
    assump_str = "\n".join([f"- (Page {c['page']}, Section '{c['section']}', Subsection '{c['subsection']}'): {c['sentence']}" for c in assumption_candidates[:200]])
    future_str = "\n".join([f"- (Page {c['page']}, Section '{c['section']}', Subsection '{c['subsection']}'): {c['sentence']}" for c in future_candidates[:120]])
    
    prompt = f"""You are an expert scientific peer reviewer and research analyst.
We are compiling detailed technical notes for a research paper titled "{title}".

We have run a high-recall offline pre-filtering pass to extract candidate sentences from the paper. These candidates contain false positives (noise), which you MUST filter out.

=== CANDIDATE ASSUMPTION & LIMITATION SENTENCES ===
{assump_str}

=== CANDIDATE FUTURE WORK SENTENCES ===
{future_str}

=== INSTRUCTIONS ===
1. **Assumptions & Limitations**:
   - Filter through candidate assumptions sentences. Identify true underlying research assumptions (e.g., noise-free gates, specific initializations) and limitations (e.g., bounds on dimensions, hardware constraints).
   - Classify each as either "Assumption" or "Limitation".
   - Match each to its exact verbatim supporting sentences from the candidate lists.
   - Ignore sentences that just mention keywords in general context (like *"we do not limit the discussion"*).
2. **Future Work Directions**:
   - Filter through candidate future work sentences. Synthesize actual future steps or research opportunities explicitly stated by the authors.
   - Provide a clear description and match it to its exact verbatim supporting sentences from the candidate lists.

=== DYNAMIC ANCHORING REQUIREMENT ===
Each extracted item MUST include a list of supporting "anchors".
An anchor is an object containing:
  - "section": The structural Level 1 section heading (string) where the sentence appears.
  - "subsection": The structural Level 2 subsection heading (string, or empty string if none) where the sentence appears.
  - "page": The page number (integer) where the sentence appears.
  - "anchor_text": The EXACT verbatim sentence from the candidate lists that supports this detail (do not edit, paraphrase, or summarize this text string, as it must match the source PDF verbatim for structural anchoring search).

Return your response strictly in JSON format matching this schema:
{{
  "assumptions_and_limitations": [
    {{
      "type": "Assumption",
      "description": "The input quantum image dimensions are restricted to powers of two (2^n x 2^n).",
      "anchors": [
        {{
          "section": "Quantum Representation of Image",
          "subsection": "NEQR Model",
          "page": 3,
          "anchor_text": "For a 2n × 2n image, n is an integer representing..."
        }}
      ]
    }}
  ],
  "future_work": [
    {{
      "description": "Extending the line detection mask to multi-channel color representations (e.g. MCQI or QRHSI models).",
      "anchors": [
        {{
          "section": "Simulation Analysis",
          "subsection": "",
          "page": 12,
          "anchor_text": "In future work, we will explore extending our line detection operator to multi-channel quantum representations..."
        }}
      ]
    }}
  ]
}}
"""
    response = call_gemini_with_retry(
        model,
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    return parse_json_robust(response.text)

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_details.py <pdf_path> <output_json_path>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    output_json_path = sys.argv[2]
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        sys.exit(1)
        
    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # Locate References boundary
    first_terminal_page = find_references_boundary(doc)
    print(f"Restricting body text scan to pages 1 to {first_terminal_page - 1}...")
    
    # Get valid TOC headers for section mapping
    valid_toc = []
    toc = doc.get_toc()
    if toc:
        for level, heading, page in toc:
            if level <= 2 and page < first_terminal_page:
                valid_toc.append((level, heading.strip(), page))
    valid_toc.sort(key=lambda x: x[2])
    
    # 1. Offline high-recall filtering
    print("Running high-recall offline pre-filtering for sentences...")
    assump_cands, future_cands = extract_candidate_sentences(doc, first_terminal_page, valid_toc)
    print(f"Extracted candidate sentence counts:")
    print(f"  - Assumptions/Limitations sentences: {len(assump_cands)}")
    print(f"  - Future Work sentences: {len(future_cands)}")
    
    # Get title from metadata
    title = doc.metadata.get("title") if hasattr(doc, 'metadata') else "Research Paper"
    doc.close()
    if not title or len(title.strip()) < 3:
         title = "Quantum Image Processing Algorithm Using Line Detection Mask Based on NEQR"
         
    # 2. Call Gemini at the final step to filter noise and structure details
    print("Querying Gemini API at the final step for high-precision filtering and synthesis...")
    details = query_gemini_to_synthesize_details(assump_cands, future_cands, title)
    
    print(f"Writing structured details JSON output to: {output_json_path}")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(details, f, indent=2)
        
    print("\nSuccessfully finished paper details extraction!")

if __name__ == "__main__":
    main()
