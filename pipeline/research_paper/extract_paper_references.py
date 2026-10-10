from _bootstrap import *
from pipeline.research_paper.extract_paper_concepts import clean_text
from pipeline.utils import parse_json_robust, call_gemini_with_retry, get_gemini_model, get_pdf_title
from pipeline.research_paper.pdf_utils import parse_toc, get_section_for_page, split_sentences
from pipeline.research_paper.tex_utils import extract_tex_references, extract_tex_cite_contexts, get_tex_title


def parse_citation_keys(bracket_text):
    """
    Parses bracket contents like:
    - Numeric: "1", "2, 3", "4-6", "7, 8, 12-15"
    - Author-Year / Alpha: "Vaswani et al., 2017", "Vaswani17", "Goodfellow2014"
    into a list of string keys.
    """
    keys = []
    cleaned = bracket_text.strip()
    parts = re.split(r'[,;]+', cleaned)
    
    for part in parts:
        p = part.strip()
        if not p:
            continue
            
        if '-' in p and not any(c.isalpha() for c in p):
            # Numeric range match, e.g. "4-6" or "12-15"
            range_parts = p.split('-')
            if len(range_parts) == 2 and range_parts[0].isdigit() and range_parts[1].isdigit():
                start = int(range_parts[0])
                end = int(range_parts[1])
                if start <= end and (end - start) < 50:
                    keys.extend([str(k) for k in range(start, end + 1)])
                else:
                    keys.append(p)
            else:
                keys.append(p)
        else:
            keys.append(p)
            
    return keys


