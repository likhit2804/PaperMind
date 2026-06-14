import fitz
import re
import json
import os
import sys
import math
import google.generativeai as genai
from dotenv import load_dotenv

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

from pipeline.utils import parse_json_robust, call_gemini_with_retry

# Load environment variables
load_dotenv()

# Reconfigure standard output to handle unicode outputs in Windows
sys.stdout.reconfigure(encoding='utf-8')

# Generic English stop words
STOPWORDS = set([
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant', 'cannot', 'could',
    'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having', 'he', 'hed', 'hell', 'hes', 'her', 'here',
    'heres', 'heres', 'herself', 'him', 'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in',
    'into', 'is', 'isnt', 'it', 'its', 'itself', 'lets', 'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor',
    'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own',
    'same', 'shant', 'she', 'shed', 'shell', 'shes', 'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats',
    'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd', 'theyll',
    'theyre', 'theyve', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasnt', 'we',
    'wed', 'well', 'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres', 'which', 'while',
    'who', 'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd', 'youll', 'youre', 'youve',
    'your', 'yours', 'yourself', 'yourselves'
])

# Words that should not be extracted as single-word key terms (unigrams)
GENERIC_UNIGRAM_STOPWORDS = set([
    'use', 'using', 'used', 'user', 'users', 'run', 'running', 'runs', 'set', 'sets', 'system', 'systems',
    'chapter', 'section', 'figure', 'table', 'example', 'examples', 'problem', 'problems', 'solution', 'solutions',
    'process', 'processes', 'thread', 'threads', 'program', 'programs', 'page', 'pages', 'number', 'numbers',
    'one', 'two', 'three', 'new', 'old', 'time', 'times', 'also', 'many', 'must', 'can', 'may', 'should', 'would',
    'could', 'like', 'show', 'shown', 'shows', 'each', 'every', 'other', 'another', 'called', 'known', 'first',
    'second', 'third', 'well', 'need', 'needs', 'needed', 'give', 'given', 'gives', 'case', 'cases', 'way',
    'ways', 'point', 'points', 'line', 'lines', 'part', 'parts', 'value', 'values', 'data', 'information',
    'type', 'types', 'result', 'results', 'following', 'illustrate', 'illustrated', 'describes', 'described',
    'discussed', 'discussion', 'consider', 'considering', 'machine', 'machines', 'various', 'several', 'simple', 
    'complex', 'general', 'specific', 'particular', 'both', 'either', 'neither', 'whether', 'however', 'therefore', 
    'thus', 'hence', 'since', 'because', 'although', 'though', 'even', 'still', 'yet', 'next', 'previous', 'last',
    'high', 'low', 'large', 'small', 'long', 'short', 'fast', 'slow', 'method', 'methods', 'step', 'steps', 'action',
    'actions', 'proposed', 'proposed method', 'proposed algorithm', 'paper', 'article', 'experimental', 'simulated',
    'authors', 'citations', 'citation', 'le', 'sun', 'etc', 'et', 'al', 'et al'
])

def extract_paper_metadata_via_ai(text_snippet, pdf_metadata_title=None):
    """
    Queries Gemini to extract the official title and core canonical domain terms/acronyms 
    from the paper text.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        title = pdf_metadata_title if (pdf_metadata_title and len(pdf_metadata_title.strip()) > 3) else "Research Paper"
        return title, set()

    try:
        genai.configure(api_key=api_key)
        model_name = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""You are a research paper metadata extractor.
Analyze the following text from a scientific research paper:
\"\"\"
{text_snippet}
\"\"\"

Extract:
1. The official Title of this research paper.
2. A comprehensive list of 25-35 core technical terms, specific modules, custom algorithms, proposed methods, hardware gates (e.g., CNOT, Toffoli, Hadamard, MAJ, UMA gates), representation models (e.g., NEQR, FRQI, etc.), mathematical properties, and key theoretical/algorithmic concepts (e.g., quantum measurement, quantum no-cloning principle) central to this paper.

Return your response strictly in JSON format as:
{{
  "title": "Exact Title of the Paper",
  "canonical_seeds": [
    "keyword1",
    "keyword2"
  ]
}}
"""
        response = call_gemini_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = parse_json_robust(response.text)
        title = data.get("title", "").strip()
        if not title and pdf_metadata_title:
            title = pdf_metadata_title
        if not title:
            title = "Research Paper"
            
        seeds = {clean_text(s.strip().lower()) for s in data.get("canonical_seeds", []) if s.strip()}
        
        # Also try to extract keywords via regex from text as a backup/supplement
        kw_match = re.search(r'(?:Keywords|Key\s*words|Index\s*terms)[:\s]+([^\n.]+)', text_snippet, re.IGNORECASE)
        if kw_match:
            regex_kws = [clean_text(k.strip().lower()) for k in re.split(r'[,;.]', kw_match.group(1)) if k.strip()]
            seeds.update(regex_kws)
            
        return title, seeds
    except Exception as e:
        print(f"Warning: Metadata extraction failed: {e}. Falling back to default values.")
        title = pdf_metadata_title if (pdf_metadata_title and len(pdf_metadata_title.strip()) > 3) else "Research Paper"
        return title, set()

