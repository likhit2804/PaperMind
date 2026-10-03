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

from pipeline.utils import parse_json_robust, call_gemini_with_retry, get_gemini_model, clean_text
from pipeline.research_paper.pdf_utils import parse_toc
from pipeline.research_paper.tex_utils import extract_tex_sections, get_tex_title

# Load environment variables
load_dotenv(override=True)

# Reconfigure standard output to handle unicode outputs in Windows
sys.stdout.reconfigure(encoding='utf-8')

def singularize_word(w):
    if not w or not isinstance(w, str):
        return w
    w_lower = w.lower()
    IRREGULAR_MAP = {
        'matrices': 'matrix', 'indices': 'index', 'axes': 'axis', 'analyses': 'analysis',
        'hypotheses': 'hypothesis', 'criteria': 'criterion', 'phenomena': 'phenomenon',
        'vertices': 'vertex', 'simplices': 'simplex'
    }
    EXCEPTIONS = {'process', 'status', 'basis', 'bias', 'loss', 'cross', 'glass', 'class', 'mass', 'pass', 'canvas', 'corpus', 'series', 'species', 'consensus', 'keras', 'graphics'}
    
    if w_lower in EXCEPTIONS or w_lower.endswith(('ss', 'us', 'is', 'as', 'os')):
        return w
    if w_lower in IRREGULAR_MAP:
        return IRREGULAR_MAP[w_lower]
    if '-' in w:
        parts = w.split('-')
        parts[-1] = singularize_word(parts[-1])
        return "-".join(parts)
    if len(w_lower) > 3:
        if w_lower.endswith('ies') and not w_lower.endswith('series'):
            return w[:-3] + 'y'
        elif w_lower.endswith('ses') or w_lower.endswith('xes') or w_lower.endswith('ches') or w_lower.endswith('shes'):
            return w[:-2]
        elif w_lower.endswith('s') and not w_lower.endswith('ss'):
            return w[:-1]
    return w

def singularize_term(term):
    """
    Normalizes a technical term or noun phrase from plural to singular form,
    including hyphenated modifiers (e.g. '68-points landmark' -> '68-point landmark').
    """
    if not term or not isinstance(term, str):
        return term
    
    term_str = term.strip()
    words = term_str.split()
    if not words:
        return term_str
    
    # Singularize the final noun and any hyphenated modifiers
    words[-1] = singularize_word(words[-1])
    for idx in range(len(words) - 1):
        if '-' in words[idx]:
            words[idx] = singularize_word(words[idx])
            
    return " ".join(words)

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

# Words that cannot end a technical concept phrase (adverbs, verbs, action tokens)
INVALID_PHRASE_ENDINGS = set([
    'slightly', 'highly', 'significantly', 'greatly', 'partially', 'currently', 'recently',
    'substantially', 'nearly', 'approximately', 'widely', 'directly', 'indirectly', 'strongly',
    'weakly', 'easily', 'hardly', 'fully', 'partly', 'mainly', 'mostly', 'primarily', 'specifically',
    'generating', 'generates', 'generated', 'manages', 'managed', 'managing', 'reduces', 'reduced',
    'reducing', 'showing', 'shows', 'shown', 'describing', 'describes', 'described', 'containing',
    'contains', 'contained', 'providing', 'provides', 'provided', 'using', 'uses', 'used',
    'performing', 'performs', 'performed', 'obtaining', 'obtains', 'obtained', 'increasing',
    'increases', 'increased', 'decreasing', 'decreases', 'decreased', 'applying', 'applies', 'applied',
    'appears', 'appeared', 'appearing', 'occurs', 'occurred', 'occurring', 'constrained', 'defined',
    'computed', 'evaluates', 'evaluated', 'becomes', 'remains', 'equals', 'relevant', 'available',
    'suitable', 'similar', 'equal', 'vanilla'
])

# Conversational, numeric, and descriptive filler words to filter out
FILLER_WORDS = set([
    'basic', 'better', 'worse', 'good', 'bad', 'adds', 'adding', 'added', 'gives', 'giving', 'given',
    'takes', 'taking', 'taken', 'open', 'real', 'found', 'setting', 'function', 'test', 'using', 'used',
    'previous', 'next', 'google', 'shows', 'shown', 'various', 'several', 'simple', 'complex', 'general',
    'specific', 'particular', 'concepts', 'concept', 'idea', 'ideas', 'approach', 'approaches', 'method',
    'methods', 'result', 'results', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    '10', '20', '30', '1', '2', '3', '4', '5', 'first', 'second', 'third', 'last', 'high', 'low'
])