def find_references_boundary(doc):
    """
    Searches the document table of contents (TOC) and pages
    to find where the References/Bibliography section starts.
    Returns the 1-based page index.
    """
    total_pages = len(doc)
    _, first_terminal_page = parse_toc(doc)

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
    Scans body text pages to locate bracketed and parenthetical citations:
    1. Numeric Brackets: [1], [2, 3], [4-6]
    2. Author-Year Brackets/Parens: [Vaswani et al., 2017], (Goodfellow et al., 2014)
    3. Narrative Citations: Vaswani et al. (2017)
    
    Returns a map: key (str) -> list of context entries:
      { "page": N, "section": "...", "sentence": "...", "full_context": "..." }
    """
    contexts_map = {}
    
    # Dual regex patterns: Numeric + Author-Year
    numeric_regex = re.compile(r'\[([\d\s,\-]+)\]')
    author_year_regex = re.compile(r'(?:\[|\()([A-Z][a-zA-Z\s\.\&]+(?:et\s+al\.?)?,?\s*\d{4}[a-z]?)(?:\]|\))')
    narrative_regex = re.compile(r'\b([A-Z][a-zA-Z]+(?:\s+et\s+al\.)?)\s*\((\d{4}[a-z]?)\)')

    for p_idx in range(first_terminal_page - 1):
        page_num = p_idx + 1
        page = doc[p_idx]
        page_text = page.get_text("text")
        
        # Determine the section label
        sec_label = get_section_for_page(page_num, valid_toc, len(doc), first_terminal_page)
        
        # Clean page text to normalize spaces
        page_clean = clean_text(page_text)
        
        # Split into sentences
        sentences = split_sentences(page_clean)
        
        for idx, sentence in enumerate(sentences):
            found_keys = []
            
            # 1. Numeric matches
            num_matches = numeric_regex.findall(sentence)
            for m in num_matches:
                found_keys.extend(parse_citation_keys(m))
                
            # 2. Author-Year matches
            ay_matches = author_year_regex.findall(sentence)
            for m in ay_matches:
                found_keys.append(m.strip())

            # 3. Narrative matches
            nar_matches = narrative_regex.findall(sentence)
            for author, year in nar_matches:
                found_keys.append(f"{author}, {year}")

            if not found_keys:
                continue

            # Collect surrounding sentences for context (one before, one after)
            before = sentences[idx - 1] if idx > 0 else ""
            after = sentences[idx + 1] if idx < len(sentences) - 1 else ""
            full_context = " ".join(filter(None, [before, sentence, after])).strip()

            for k_str in found_keys:
                if k_str not in contexts_map:
                    contexts_map[k_str] = []
                    
                if not any(entry["sentence"] == sentence for entry in contexts_map[k_str]):
                    contexts_map[k_str].append({
                        "page": page_num,
                        "section": sec_label,
                        "sentence": sentence,
                        "full_context": full_context
                    })
                        
    return contexts_map


def classify_citation_role_offline(sentence_text):
    """
    Deterministic rule-based keyword classifier for citation intent/role.
    Used for offline fallback when API key is unavailable or rate-limited.
    """
    st = sentence_text.lower()
    
    # 1. Baseline Comparison
    if any(w in st for w in ["compare", "compared", "baseline", "outperform", "outperformed", "vs.", "versus", "benchmark", "sota", "state-of-the-art"]):
        return "Baseline Comparison"
        
    # 2. Foundation / Building Block
    if any(w in st for w in ["build on", "builds on", "extend", "extending", "framework", "architecture", "proposed by", "based on", "inspired by", "adopt"]):
        return "Foundation / Building Block"
        
    # 3. Tool / Infrastructure
    if any(w in st for w in ["qiskit", "matlab", "gurobi", "scip", "python", "pytorch", "tensorflow", "code available", "library", "package", "dataset"]):
        return "Tool / Infrastructure"
        
    # 4. Background Context / Survey
    if any(w in st for w in ["survey", "review", "introduced", "pioneered", "demonstrated", "shown", "reported", "previously", "earlier work"]):
        return "Background Context / Survey"
        
    return "Background Context / Survey"


def parse_raw_bibliography_offline(raw_bib_text, contexts_map):
    """
    Regex fallback parser that parses raw bibliography text into structured entries
    when Gemini API calls are skipped or unavailable.
    """
    entries = []
    # Pattern to match numbered entries like [1] Author et al. Title... or 1. Author...
    bib_item_pat = re.compile(r'^\s*\[?(\d+|[A-Za-z0-9\.\-\&]+)\]?\s+(.*)', re.MULTILINE)
    matches = bib_item_pat.findall(raw_bib_text)
    
    if matches:
        for key, text in matches:
            year_match = re.search(r'\b(19\d\d|20\d\d)\b', text)
            year = year_match.group(1) if year_match else "N/A"
            
            parts = text.split('.')
            authors = parts[0].strip() if len(parts) > 0 else "Unknown Authors"
            title = parts[1].strip() if len(parts) > 1 else text[:80] + "..."
            
            ctx_entries = contexts_map.get(str(key), [])
            sample_sentence = ctx_entries[0]["sentence"] if ctx_entries else ""
            role = classify_citation_role_offline(sample_sentence) if sample_sentence else "Unknown"
            
            summary = f"Cited as a {role.lower()} reference in the document."
            if sample_sentence:
                summary = f"Cited in context: '{sample_sentence[:120]}...'"

            entries.append({
                "key": str(key),
                "title": title,
                "authors": authors,
                "year": year,
                "citation_role": role,
                "contribution_summary": summary,
                "contexts": [
                    {
                        "page": e["page"],
                        "section": e["section"],
                        "sentence": e["sentence"]
                    }
                    for e in ctx_entries
                ]
            })
            
    if not entries:
        blocks = [b.strip() for b in raw_bib_text.split('\n\n') if len(b.strip()) > 15]
        for idx, block in enumerate(blocks):
            key = str(idx + 1)
            year_match = re.search(r'\b(19\d\d|20\d\d)\b', block)
            year = year_match.group(1) if year_match else "N/A"
            parts = block.split('.')
            authors = parts[0].strip() if len(parts) > 0 else "Unknown Authors"
            title = parts[1].strip() if len(parts) > 1 else block[:80] + "..."
            ctx_entries = contexts_map.get(key, [])
            sample_sentence = ctx_entries[0]["sentence"] if ctx_entries else ""
            role = classify_citation_role_offline(sample_sentence) if sample_sentence else "Unknown"
            
            entries.append({
                "key": key,
                "title": title,
                "authors": authors,
                "year": year,
                "citation_role": role,
                "contribution_summary": f"Cited in paper: '{block[:100]}...'",
                "contexts": [
                    {
                        "page": e["page"],
                        "section": e["section"],
                        "sentence": e["sentence"]
                    }
                    for e in ctx_entries
                ]
            })

    return entries


def query_gemini_to_synthesize_references(raw_bib_text, contexts_map, title):
    """
    Runs Gemini API call to parse raw bibliography text into structured JSON.
    Includes deterministic offline fallback if API call fails or key is missing.
    """
    model, api_key = get_gemini_model()
    if not model or not api_key:
        print("[Offline Fallback] No active Gemini API key found. Executing regex bibliography parser.")
        return parse_raw_bibliography_offline(raw_bib_text, contexts_map)

    # Prepare compact contexts map to inject into prompt
    compact_contexts = {}
    for key, entries in contexts_map.items():
        compact_contexts[key] = [
            f"(Page {e['page']}, Section '{e['section']}'): {e['sentence']}"
            for e in entries[:3]
        ]
        
    prompt = f"""You are an expert scientific editor and computer scientist.
We are compiling detailed technical reference notes for a research paper titled "{title}".

We have extracted:
1. The raw text of the bibliography / references section at the end of the PDF.
2. An offline citation map containing sentences from the body text where each bracketed or parenthetical reference key is cited.