def clean_page_text(text, title_clean=""):
    """Strips academic journal boilerplates, margins, emails, math formulas, and citation keys."""
    lines = text.split('\n')
    cleaned_lines = []
    
    # MDPI/academic boilerplate indicators
    boilerplate_patterns = [
        r'entropy\s+\d{4}',
        r'doi\.org',
        r'distributed\s+under\s+the\s+terms',
        r'creativecommons\.org',
        r'citation:',
        r'academic\s+editors',
        r'received:',
        r'revised:',
        r'accepted:',
        r'published:',
        r'copyright:',
        r'college\s+of\s+science',
        r'university',
        r'correspondence:'
    ]
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        # Strip pure page numbers
        if line_strip.isdigit():
            continue
            
        # Strip running headers/footers containing citation info or doi
        if any(re.search(pat, line_strip, re.IGNORECASE) for pat in boilerplate_patterns):
            continue
            
        # Strip email addresses
        if '@' in line_strip and ('.edu' in line_strip or '.com' in line_strip or '.org' in line_strip):
            continue
            
        # Remove parenthesized phrases and bracketed citations to avoid compound nouns interruption
        line_strip = re.sub(r'\([^)]*\)', ' ', line_strip)
        line_strip = re.sub(r'\[[^\]]*\]', ' ', line_strip)

        # Remove Dirac ket notation from the line
        line_strip = re.sub(r'\|[^>⟩]+[>⟩]', ' ', line_strip)
        
        # Remove LaTeX/math symbols
        line_strip = re.sub(r'[\$\\#_\^\{\}]', ' ', line_strip)
        
        # Skip lines that are mostly equations (e.g. contain '=', '+', '-', etc.)
        if line_strip.count('=') >= 1 and any(c in line_strip for c in ['+', '-', '*', '/', '⟩', '|', 'cos', 'sin']):
            continue
            
        cleaned_lines.append(line_strip)
        
    return "\n".join(cleaned_lines)

def extract_clean_text_from_page(page, title_clean=""):
    """Extracts page text, dynamically ignoring code/equation blocks in monospace fonts."""
    blocks_text = []
    try:
        layout = page.get_text("dict")
        for block in layout.get("blocks", []):
            if block.get("type") != 0: # Skip images or drawings
                continue
            block_lines = []
            for line in block.get("lines", []):
                line_spans = []
                is_code_line = False
                for span in line.get("spans", []):
                    font_name = span.get("font", "").lower()
                    # Monospace font indicators
                    if any(m in font_name for m in ["courier", "mono", "consolas", "lucida", "crd", "tele", "code", "terminal"]):
                        is_code_line = True
                        break
                    line_spans.append(span.get("text", ""))
                if is_code_line:
                    continue
                line_text = "".join(line_spans)
                block_lines.append(line_text)
            block_text = "\n".join(block_lines)
            blocks_text.append(block_text)
    except Exception:
        # Fallback to standard text extraction on failure
        return clean_page_text(page.get_text("text"), title_clean)
        
    raw_page_text = "\n".join(blocks_text)
    return clean_page_text(raw_page_text, title_clean)

def clean_text(text):
    """Normalize whitespace and standard ligatures."""
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    return text.strip()

def singularize(word):
    """Simple rule-based singularization for common noun plurals."""
    if word.endswith('ies'):
        return word[:-3] + 'y'
    elif word.endswith('es'):
        if word.endswith('sses') or word.endswith('ses'):
            return word[:-2]
        return word[:-1]
    elif word.endswith('s') and not word.endswith('ss') and not word.endswith('us') and not word.endswith('is'):
        return word[:-1]
    return word