# Non-essential modifier prefixes to strip or filter
FILLER_PREFIXES = set([
    'corresponding', 'respective', 'particular', 'specific', 'different', 'various',
    'given', 'described', 'proposed', 'selected', 'overall', 'total', 'average'
])

def extract_paper_metadata_via_ai(text_snippet, pdf_metadata_title=None):
    """
    Queries Gemini to extract the official title and core canonical domain terms/acronyms 
    from the paper text.
    """
    model, api_key = get_gemini_model()
    if not model:
        title = pdf_metadata_title if (pdf_metadata_title and len(pdf_metadata_title.strip()) > 3) else "Research Paper"
        return title, set()

    try:
        
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

# clean_text is imported from pipeline.utils — defined there to avoid duplication.

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
    
    valid_toc, first_terminal_page = parse_toc(doc)
    first_terminal_page = min(first_terminal_page, total_pages + 1)

    if not valid_toc:
        print("TOC Outline not found inside PDF metadata. Falling back to page-by-page scan...")
        # Fallback: chunk by page ranges
        for p in range(1, min(14, total_pages + 1)):
            valid_toc.append((1, f"Section Page {p}", p))
    
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

def extract_noun_phrase_candidates(text, canonical_seeds=None, high_recall_mode=True):
    """
    Stage 1: Syntactic POS / Noun Phrase Chunking
    Extracts 1-to-4 word technical concept phrases and valid domain unigrams/acronyms.
    Enforces clause/sentence boundaries (punctuation) so phrases never cross commas/clauses.
    High-Recall Mode casts a wide net to capture 99%+ of all technical terms for AI filtering.
    """
    clean_raw = clean_text(text)
    # Split by clause separators: punctuation (, ; : . ! ? \n)
    clauses = re.split(r'[,;:\.!\?\n]+', clean_raw)
    
    candidates = []
    global_pos = 0
    
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
            
        words = re.findall(r'\b[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*\b', clause)
        num_words = len(words)
        
        for i in range(num_words):
            raw_word = words[i]
            word_lower = raw_word.lower()
            global_pos += 1
            
            # Single-word unigram rules:
            # High-Recall mode allows valid technical unigrams (e.g. gurobi, scip, miplib, heuristics, relaxations, embeddings)
            is_valid_unigram = (
                (raw_word.isupper() and len(raw_word) >= 2) or
                (canonical_seeds and word_lower in canonical_seeds) or
                (high_recall_mode and len(word_lower) >= 4 and 
                 word_lower not in STOPWORDS and 
                 word_lower not in GENERIC_UNIGRAM_STOPWORDS and 
                 word_lower not in FILLER_WORDS and 
                 word_lower not in INVALID_PHRASE_ENDINGS)
            )
            
            if is_valid_unigram:
                candidates.append((singularize_term(word_lower), global_pos))
                
            if (word_lower in STOPWORDS or word_lower in GENERIC_UNIGRAM_STOPWORDS or 
                word_lower in FILLER_WORDS or word_lower in INVALID_PHRASE_ENDINGS or 
                len(word_lower) < 2):
                continue
                
            # Multi-word technical phrase (1 to 4 words MAX within the SAME clause)
            phrase_words = [word_lower]
            max_words_window = 4 if high_recall_mode else 3
            for j in range(i + 1, min(i + max_words_window, num_words)):
                next_word_lower = words[j].lower()
                if (next_word_lower in STOPWORDS or len(next_word_lower) < 2):
                    break
                phrase_words.append(next_word_lower)
                
                # Check for word duplication within phrase
                if len(phrase_words) >= 3 and phrase_words[-1] in phrase_words[:-1]:
                    continue
                    
                # Strip non-essential modifier prefix if present
                if phrase_words[0] in FILLER_PREFIXES and len(phrase_words) > 2:
                    phrase_words = phrase_words[1:]
                    
                first_word = phrase_words[0]
                last_word = phrase_words[-1]
                
                # Must NOT start or end with filler words or invalid ending tokens
                if (first_word not in FILLER_WORDS and first_word not in FILLER_PREFIXES and
                    last_word not in GENERIC_UNIGRAM_STOPWORDS and 
                    last_word not in INVALID_PHRASE_ENDINGS and 
                    last_word not in FILLER_WORDS):
                    if len(last_word) <= 2 and not last_word.isupper() and last_word not in ['lp', 'ip', 'ml', 'ai', 'nn']:
                        continue
                    phrase_str = " ".join(phrase_words)
                    candidates.append((singularize_term(phrase_str), global_pos))
                    
    return candidates