=== RAW BIBLIOGRAPHY TEXT ===
{raw_bib_text[:12000]}

=== OFFLINE CITATION CONTEXTS ===
{json.dumps(compact_contexts, indent=2)[:8000]}

=== INSTRUCTIONS ===
Parse the raw bibliography text and map it to the citation contexts to produce a structured reference list matching the JSON schema below.
For each reference item:
1. Extract metadata:
   - "key": The citation key matching the brackets (e.g. "5", "Vaswani17"). Must be a string.
   - "title": The title of the cited paper.
   - "authors": The authors of the cited paper.
   - "year": The year of publication.
2. Determine the "citation_role" based on how it is mentioned in the contexts:
   - "Foundation / Building Block": The authors build directly on this methodology (e.g. using their model, framework, or core operator).
   - "Baseline Comparison": The authors compare their results/performance against this work.
   - "Background Context / Survey": Cited to provide general literature background, history, or motivation.
   - "Tool / Infrastructure": Cited as a tool, compiler, platform, or hardware used (e.g. Qiskit, Matlab, Gurobi).
   - "Unknown": If no contexts were found or it is unclear.
3. Synthesize a "contribution_summary" of exactly 1-2 sentences. Explain how this cited paper contributes to, or relates to, the current paper's work. Ground this strictly in the provided contexts.

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
    try:
        response = call_gemini_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        parsed_data = parse_json_robust(response.text)
        references = parsed_data.get("references", [])
    except Exception as e:
        print(f"[Offline Fallback] Gemini API call failed ({e}). Executing local regex bibliography parser.")
        return parse_raw_bibliography_offline(raw_bib_text, contexts_map)

    # Post-process: attach full contexts to matching reference items
    for ref in references:
        key = str(ref.get("key", "")).strip()
        matched_ctx = []
        if key in contexts_map:
            matched_ctx = contexts_map[key]
        else:
            norm_key = re.sub(r'\D', '', key)
            if norm_key and norm_key in contexts_map:
                matched_ctx = contexts_map[norm_key]
                
        ref["contexts"] = [
            {
                "page": e["page"],
                "section": e["section"],
                "sentence": e["sentence"]
            }
            for e in matched_ctx
        ]

    return references


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_references.py <pdf_or_tex_path> <output_json_path>")
        sys.exit(1)

    input_path       = sys.argv[1]
    output_json_path = sys.argv[2]

    if not os.path.exists(input_path):
        print(f"Error: input file not found at {input_path}")
        sys.exit(1)

    # ------------------------------------------------------------------ .tex path
    if input_path.lower().endswith('.tex'):
        print(f"[.tex mode] Extracting references locally from LaTeX source: {input_path}")
        with open(input_path, encoding='utf-8', errors='replace') as _f:
            _raw = _f.read()
        title = get_tex_title(_raw)

        bib_entries = extract_tex_references(input_path)
        if bib_entries:
            raw_bib_text = "\n".join(
                f"[{e['key']}] {e['text']}" for e in bib_entries
            )
            print(f"Found {len(bib_entries)} \\bibitem entries in .tex source.")
        else:
            raw_bib_text = ""
            print("No \\bibitem entries found — Gemini will work from context only.")

        print("Scanning .tex body for \\cite contexts...")
        raw_ctx = extract_tex_cite_contexts(input_path)
        contexts_map = {
            key: [{'sentence': e['sentence'], 'full_context': e['full_context'],
                   'page': 0, 'section': e['section']}
                  for e in entries]
            for key, entries in raw_ctx.items()
        }
        print(f"Mapped \\cite contexts for {len(contexts_map)} keys.")

    else:
        # ---------------------------------------------------------------- PDF path
        pdf_path = input_path
        print(f"Opening PDF: {pdf_path}")
        doc         = fitz.open(pdf_path)
        total_pages = len(doc)

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

        # 3. Get TOC + scan body pages offline for citation sentence contexts
        valid_toc, _ = parse_toc(doc)
        title = get_pdf_title(doc, fallback="Quantum Image Processing Algorithm Using Line Detection Mask Based on NEQR")
        print("Scanning body text offline for citation contexts...")
        contexts_map = extract_citation_contexts(doc, first_terminal_page, valid_toc)
        print(f"Mapped contexts for {len(contexts_map)} citation keys.")
        doc.close()

    # 4. Final step: Call Gemini or offline fallback to structure references and classify roles
    print("Structuring references and classifying citation roles...")
    references = query_gemini_to_synthesize_references(raw_bib_text, contexts_map, title)

    output_data = {
        "paper_title": title,
        "references":  references
    }

    print(f"Writing structured JSON references output to: {output_json_path}")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print("\nSuccessfully finished references extraction!")

if __name__ == "__main__":
    main()