def normalize_phrase(phrase):
    """Normalizes the last word of a phrase to its singular form."""
    words = phrase.split()
    if not words:
        return phrase
    words[-1] = singularize(words[-1])
    return " ".join(words)

def get_ngrams(words, n, min_word_len=3, canonical_seeds=None):
    """Generate n-grams skipping those starting or ending with stopwords, and normalizes plurals."""
    ngrams = []
    for i in range(len(words) - n + 1):
        gram = words[i:i+n]
        if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
            continue
        if any(len(w) < min_word_len or w.isdigit() or re.search(r'\d', w) for w in gram):
            continue
        if n == 1 and gram[0] in GENERIC_UNIGRAM_STOPWORDS:
            # Let it pass if it's a known canonical seed
            if canonical_seeds and gram[0] in canonical_seeds:
                pass
            else:
                continue
        # Check for single-letter math variables that slipped through
        if any(len(w) == 1 and w not in ['a', 'i'] for w in gram):
            continue
        phrase = " ".join(gram)
        ngrams.append(normalize_phrase(phrase))
    return ngrams

def parse_pdf_into_sections(pdf_path, title_clean=""):
    """Chunks PDF text by section boundaries without page overlaps, and strips References/Appendix."""
    print(f"\n--- [PHASE 1] Slicing & Boundary Partitioning ---")
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    total_pages = len(doc)
    
    # 1. Identify outline nodes and terminal page
    valid_toc = []
    first_terminal_page = total_pages + 1
    
    terminal_keywords = ["references", "bibliography", "acknowledgments", "appendix"]
    
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
                
    if not valid_toc:
        print("TOC Outline not found inside PDF metadata. Falling back to page-by-page scan...")
        # Fallback: chunk by page ranges
        for p in range(1, min(14, total_pages + 1)):
            valid_toc.append((1, f"Section Page {p}", p))
            
    valid_toc.sort(key=lambda x: x[2])
    first_terminal_page = min(first_terminal_page, total_pages + 1)
    
    print(f"Detected outlines/sections for Paper:")
    for level, heading, page in valid_toc:
        print(f"  - [{level}] Heading: '{heading}' starting on PDF Page {page}")
    print(f"  - Excluded references/appendix sections starting at PDF Page {first_terminal_page}")
    
    sections = []
    for i in range(len(valid_toc)):
        level, heading, start_page = valid_toc[i]
        
        if i + 1 < len(valid_toc):
            end_page = valid_toc[i + 1][2]
            if end_page > start_page:
                adjusted_end = end_page - 1
            else:
                adjusted_end = end_page
        else:
            adjusted_end = min(total_pages, first_terminal_page - 1)
            
        pages_data = []
        raw_text = ""
        for p in range(start_page - 1, adjusted_end):
            page_obj = doc[p]
            p_clean = extract_clean_text_from_page(page_obj, title_clean)
            pages_data.append((p + 1, p_clean))
            raw_text += p_clean + "\n"
            
        print(f"  - Compiled Section '{heading}' -> mapping to PDF Pages {start_page} to {adjusted_end}")
        sections.append({
            "label": heading,
            "raw_text": raw_text,
            "page_start": start_page,
            "pages_data": pages_data
        })
        
    doc.close()
    return sections