def calculate_pos_yake_concepts(sections, canonical_seeds, max_candidates=15):
    """
    Stage 2: Tri-Hybrid Concept Extraction (Syntactic POS Chunking + YAKE Graph Centrality + Section TF-IDF)
    Computes TF-IDF across paper sections to highlight section-distinctive technical concepts.
    """
    print(f"\n--- [PHASE 2] Local Candidate Generation (Tri-Hybrid POS + YAKE + TF-IDF) ---")
    
    num_sections = max(1, len(sections))
    
    # Pre-pass: Compute Document Frequency (DF) across sections for IDF calculation
    doc_freq = {}
    sec_entries = {}
    
    for sec in sections:
        label_key = sec["label"]
        raw_text = sec["raw_text"]
        if not raw_text.strip():
            continue
        entries = extract_noun_phrase_candidates(raw_text, canonical_seeds, high_recall_mode=True)
        sec_entries[label_key] = entries
        
        unique_terms_in_sec = {term for term, pos in entries}
        for term in unique_terms_in_sec:
            doc_freq[term] = doc_freq.get(term, 0) + 1
            
    section_concepts = {}
    
    for sec in sections:
        label_key = sec["label"]
        raw_text = sec["raw_text"]
        
        if label_key not in sec_entries or not sec_entries[label_key]:
            continue
            
        phrase_entries = sec_entries[label_key]
        
        term_tf = {}
        first_pos = {}
        casing_counts = {}
        
        for term, pos in phrase_entries:
            term_tf[term] = term_tf.get(term, 0) + 1
            if term not in first_pos:
                first_pos[term] = pos
            if re.search(r'\b' + re.escape(term) + r'(?:s|es)?\b', raw_text, re.IGNORECASE):
                matches = re.findall(r'\b' + re.escape(term) + r'(?:s|es)?\b', raw_text)
                title_cased = sum(1 for m in matches if m.istitle() or m.isupper())
                casing_counts[term] = title_cased
                
        total_tokens = max(1, len(phrase_entries))
        
        scores = {}
        for term, count in term_tf.items():
            words_in_term = term.split()
            word_len = len(words_in_term)
            
            tf_val = count / total_tokens
            df_val = doc_freq.get(term, 1)
            idf_val = math.log(1.0 + (num_sections / (1.0 + df_val)))
            tfidf_score = tf_val * idf_val
            
            pos_score = 1.0 / (1.0 + math.log(1.0 + first_pos[term]))
            length_boost = 1.0 + 0.35 * (word_len - 1)
            casing_boost = 1.0 + 0.5 * min(2, casing_counts.get(term, 0))
            tfidf_boost = 1.0 + 1.2 * tfidf_score
            
            seed_boost = 1.0
            if canonical_seeds:
                if term in canonical_seeds:
                    seed_boost = 3.5
                else:
                    for canonical in canonical_seeds:
                        if re.search(r'\b' + re.escape(canonical) + r'\b', term):
                            seed_boost = 2.2
                            break
                            
            # Tri-Hybrid Score combining YAKE + TF-IDF + POS boosts
            scores[term] = tf_val * pos_score * length_boost * casing_boost * tfidf_boost * seed_boost
            
        sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        selected = []
        for term, score in sorted_terms:
            if len(selected) >= max_candidates:
                break
            overlap_found = False
            replaced = False
            for idx, s in enumerate(selected):
                if s == term:
                    overlap_found = True
                    break
                if s in term and len(s) < len(term):
                    selected[idx] = term
                    replaced = True
                    break
                if term in s and len(term) < len(s):
                    overlap_found = True
                    break
                s_w = s.split()
                t_w = term.split()
                if len(s_w) >= 2 and len(t_w) >= 2 and s_w[-2:] == t_w[-2:]:
                    overlap_found = True
                    break
                    
            if not overlap_found and not replaced:
                selected.append(term)
                
        section_concepts[label_key] = selected
        print(f"Section '{label_key}' Candidates (Total Unique Candidates: {len(term_tf)}):")
        for idx, term in enumerate(selected[:5]):
            print(f"  Candidate {idx+1}: '{term}' (POS-YAKE Score: {scores[term]:.5f}, Count: {term_tf[term]})")
            
    return section_concepts

