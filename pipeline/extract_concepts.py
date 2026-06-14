import fitz
import re
import json
import os
import sys
import math
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reconfigure standard output to handle unicode outputs in Windows
sys.stdout.reconfigure(encoding='utf-8')

# Generic English stop words (no domain-specific terms)
STOPWORDS = set([
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant', 'cannot', 'could',
    'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having', 'he', 'hed', 'hell', 'hes', 'her', 'here',
    'heres', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in',
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
# because they are generic verbs, nouns, or transitional words.
GENERIC_UNIGRAM_STOPWORDS = set([
    'use', 'using', 'used', 'user', 'users', 'run', 'running', 'runs', 'set', 'sets', 'system', 'systems',
    'chapter', 'section', 'figure', 'table', 'example', 'examples', 'problem', 'problems', 'solution', 'solutions',
    'process', 'processes', 'thread', 'threads', 'program', 'programs', 'page', 'pages', 'number', 'numbers',
    'one', 'two', 'three', 'new', 'old', 'time', 'times', 'also', 'many', 'must', 'can', 'may', 'should', 'would',
    'could', 'like', 'show', 'shown', 'shows', 'each', 'every', 'other', 'another', 'called', 'known', 'first',
    'second', 'third', 'well', 'need', 'needs', 'needed', 'give', 'given', 'gives', 'case', 'cases', 'way',
    'ways', 'point', 'points', 'line', 'lines', 'part', 'parts', 'value', 'values', 'data', 'information',
    'type', 'types', 'result', 'results', 'following', 'illustrate', 'illustrated', 'describes', 'described',
    'discussed', 'discussion', 'consider', 'considering', 'machine', 'machines', 'operating', 'operation',
    'operations', 'various', 'several', 'simple', 'complex', 'general', 'specific', 'particular', 'must',
    'should', 'both', 'either', 'neither', 'whether', 'however', 'therefore', 'thus', 'hence', 'since',
    'because', 'although', 'though', 'even', 'still', 'yet', 'so', 'then', 'here', 'there', 'when', 'where',
    'why', 'how', 'who', 'whom', 'which', 'what', 'whose', 'only', 'even', 'just', 'more', 'most', 'less',
    'least', 'much', 'many', 'some', 'any', 'none', 'all', 'both', 'each', 'every', 'other', 'another',
    'different', 'same', 'similar', 'next', 'previous', 'last', 'first', 'second', 'third', 'high', 'low',
    'large', 'small', 'long', 'short', 'wide', 'narrow', 'deep', 'shallow', 'heavy', 'light', 'fast', 'slow',
    'true', 'false', 'list', 'lists', 'method', 'methods', 'turn', 'turns', 'execution', 'execute', 'executing',
    'enters', 'enter', 'entering', 'exit', 'exits', 'exiting', 'remain', 'remains', 'remainder', 'typical', 'general',
    'object', 'objects', 'memory', 'memories', 'file', 'files', 'kernel', 'kernels', 'operating system',
    'operating systems', 'software', 'softwares', 'hardware', 'hardwares', 'process', 'processes', 'thread', 'threads',
    'int', 'void', 'char', 'double', 'float', 'long', 'short', 'unsigned', 'signed', 'register', 'static', 'extern',
    'null', 'nil', 'const', 'return', 'goto', 'break', 'continue', 'typedef', 'struct', 'union', 'sizeof',
    'class', 'public', 'private', 'protected', 'import', 'include', 'define', 'def', 'func', 'function',
    'ptr', 'shm', 'ecb', 'zf', 'nf', 'ptr_t', 'size_t', 'code', 'codes'
])

# Canonical OS terms that should receive score boosting to prevent high-DF penalties
CANONICAL_OS_TERMS = {
    "race condition", "critical section", "mutual exclusion", "page fault",
    "demand paging", "virtual memory", "seek time", "inode", "compare and swap",
    "test and set", "safe state", "resource allocation graph", "dining philosophers",
    "working set", "busy waiting", "priority inversion", "reader writer", "spin lock",
    "address space", "page table", "tlb", "copy on write", "buddy system", "slab allocation",
    "process synchronization", "cpu scheduling", "deadlock", "main memory", "mass storage",
    "file system", "i/o system", "protection", "security", "virtual machine"
}

def clean_page_text(text, chapter_num, chapter_title_clean=""):
    """Strips running headers, footers, page numbers, captions, and structural code remnants."""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        # Strip pure page numbers
        if line_strip.isdigit():
            continue
        # Strip running headers with chapter title
        if chapter_title_clean and chapter_title_clean.lower() in line_strip.lower():
            continue
        # Standard chapter header matches
        if f"chapter {chapter_num}" in line_strip.lower():
            continue
        if re.search(r'^\s*c\s*h\s*a\s*p\s*t\s*e\s*r\s*' + str(chapter_num) + r'\b', line_strip, re.IGNORECASE):
            continue
        # Strip captions (Figure 5.1, Table 6.2, etc.)
        if re.search(r'^\s*(?:Figure|Table|Source|Chart|Caption)\s+\d+', line_strip, re.IGNORECASE):
            continue
        # Strip code-like structural boundaries
        if line_strip in ['{', '}', '};', '{};', '/*', '*/', 'do {', '} while']:
            continue
        # Skip common pointer trace lines or code assignments (e.g. counter = counter + 1;)
        if '=' in line_strip and (';' in line_strip or '++' in line_strip or '--' in line_strip):
            continue
        # Skip lines containing trailing code semicolon patterns
        if re.search(r';\s*$', line_strip) and any(kw in line_strip for kw in ['int', 'void', 'char', 'float', 'double', 'struct', 'ptr', 'shm']):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def extract_clean_text_from_page(page, chapter_num, chapter_title_clean=""):
    """Extracts page text, dynamically ignoring code blocks in monospace fonts."""
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
        return clean_page_text(page.get_text("text"), chapter_num, chapter_title_clean)
        
    raw_page_text = "\n".join(blocks_text)
    return clean_page_text(raw_page_text, chapter_num, chapter_title_clean)

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

def get_ngrams(words, n, min_word_len=3):
    """Generate n-grams skipping those starting or ending with stopwords, and normalizes plurals."""
    ngrams = []
    for i in range(len(words) - n + 1):
        gram = words[i:i+n]
        if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
            continue
        if any(len(w) < min_word_len or w.isdigit() for w in gram):
            continue
        if n == 1 and gram[0] in GENERIC_UNIGRAM_STOPWORDS:
            continue
        phrase = " ".join(gram)
        ngrams.append(normalize_phrase(phrase))
    return ngrams

def detect_chapter_outline_sections(toc, chapter_number):
    """Search the outline list for sub-sections belonging to the requested chapter."""
    chapter_idx = None
    start_level = None
    
    chapter_patterns = [
        rf'\b(?:Chapter|CHAPTER|Unit|Part|Section)\s+0*{chapter_number}\b',
        rf'^\s*0*{chapter_number}(?:\.|\b)'
    ]
    
    for idx, (level, title, page) in enumerate(toc):
        for pattern in chapter_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                chapter_idx = idx
                start_level = level
                break
        if chapter_idx is not None:
            break
            
    if chapter_idx is None:
        return []

    sections = []
    for idx in range(chapter_idx + 1, len(toc)):
        level, title, page = toc[idx]
        if level <= start_level:
            break
        if level == start_level + 1:
            sections.append({
                "label": title.strip(),
                "page": page
            })
            
    return sections

def get_sections_by_text_scan(doc, chapter_number):
    """Fallback method: scan page text for numbered headings like '5.1 Background'."""
    header_pattern = re.compile(rf'^\s*({chapter_number}\.\d+)(?:\s+|\s*\n\s*)([A-Z][^\n]+)', re.MULTILINE)
    sections = []
    max_section_suffix = -1
    
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text("text")
        stop_scanning = False
        for match in header_pattern.finditer(text):
            num_str = match.group(1).strip()
            label = clean_text(match.group(2))
            
            try:
                suffix = int(num_str.split(".")[1])
            except (IndexError, ValueError):
                continue
            
            label = re.split(r'\.|\(|,', label)[0].strip()
            
            if 3 < len(label) < 60:
                if any(s["label"].startswith(num_str + " ") for s in sections):
                    continue

                if suffix <= max_section_suffix:
                    break
                
                if not any(s["label"] == label for s in sections):
                    sections.append({
                        "label": f"{num_str} {label}",
                        "page": page_idx + 1
                    })
                    max_section_suffix = suffix
                    
                    if "summary" in label.lower():
                        stop_scanning = True
        
        if stop_scanning:
            break
            
    return sections

def get_chapter_title_from_toc(toc, chapter_number):
    chapter_patterns = [
        rf'\b(?:Chapter|CHAPTER|Unit|Part|Section)\s+0*{chapter_number}\b',
        rf'^\s*0*{chapter_number}(?:\.|\b)'
    ]
    for level, title, page in toc:
        for pattern in chapter_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                # Clean up title: e.g. "Chapter 5 Process Synchronization" -> "Process Synchronization"
                clean = re.sub(rf'\b(?:Chapter|CHAPTER|Unit|Part|Section)\s+0*{chapter_number}\b', '', title, flags=re.IGNORECASE)
                clean = re.sub(r'^\s*[0-9.\-\s]+', '', clean)
                return clean.strip()
    return ""

def parse_pdf_into_sections(pdf_path, chapter_number):
    """Chunks PDF text by section boundaries without page overlaps, and strips trailing non-expository zones."""
    print(f"\n--- [PHASE 1] Slicing & Boundary Partitioning ---")
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    total_pages = len(doc)
    
    chapter_title_clean = get_chapter_title_from_toc(toc, chapter_number) if toc else ""
    print(f"Cleaned Chapter Title for header filtering: '{chapter_title_clean}'")
    
    # 1. Identify outline nodes
    raw_outlines = []
    if toc:
        # Search for chapter index
        chapter_idx = None
        start_level = None
        chapter_patterns = [
            rf'\b(?:Chapter|CHAPTER|Unit|Part|Section)\s+0*{chapter_number}\b',
            rf'^\s*0*{chapter_number}(?:\.|\b)'
        ]
        for idx, (level, title, page) in enumerate(toc):
            for pattern in chapter_patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    chapter_idx = idx
                    start_level = level
                    break
            if chapter_idx is not None:
                break
                
        if chapter_idx is not None:
            for idx in range(chapter_idx + 1, len(toc)):
                level, title, page = toc[idx]
                if level <= start_level:
                    break
                if level == start_level + 1:
                    raw_outlines.append({
                        "label": title.strip(),
                        "page": page
                    })
                    
    if not raw_outlines:
        print("TOC Outline not found inside PDF metadata. Falling back to text scan regex parser...")
        raw_outlines = get_sections_by_text_scan(doc, chapter_number)
        
    if not raw_outlines:
        raw_outlines = [{"label": "Overview", "page": 1}]
        
    # 2. Separate valid expository sections from terminal (Summary/Exercises/Bibliography) sections
    valid_sections = []
    terminal_pages = []
    
    terminal_keywords = ["summary", "exercises", "problems", "bibliography", "references", "project", "study guide"]
    
    for item in raw_outlines:
        label_lower = item["label"].lower().strip()
        # Clean section numbers: e.g. "5.11 Summary" -> "summary"
        label_clean = re.sub(r'^\d+[\d.]*\s+', '', label_lower)
        
        is_terminal = False
        for kw in terminal_keywords:
            if kw == "summary" and "summary" in label_clean:
                is_terminal = True
                break
            if kw in ["exercises", "problems"] and (label_clean == kw or label_clean.startswith(kw) or "practice exercises" in label_clean or "practice problems" in label_clean):
                is_terminal = True
                break
            if kw in ["bibliography", "references"] and ("bibliography" in label_clean or "references" in label_clean):
                is_terminal = True
                break
            if kw in ["project", "study guide"] and kw in label_clean:
                is_terminal = True
                break
                
        if is_terminal:
            terminal_pages.append(item["page"])
        else:
            valid_sections.append(item)
            
    if not valid_sections:
        # Fallback: if all sections matched terminal keywords, keep them to avoid empty sets
        valid_sections = raw_outlines
        terminal_pages = []
        
    valid_sections.sort(key=lambda x: x["page"])
    first_terminal_page = min(terminal_pages) if terminal_pages else (total_pages + 1)
    
    print(f"Detected outlines/sections for Chapter {chapter_number}:")
    for s in valid_sections:
        print(f"  - Heading: '{s['label']}' starting on relative PDF Page {s['page']}")
    if terminal_pages:
        print(f"  - Excluded terminal sections starting at relative PDF Page {first_terminal_page}")
        
    sections = []
    for i in range(len(valid_sections)):
        current = valid_sections[i]
        start_page = current["page"]
        
        if i + 1 < len(valid_sections):
            end_page = valid_sections[i + 1]["page"]
            if end_page > start_page:
                adjusted_end = end_page - 1
            else:
                adjusted_end = end_page
        else:
            # Last valid section ends right before the first terminal section or at the end of PDF
            adjusted_end = min(total_pages, first_terminal_page - 1)
            
        pages_data = []
        raw_text = ""
        for p in range(start_page - 1, adjusted_end):
            # Extract clean text using monospace span detection
            p_clean = extract_clean_text_from_page(doc[p], chapter_number, chapter_title_clean)
            pages_data.append((p + 1, p_clean))
            raw_text += p_clean + "\n"
            
        print(f"  - Compiled Section '{current['label']}' -> mapping to PDF Pages {start_page} to {adjusted_end}")
        sections.append({
            "label": current["label"],
            "raw_text": raw_text,
            "page_start": start_page,
            "pages_data": pages_data
        })

    doc.close()
    return sections

def calculate_tfidf_concepts(sections, max_candidates=8, min_word_len=3, use_unigrams=True, use_bigrams=True, use_trigrams=True, apply_overlap_pruning=True):
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
            candidates += get_ngrams(words, 1, min_word_len)
        if use_bigrams:
            candidates += get_ngrams(words, 2, min_word_len)
        if use_trigrams:
            candidates += get_ngrams(words, 3, min_word_len)
        
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
            if term in CANONICAL_OS_TERMS:
                boost = 3.0
            else:
                for canonical in CANONICAL_OS_TERMS:
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
                    # If already selected s is a substring of new term (e.g. s='critical', term='critical section')
                    if s in term and len(s) < len(term):
                        selected[idx] = term
                        replaced = True
                        break
                    # If new term is a substring of already selected s (e.g. term='critical', s='critical section')
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

def filter_terms_via_ai(candidates, chapter_num):
    """
    Uses Gemini API to validate CS/OS terms and filter out grammar fragments, proper nouns, 
    figure names, code variables, and generic non-technical verbs.
    Returns a list of verified terms. Falls back to original candidates list on failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Skipping AI verification pass.")
        return candidates

    try:
        genai.configure(api_key=api_key)
        model_name = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""You are an expert Computer Science and Operating Systems textbook editor.
We have extracted a list of key term candidates from Chapter {chapter_num} of an Operating Systems textbook.
Some of these terms are noisy, code remnants, fragments, or too generic.

Review the following candidate list:
{json.dumps(candidates, indent=2)}

Filter this list to keep ONLY valid Computer Science, Operating Systems, or textbook-relevant core technical concepts.
Specifically:
- REMOVE: code variable names (e.g. 'register1', 'register2', 'ptr_t', 'int', 'void', code identifiers/traces)
- REMOVE: generic common words/verbs that are not technical terms (e.g. 'typical', 'general', 'enters', 'execution', 'exit', 'remaining', 'solution', 'problem', 'need', 'must', 'various')
- REMOVE: proper nouns that aren't core concepts (e.g. names of authors, places)
- REMOVE: figure names, page or table captions (e.g. 'figure', 'table')
- REMOVE: grammatical fragments, incomplete phrases, or punctuation artifacts (e.g. 'will', 'with', 'from', 'etc')
- KEEP: actual technical concepts, data structures, algorithms, hardware components, or formal CS methods (e.g. 'process synchronization', 'mutex lock', 'critical section', 'deadlock', 'semaphores', 'demand paging', 'page fault', 'context switch')

Return your response strictly in JSON format as an object with the key "verified_terms" containing a list of strings:
{{
  "verified_terms": [
    "verified term 1",
    "verified term 2"
  ]
}}
"""
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Parse the JSON response
        data = json.loads(response.text)
        verified = data.get("verified_terms", [])
        # Lowercase and strip for consistency
        verified_clean = {t.strip().lower() for t in verified if isinstance(t, str)}
        
        # Keep only elements that are actually in the original candidates list (preventing hallucinations)
        final_verified = []
        for c in candidates:
            c_clean = c.lower().strip()
            # Retain if verified by AI OR if it's a known canonical OS term
            if c_clean in verified_clean or c_clean in CANONICAL_OS_TERMS:
                final_verified.append(c)
                
        print(f"AI Filtering: Input {len(candidates)} candidates -> Output {len(final_verified)} verified concepts.")
        return final_verified
    except Exception as e:
        print(f"Warning: Gemini API call failed with error: {e}. Falling back to unverified list.")
        return candidates

class TraceLogger:
    def __init__(self, log_path="extraction_trace.log"):
        self.log_path = log_path
        self.log_file = None
        self.original_stdout = sys.stdout

    def start(self):
        # Open in write mode to clear previous logs
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self.log_file.write("=== Extraction Pipeline Trace ===\n\n")
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
        print("Usage: python extract_concepts.py <pdf_path> <chapter_number> [output_json]")
        sys.exit(1)
        
    pdf = sys.argv[1]
    chapter_num = int(sys.argv[2])
    output_path = sys.argv[3] if len(sys.argv) > 3 else "extracted_concepts.json"

    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)

    # Initialize Trace Logger
    logger = TraceLogger("extraction_trace.log")
    logger.console_print(f"Extracting key terms from PDF: {pdf}, Chapter {chapter_num}")
    
    # Start stdout redirection for trace logging
    logger.start()
    
    # 1. Segment text
    logger.console_print("Phase 1: Segmenting textbook outline and slicing pages cleanly...")
    sections = parse_pdf_into_sections(pdf, chapter_num)
    if not sections:
        logger.stop()
        logger.console_print("Error: Could not extract section outline.")
        sys.exit(1)
        
    # 2. Local Candidate Extraction (High-recall TF-IDF)
    logger.console_print("Phase 2: Calculating local smoothed TF-IDF candidate n-grams (up to 8 per section)...")
    section_candidates = calculate_tfidf_concepts(sections)
    
    # Deduplicate and consolidate globally
    logger.console_print("Phase 3: Consolidating and deduplicating unique key terms list...")
    all_terms = set()
    for label, candidates in section_candidates.items():
        for term in candidates:
            all_terms.add(term.strip().lower())
            
    # Post-processing Canonical verification pass
    raw_chapter_text_lower = " ".join([sec["raw_text"].lower() for sec in sections])
    boosted_additions = []
    for canonical in CANONICAL_OS_TERMS:
        if canonical not in all_terms:
            matches = len(re.findall(r'\b' + re.escape(canonical) + r'\b', raw_chapter_text_lower))
            if matches >= 5:
                boosted_additions.append(canonical)
                
    if boosted_additions:
        all_terms.update(boosted_additions)
        logger.console_print(f"Post-Processing Pass: Recovered {len(boosted_additions)} canonical terms (occurrences >= 5): {boosted_additions}")
        
    sorted_unique_terms = sorted(list(all_terms))
    
    # Phase 4: AI Semantic Verification Filter
    logger.console_print("Phase 4: Running Gemini AI Semantic Verification Filter...")
    verified_terms = filter_terms_via_ai(sorted_unique_terms, chapter_num)
    verified_set = set(verified_terms)
    
    # Back-propagate verification to sections
    filtered_section_candidates = {}
    for label, candidates in section_candidates.items():
        filtered_section = [c for c in candidates if c.strip().lower() in verified_set]
        filtered_section_candidates[label] = filtered_section
        
    # Stop redirection
    logger.stop()
    
    # Write to final JSON
    output_data = {
        "chapter": chapter_num,
        "sections": filtered_section_candidates,
        "unique_key_terms": sorted(list(verified_set))
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    logger.console_print(f"\nSuccessfully wrote {len(verified_set)} unique key terms to {output_path}!")
    logger.console_print(f"Detailed step-by-step data transformation trace saved to: extraction_trace.log")

if __name__ == "__main__":
    main()