def calculate_tfidf_concepts(sections, canonical_seeds, max_candidates=8, min_word_len=3, use_unigrams=True, use_bigrams=True, use_trigrams=True, apply_overlap_pruning=True):
    """Computes TF-IDF on n-grams to retrieve top candidates per section."""
    print(f"\n--- [PHASE 2] Local Candidate Term Generation (Smoothed TF-IDF) ---")
    section_tokens = {}
    all_vocabulary = set()
    
    for sec in sections:
        clean_sec_text = clean_text(sec["raw_text"])
        words = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_sec_text.lower()).split()
        words = [w for w in words if w]
        
        candidates = []
        if use_unigrams:
            candidates += get_ngrams(words, 1, min_word_len, canonical_seeds)
        if use_bigrams:
            candidates += get_ngrams(words, 2, min_word_len, canonical_seeds)
        if use_trigrams:
            candidates += get_ngrams(words, 3, min_word_len, canonical_seeds)
        
        section_tokens[sec["label"]] = candidates
        all_vocabulary.update(candidates)
        
    df = {}
    for term in all_vocabulary:
        df[term] = sum(1 for sec in sections if term in section_tokens[sec["label"]])

    section_concepts = {}
    for sec in sections:
        label_key = sec["label"]
        tokens = section_tokens[label_key]
        if not tokens:
            continue
            
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
            
        scores = {}
        for term, count in tf.items():
            tf_val = count / len(tokens)
            idf_val = 1.0 + math.log((1.0 + len(sections)) / (1.0 + df[term]))
            
            # Canonical seed term boost
            boost = 1.0
            if canonical_seeds:
                if term in canonical_seeds:
                    boost = 3.0
                else:
                    for canonical in canonical_seeds:
                        if re.search(r'\b' + re.escape(canonical) + r'\b', term):
                            boost = 2.0
                            break
            scores[term] = tf_val * idf_val * boost
            
        sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = []
        for term, score in sorted_terms:
            if len(selected) >= max_candidates:
                break
            if not apply_overlap_pruning:
                selected.append(term)
            else:
                overlap_found = False
                replaced = False
                for idx, s in enumerate(selected):
                    if s in term and len(s) < len(term):
                        selected[idx] = term
                        replaced = True
                        break
                    if term in s and len(term) < len(s):
                        overlap_found = True
                        break
                if not overlap_found and not replaced:
                    selected.append(term)
                
        section_concepts[label_key] = selected
        print(f"Section '{label_key}' Candidates (Token Count: {len(tokens)}):")
        for idx, term in enumerate(selected):
            term_score = scores[term]
            term_tf = tf[term]
            term_df = df[term]
            print(f"  Candidate {idx+1}: '{term}' (Score: {term_score:.5f}, Count: {term_tf}, DF: {term_df})")
        
    return section_concepts

def filter_terms_via_ai(candidates, title, canonical_seeds):
    """
    Uses Gemini API to validate scientific research paper terms, filtering out math variables, 
    citations, boilerplates, common words, and grammar fragments.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Skipping AI verification pass.")
        return candidates

    try:
        genai.configure(api_key=api_key)
        model_name = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""You are an expert scientific journal peer reviewer and academic editor.
We have extracted a list of key term candidates from a research paper titled "{title}".
Some of these terms are noisy, mathematical variables, layout remnants, or too generic.

Review the following candidate list:
{json.dumps(candidates, indent=2)}

Filter this list to keep ONLY valid Computer Science, Quantum Computing, Image Processing, or formal research-relevant technical concepts.
Specifically:
- REMOVE: mathematical variables or formula parameters (e.g. 'x', 'y', 'n', 'i', 'psi', variables)
- REMOVE: generic common words/verbs that are not technical terms (e.g. 'typical', 'general', 'enters', 'execution', 'remaining', 'solution', 'problem', 'need', 'must', 'various', 'show', 'step')
- REMOVE: citation markers or author names (e.g. 'citation', 'et al', 'le', 'sun')
- REMOVE: layout-related labels or captions (e.g. 'figure', 'table', 'section', 'page')
- REMOVE: grammatical fragments, incomplete phrases, or punctuation artifacts (e.g. 'will', 'with', 'from', 'etc')
- KEEP: core contributions, algorithms, models, modules, and experimental analysis concepts (e.g. named algorithms, custom circuit/architectural modules, representation schemes, or formal complexity definitions discussed in the text)

Return your response strictly in JSON format as an object with the key "verified_terms" containing a list of strings:
{{
  "verified_terms": [
    "verified term 1",
    "verified term 2"
  ]
}}
"""
        response = call_gemini_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Parse the JSON response
        data = parse_json_robust(response.text)
        verified = data.get("verified_terms", [])
        # Lowercase and strip for consistency
        verified_clean = {t.strip().lower() for t in verified if isinstance(t, str)}
        
        # Keep only elements that are actually in the original candidates list (preventing hallucinations)
        final_verified = []
        for c in candidates:
            c_clean = c.lower().strip()
            # Retain if verified by AI OR if it's a known canonical seed
            if c_clean in verified_clean or (canonical_seeds and c_clean in canonical_seeds):
                final_verified.append(c)
                
        print(f"AI Filtering: Input {len(candidates)} candidates -> Output {len(final_verified)} verified concepts.")
        return final_verified
    except Exception as e:
        print(f"Warning: Gemini API call failed with error: {e}. Falling back to unverified list.")
        return candidates