def extract_global_doc_concepts(sections, title="", canonical_seeds=None, max_candidates=150):
    """
    Extracts paper-wide global key concepts across all sections combined.
    Uses:
    1. Logarithmic Sub-linear TF Scaling
    2. Multi-Section Dispersion Boost
    3. Heading Consensus Boost
    4. High Recall Candidate Pool (Max 150 Candidates)
    """
    full_paper_text = "\n".join([sec["raw_text"] for sec in sections])
    phrase_entries = extract_noun_phrase_candidates(full_paper_text, canonical_seeds, high_recall_mode=True)
    if not phrase_entries:
        return []
        
    term_tf = {}
    first_pos = {}
    casing_counts = {}
    section_spread = {}
    
    all_headings_str = (title + " " + " ".join([sec["label"] for sec in sections])).lower()
    
    for term, pos in phrase_entries:
        term_tf[term] = term_tf.get(term, 0) + 1
        if term not in first_pos:
            first_pos[term] = pos
        if re.search(r'\b' + re.escape(term) + r'(?:s|es)?\b', full_paper_text, re.IGNORECASE):
            matches = re.findall(r'\b' + re.escape(term) + r'(?:s|es)?\b', full_paper_text)
            title_cased = sum(1 for m in matches if m.istitle() or m.isupper())
            casing_counts[term] = title_cased
            
    for term in term_tf:
        sec_count = 0
        for sec in sections:
            if re.search(r'\b' + re.escape(term) + r'(?:s|es)?\b', sec["raw_text"], re.IGNORECASE):
                sec_count += 1
        section_spread[term] = sec_count

    total_tokens = max(1, len(phrase_entries))
    scores = {}
    for term, count in term_tf.items():
        words_in_term = term.split()
        word_len = len(words_in_term)
        
        tf_score = (1.0 + math.log(count)) / math.log(1.0 + total_tokens)
        pos_score = 1.0 / (1.0 + math.log(1.0 + first_pos[term]))
        length_boost = 1.0 + 0.35 * (word_len - 1)
        casing_boost = 1.0 + 0.5 * min(2, casing_counts.get(term, 0))
        dispersion_boost = 1.0 + 0.45 * math.log(1.0 + section_spread.get(term, 1))
        
        heading_boost = 1.0
        if re.search(r'\b' + re.escape(term) + r'\b', all_headings_str):
            heading_boost = 2.0
            
        seed_boost = 1.0
        if canonical_seeds:
            if term in canonical_seeds:
                seed_boost = 3.5
            else:
                for canonical in canonical_seeds:
                    if re.search(r'\b' + re.escape(canonical) + r'\b', term):
                        seed_boost = 2.2
                        break
                        
        scores[term] = tf_score * pos_score * length_boost * casing_boost * dispersion_boost * heading_boost * seed_boost
        
    sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    selected = []
    for term, score in sorted_terms:
        if len(selected) >= max_candidates:
            break
        overlap_found = False
        replaced = False
        for idx, s in enumerate(selected):
            s_sing = singularize_term(s)
            t_sing = singularize_term(term)
            if s == term or s_sing == t_sing:
                overlap_found = True
                break
            if t_sing in s_sing and len(t_sing) < len(s_sing):
                overlap_found = True
                break
            s_w = s_sing.split()
            t_w = t_sing.split()
            if len(s_w) >= 2 and len(t_w) >= 2 and s_w[-2:] == t_w[-2:]:
                overlap_found = True
                break
                
        if not overlap_found and not replaced:
            selected.append(singularize_term(term))
            
    return selected

def filter_terms_via_ai(candidates, title, canonical_seeds):
    """
    Uses Gemini API to validate scientific research paper terms, filtering out math variables, 
    citations, boilerplates, common words, and grammar fragments.
    """
    model, api_key = get_gemini_model()
    if not model:
        print("Warning: GEMINI_API_KEY not set. Skipping AI verification pass.")
        return candidates

    try:
        
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
- CONVERT PLURALS TO SINGULAR: Normalize all terms to their singular form (e.g. 'facial expressions' -> 'facial expression', 'neural networks' -> 'neural network', 'models' -> 'model', 'heuristics' -> 'heuristic', 'algorithms' -> 'algorithm'). Never return both singular and plural versions of the same concept.
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
        # Lowercase, strip, and singularize for consistency
        verified_clean = {singularize_term(t.strip().lower()) for t in verified if isinstance(t, str)}
        
        # Keep only elements that are actually in the original candidates list (preventing hallucinations)
        final_verified = []
        for c in candidates:
            c_clean = singularize_term(c.lower().strip())
            # Retain if verified by AI OR if it's a known canonical seed
            if c_clean in verified_clean or (canonical_seeds and c_clean in canonical_seeds):
                if c_clean not in [singularize_term(v.lower().strip()) for v in final_verified]:
                    final_verified.append(c_clean)
                
        print(f"AI Filtering: Input {len(candidates)} candidates -> Output {len(final_verified)} verified concepts.")
        return final_verified
    except Exception as e:
        print(f"Warning: Gemini API call failed with error: {e}. Falling back to unverified list.")
        return candidates

class TraceLogger:
    def __init__(self, log_path="paper_extraction_trace.log"):
        self.log_path = log_path
        self.log_file = None

    def start(self):
        try:
            self.log_file = open(self.log_path, "w", encoding="utf-8")
            self.log_file.write("=== Research Paper Extraction Trace ===\n\n")
            self.log_file.flush()
        except Exception:
            pass

    def stop(self):
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass

    def console_print(self, message):
        print(message, flush=True)
        if self.log_file:
            try:
                self.log_file.write(message + "\n")
                self.log_file.flush()
            except Exception:
                pass

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_concepts.py <pdf_or_tex_path> <output_json>")
        sys.exit(1)

    input_path  = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(input_path):
        print(f"Error: input file not found at: {input_path}")
        sys.exit(1)

    output_dir = os.path.dirname(output_path)
    log_path   = os.path.join(output_dir, "paper_extraction_trace.log") if output_dir else "paper_extraction_trace.log"
    logger     = TraceLogger(log_path)
    logger.console_print(f"Extracting key terms from: {input_path}")

    logger.start()

    # 1. Segment text
    logger.console_print("Phase 1: Segmenting paper sections and pruning references...")

    if input_path.lower().endswith('.tex'):
        # --------------------------------------------------------- .tex path
        logger.console_print("[.tex mode] Parsing LaTeX source for sections...")
        sections = extract_tex_sections(input_path)
        with open(input_path, encoding='utf-8', errors='replace') as _f:
            _raw = _f.read()
        metadata_title = get_tex_title(_raw)
    else:
        # --------------------------------------------------------- PDF path
        sections = parse_pdf_into_sections(input_path, "")
        doc = fitz.open(input_path)
        metadata_title = doc.metadata.get("title") if hasattr(doc, 'metadata') else None
        doc.close()

    if not sections:
        logger.stop()
        logger.console_print("Error: Could not extract paper sections.")
        sys.exit(1)

    # 0. Extract Dynamic Metadata
    logger.console_print("Phase 0: Extracting paper title and canonical seeds dynamically from all sections...")
    intro_snippet = "\n".join([sec["raw_text"] for sec in sections[:2]])
    title, canonical_seeds = extract_paper_metadata_via_ai(intro_snippet, metadata_title)
    
    logger.console_print(f"  - Extracted Title: '{title}'")
    logger.console_print(f"  - Extracted Canonical Seeds ({len(canonical_seeds)}): {list(canonical_seeds)}")
    
    # 2. Local Candidate Extraction & Global Full-Paper Scan
    logger.console_print("Phase 2: Calculating Local (Per-Section) & Global (Full-Doc) Candidate Terms via POS-YAKE...")
    section_candidates = calculate_pos_yake_concepts(sections, canonical_seeds)
    
    full_paper_text = "\n".join([sec["raw_text"] for sec in sections])
    global_doc_candidates = extract_global_doc_concepts(sections, title, canonical_seeds, max_candidates=75)
    logger.console_print(f"  - Extracted {len(global_doc_candidates)} Global Full-Paper Concepts.")
    
    # Deduplicate and consolidate globally with singular normalization
    logger.console_print("Phase 3: Merging Local + Global concepts into consolidated unique key terms list...")
    all_terms = set(singularize_term(c.lower()) for c in global_doc_candidates)
    for label, candidates in section_candidates.items():
        for term in candidates:
            all_terms.add(singularize_term(term.strip().lower()))
            
    # Post-processing Canonical verification pass
    raw_paper_text_lower = clean_text(full_paper_text.lower())
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
    
    # Back-propagate verification to sections with singular normalization
    filtered_section_candidates = {}
    for label, candidates in section_candidates.items():
        filtered_section = []
        for c in candidates:
            sing_c = singularize_term(c.strip().lower())
            if sing_c in verified_set and sing_c not in filtered_section:
                filtered_section.append(sing_c)
        filtered_section_candidates[label] = filtered_section
        
    logger.stop()
    
    output_data = {
        "paper_title": title,
        "sections": filtered_section_candidates,
        "global_document_concepts": [c for c in global_doc_candidates if c.lower() in verified_set],
        "unique_key_terms": sorted(list(verified_set))
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    logger.console_print(f"\nSuccessfully wrote {len(verified_set)} unique key terms (Local + Global) to {output_path}!")
    logger.console_print(f"Detailed step-by-step trace saved to: {log_path}")

if __name__ == "__main__":
    main()