class TraceLogger:
    def __init__(self, log_path="paper_extraction_trace.log"):
        self.log_path = log_path
        self.log_file = None
        self.original_stdout = sys.stdout

    def start(self):
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self.log_file.write("=== Research Paper Extraction Trace ===\n\n")
        self.log_file.flush()
        sys.stdout = self.log_file

    def stop(self):
        sys.stdout = self.original_stdout
        if self.log_file:
            self.log_file.close()

    def console_print(self, message):
        self.original_stdout.write(message + "\n")
        self.original_stdout.flush()

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_concepts.py <pdf_path> <output_json>")
        sys.exit(1)
        
    pdf = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)

    output_dir = os.path.dirname(output_path)
    log_path = os.path.join(output_dir, "paper_extraction_trace.log") if output_dir else "paper_extraction_trace.log"
    logger = TraceLogger(log_path)
    logger.console_print(f"Extracting key terms from Paper: {pdf}")
    
    logger.start()
    
    # 1. Segment text
    logger.console_print("Phase 1: Segmenting paper sections and pruning references...")
    sections = parse_pdf_into_sections(pdf, "")
    if not sections:
        logger.stop()
        logger.console_print("Error: Could not extract paper sections.")
        sys.exit(1)
        
    # 0. Extract Dynamic Metadata from all clean, segment-extracted text
    logger.console_print("Phase 0: Extracting paper title and canonical seeds dynamically from all sections...")
    full_cleaned_text = "\n".join([sec["raw_text"] for sec in sections])
    
    doc = fitz.open(pdf)
    metadata_title = doc.metadata.get("title") if hasattr(doc, 'metadata') else None
    doc.close()
    
    title, canonical_seeds = extract_paper_metadata_via_ai(full_cleaned_text, metadata_title)
    
    logger.console_print(f"  - Extracted Title: '{title}'")
    logger.console_print(f"  - Extracted Canonical Seeds ({len(canonical_seeds)}): {list(canonical_seeds)}")
    
    # 2. Local Candidate Extraction
    logger.console_print("Phase 2: Calculating local smoothed TF-IDF candidate n-grams...")
    section_candidates = calculate_tfidf_concepts(sections, canonical_seeds)
    
    # Deduplicate and consolidate globally
    logger.console_print("Phase 3: Consolidating and deduplicating unique key terms list...")
    all_terms = set()
    for label, candidates in section_candidates.items():
        for term in candidates:
            all_terms.add(term.strip().lower())
            
    # Post-processing Canonical verification pass
    raw_paper_text_lower = " ".join([sec["raw_text"].lower() for sec in sections])
    raw_paper_text_lower = clean_text(raw_paper_text_lower)
    boosted_additions = []
    if canonical_seeds:
        for canonical in canonical_seeds:
            if canonical not in all_terms:
                matches = len(re.findall(r'\b' + re.escape(canonical) + r'\b', raw_paper_text_lower))
                if matches >= 1: # Lower frequency threshold for sparse terms in shorter papers
                    boosted_additions.append(canonical)
                
    if boosted_additions:
        all_terms.update(boosted_additions)
        logger.console_print(f"Post-Processing Pass: Recovered {len(boosted_additions)} canonical terms: {boosted_additions}")
        
    sorted_unique_terms = sorted(list(all_terms))
    
    # Phase 4: AI Semantic Verification Filter
    logger.console_print("Phase 4: Running Gemini AI Semantic Verification Filter...")
    verified_terms = filter_terms_via_ai(sorted_unique_terms, title, canonical_seeds)
    verified_set = set(verified_terms)
    
    # Back-propagate verification to sections
    filtered_section_candidates = {}
    for label, candidates in section_candidates.items():
        filtered_section = [c for c in candidates if c.strip().lower() in verified_set]
        filtered_section_candidates[label] = filtered_section
        
    logger.stop()
    
    output_data = {
        "paper_title": title,
        "sections": filtered_section_candidates,
        "unique_key_terms": sorted(list(verified_set))
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    logger.console_print(f"\nSuccessfully wrote {len(verified_set)} unique key terms to {output_path}!")
    logger.console_print(f"Detailed step-by-step trace saved to: {log_path}")

if __name__ == "__main__":
    main()
