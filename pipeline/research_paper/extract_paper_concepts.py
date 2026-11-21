import json
import math
import os
import re
import sys
import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from _bootstrap import *  # noqa: F403, F401
except ImportError:
    from pipeline.research_paper._bootstrap import *  # noqa: F403, F401

from pipeline.utils import parse_json_robust, call_gemini_with_retry, get_gemini_model, clean_text
from pipeline.research_paper.pdf_utils import parse_toc
from pipeline.research_paper.tex_utils import extract_tex_sections, get_tex_title
from pipeline.prompts import load_prompt
from pipeline.schemas import ConceptMetadataOutput

# Generic English stop words
STOPWORDS = set(
    [
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "arent",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "cant",
        "cannot",
        "could",
        "couldnt",
        "did",
        "didnt",
        "do",
        "does",
        "doesnt",
        "doing",
        "dont",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadnt",
        "has",
        "hasnt",
        "have",
        "havent",
        "having",
        "he",
        "hed",
        "hell",
        "hes",
        "her",
        "here",
        "heres",
        "heres",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "hows",
        "i",
        "id",
        "ill",
        "im",
        "ive",
        "if",
        "in",
        "into",
        "is",
        "isnt",
        "it",
        "its",
        "itself",
        "lets",
        "me",
        "more",
        "most",
        "mustnt",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shant",
        "she",
        "shed",
        "shell",
        "shes",
        "should",
        "shouldnt",
        "so",
        "some",
        "such",
        "than",
        "that",
        "thats",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "theres",
        "these",
        "they",
        "theyd",
        "theyll",
        "theyre",
        "theyve",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasnt",
        "we",
        "wed",
        "well",
        "were",
        "weve",
        "werent",
        "what",
        "whats",
        "when",
        "whens",
        "where",
        "wheres",
        "which",
        "while",
        "who",
        "whos",
        "whom",
        "why",
        "whys",
        "with",
        "wont",
        "would",
        "wouldnt",
        "you",
        "youd",
        "youll",
        "youre",
        "youve",
        "your",
        "yours",
        "yourself",
        "yourselves",
    ]
)

# Words that should not be extracted as single-word key terms (unigrams)
GENERIC_UNIGRAM_STOPWORDS = set(
    [
        "use",
        "using",
        "used",
        "user",
        "users",
        "run",
        "running",
        "runs",
        "set",
        "sets",
        "system",
        "systems",
        "chapter",
        "section",
        "figure",
        "table",
        "example",
        "examples",
        "problem",
        "problems",
        "solution",
        "solutions",
        "process",
        "processes",
        "thread",
        "threads",
        "program",
        "programs",
        "page",
        "pages",
        "number",
        "numbers",
        "one",
        "two",
        "three",
        "new",
        "old",
        "time",
        "times",
        "also",
        "many",
        "must",
        "can",
        "may",
        "should",
        "would",
        "could",
        "like",
        "show",
        "shown",
        "shows",
        "each",
        "every",
        "other",
        "another",
        "called",
        "known",
        "first",
        "second",
        "third",
        "well",
        "need",
        "needs",
        "needed",
        "give",
        "given",
        "gives",
        "case",
        "cases",
        "way",
        "ways",
        "point",
        "points",
        "line",
        "lines",
        "part",
        "parts",
        "value",
        "values",
        "data",
        "information",
        "type",
        "types",
        "result",
        "results",
        "following",
        "illustrate",
        "illustrated",
        "describes",
        "described",
        "discussed",
        "discussion",
        "consider",
        "considering",
        "machine",
        "machines",
        "various",
        "several",
        "simple",
        "complex",
        "general",
        "specific",
        "particular",
        "both",
        "either",
        "neither",
        "whether",
        "however",
        "therefore",
        "thus",
        "hence",
        "since",
        "because",
        "although",
        "though",
        "even",
        "still",
        "yet",
        "next",
        "previous",
        "last",
        "high",
        "low",
        "large",
        "small",
        "long",
        "short",
        "fast",
        "slow",
        "method",
        "methods",
        "step",
        "steps",
        "action",
        "actions",
        "proposed",
        "proposed method",
        "proposed algorithm",
        "paper",
        "article",
        "experimental",
        "simulated",
        "authors",
        "citations",
        "citation",
        "le",
        "sun",
        "etc",
        "et",
        "al",
        "et al",
    ]
)

# Words that cannot end a technical concept phrase (adverbs, verbs, action tokens)
INVALID_PHRASE_ENDINGS = set(
    [
        "slightly",
        "highly",
        "significantly",
        "greatly",
        "partially",
        "currently",
        "recently",
        "substantially",
        "nearly",
        "approximately",
        "widely",
        "directly",
        "indirectly",
        "strongly",
        "weakly",
        "easily",
        "hardly",
        "fully",
        "partly",
        "mainly",
        "mostly",
        "primarily",
        "specifically",
        "generating",
        "generates",
        "generated",
        "manages",
        "managed",
        "managing",
        "reduces",
        "reduced",
        "reducing",
        "showing",
        "shows",
        "shown",
        "describing",
        "describes",
        "described",
        "containing",
        "contains",
        "contained",
        "providing",
        "provides",
        "provided",
        "using",
        "uses",
        "used",
        "performing",
        "performs",
        "performed",
        "obtaining",
        "obtains",
        "obtained",
        "increasing",
        "increases",
        "increased",
        "decreasing",
        "decreases",
        "decreased",
        "applying",
        "applies",
        "applied",
        "appears",
        "appeared",
        "appearing",
        "occurs",
        "occurred",
        "occurring",
        "constrained",
        "defined",
        "computed",
        "evaluates",
        "evaluated",
        "becomes",
        "remains",
        "equals",
        "relevant",
        "available",
        "suitable",
        "similar",
        "equal",
        "vanilla",
    ]
)

# Conversational, numeric, and descriptive filler words to filter out
FILLER_WORDS = set(
    [
        "basic",
        "better",
        "worse",
        "good",
        "bad",
        "adds",
        "adding",
        "added",
        "gives",
        "giving",
        "given",
        "takes",
        "taking",
        "taken",
        "open",
        "real",
        "found",
        "setting",
        "function",
        "test",
        "using",
        "used",
        "previous",
        "next",
        "google",
        "shows",
        "shown",
        "various",
        "several",
        "simple",
        "complex",
        "general",
        "specific",
        "particular",
        "concepts",
        "concept",
        "idea",
        "ideas",
        "approach",
        "approaches",
        "method",
        "methods",
        "result",
        "results",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "10",
        "20",
        "30",
        "1",
        "2",
        "3",
        "4",
        "5",
        "first",
        "second",
        "third",
        "last",
        "high",
        "low",
    ]
)

# Non-essential modifier prefixes to strip or filter
FILLER_PREFIXES = set(
    [
        "corresponding",
        "respective",
        "particular",
        "specific",
        "different",
        "various",
        "given",
        "described",
        "proposed",
        "selected",
        "overall",
        "total",
        "average",
    ]
)


def extract_paper_metadata_via_ai(text_snippet, pdf_metadata_title=None):
    """
    Queries Gemini to extract the official title and core canonical domain terms/acronyms
    from the paper text.
    """
    model, api_key = get_gemini_model()
    if not model:
        title = (
            pdf_metadata_title
            if (pdf_metadata_title and len(pdf_metadata_title.strip()) > 3)
            else "Research Paper"
        )
        return title, set()
    try:
        active_prompt = load_prompt("metadata_extraction_v1.txt", text_snippet=text_snippet)
        validated_metadata = None
        max_repair_attempts = 1

        for attempt in range(max_repair_attempts + 1):
            response = call_gemini_with_retry(
                model, active_prompt, generation_config={"response_mime_type": "application/json"}
            )
            raw_dict = parse_json_robust(response.text)
            try:
                validated_metadata = ConceptMetadataOutput.model_validate(raw_dict)
                break  # Successful schema validation
            except Exception as val_err:
                if attempt < max_repair_attempts:
                    active_prompt = (
                        f"Your previous JSON output failed validation: {val_err}.\n"
                        f"Ensure strictly valid JSON containing 'title' (string) and 'canonical_seeds' (list of strings).\n"
                        f"Paper text:\n{text_snippet}"
                    )
                else:
                    # Final fallback: use raw dict if available
                    if isinstance(raw_dict, dict):
                        validated_metadata = ConceptMetadataOutput(
                            title=raw_dict.get("title") or "Research Paper",
                            canonical_seeds=raw_dict.get("canonical_seeds") or [],
                        )

        title = validated_metadata.title.strip() if validated_metadata else ""
        if not title and pdf_metadata_title:
            title = pdf_metadata_title
        if not title:
            title = "Research Paper"

        seed_list = validated_metadata.canonical_seeds if validated_metadata else []
        seeds = {
            clean_text(s.strip().lower()) for s in seed_list if isinstance(s, str) and s.strip()
        }

        # Also try to extract keywords via regex from text as a backup/supplement
        kw_match = re.search(
            r"(?:Keywords|Key\s*words|Index\s*terms)[:\s]+([^\n.]+)", text_snippet, re.IGNORECASE
        )
        if kw_match:
            regex_kws = [
                clean_text(k.strip().lower())
                for k in re.split(r"[,;.]", kw_match.group(1))
                if k.strip()
            ]
            seeds.update(regex_kws)

        return title, seeds
    except Exception as e:
        print(f"Warning: Metadata extraction failed: {e}. Falling back to default values.")
        title = (
            pdf_metadata_title
            if (pdf_metadata_title and len(pdf_metadata_title.strip()) > 3)
            else "Research Paper"
        )
        return title, set()


def clean_page_text(text, title_clean=""):
    """Strips academic journal boilerplates, margins, emails, math formulas, and citation keys."""
    lines = text.split("\n")
    cleaned_lines = []

    # MDPI/academic boilerplate indicators
    boilerplate_patterns = [
        r"entropy\s+\d{4}",
        r"doi\.org",
        r"distributed\s+under\s+the\s+terms",
        r"creativecommons\.org",
        r"citation:",
        r"academic\s+editors",
        r"received:",
        r"revised:",
        r"accepted:",
        r"published:",
        r"copyright:",
        r"college\s+of\s+science",
        r"university",
        r"correspondence:",
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
        if "@" in line_strip and (
            ".edu" in line_strip or ".com" in line_strip or ".org" in line_strip
        ):
            continue

        # Remove parenthesized phrases and bracketed citations to avoid compound nouns interruption
        line_strip = re.sub(r"\([^)]*\)", " ", line_strip)
        line_strip = re.sub(r"\[[^\]]*\]", " ", line_strip)

        # Remove Dirac ket notation from the line
        line_strip = re.sub(r"\|[^>⟩]+[>⟩]", " ", line_strip)

        # Remove LaTeX/math symbols
        line_strip = re.sub(r"[\$\\#_\^\{\}]", " ", line_strip)

        # Skip lines that are mostly equations (e.g. contain '=', '+', '-', etc.)
        if line_strip.count("=") >= 1 and any(
            c in line_strip for c in ["+", "-", "*", "/", "⟩", "|", "cos", "sin"]
        ):
            continue

        cleaned_lines.append(line_strip)

    return "\n".join(cleaned_lines)


def extract_clean_text_from_page(page, title_clean=""):
    """Extracts page text, dynamically ignoring code/equation blocks in monospace fonts."""
    blocks_text = []
    try:
        layout = page.get_text("dict")
        for block in layout.get("blocks", []):
            if block.get("type") != 0:  # Skip images or drawings
                continue
            block_lines = []
            for line in block.get("lines", []):
                line_spans = []
                is_code_line = False
                for span in line.get("spans", []):
                    font_name = span.get("font", "").lower()
                    # Monospace font indicators
                    if any(
                        m in font_name
                        for m in [
                            "courier",
                            "mono",
                            "consolas",
                            "lucida",
                            "crd",
                            "tele",
                            "code",
                            "terminal",
                        ]
                    ):
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
    if word.endswith("ies"):
        return word[:-3] + "y"
    elif word.endswith("es"):
        if word.endswith("sses") or word.endswith("ses"):
            return word[:-2]
        return word[:-1]
    elif (
        word.endswith("s")
        and not word.endswith("ss")
        and not word.endswith("us")
        and not word.endswith("is")
    ):
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
        gram = words[i : i + n]
        if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
            continue
        if any(len(w) < min_word_len or w.isdigit() or re.search(r"\d", w) for w in gram):
            continue
        if n == 1 and gram[0] in GENERIC_UNIGRAM_STOPWORDS:
            # Let it pass if it's a known canonical seed
            if canonical_seeds and gram[0] in canonical_seeds:
                pass
            else:
                continue
        # Check for single-letter math variables that slipped through
        if any(len(w) == 1 and w not in ["a", "i"] for w in gram):
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

        print(
            f"  - Compiled Section '{heading}' -> mapping to PDF Pages {start_page} to {adjusted_end}"
        )
        sections.append(
            {
                "label": heading,
                "raw_text": raw_text,
                "page_start": start_page,
                "pages_data": pages_data,
            }
        )

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
    clauses = re.split(r"[,;:\.!\?\n]+", clean_raw)

    candidates = []
    global_pos = 0

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        words = re.findall(r"\b[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*\b", clause)
        num_words = len(words)

        for i in range(num_words):
            raw_word = words[i]
            word_lower = raw_word.lower()
            global_pos += 1

            # Single-word unigram rules:
            # High-Recall mode allows valid technical unigrams (e.g. gurobi, scip, miplib, heuristics, relaxations, embeddings)
            is_valid_unigram = (
                (raw_word.isupper() and len(raw_word) >= 2)
                or (canonical_seeds and word_lower in canonical_seeds)
                or (
                    high_recall_mode
                    and len(word_lower) >= 4
                    and word_lower not in STOPWORDS
                    and word_lower not in GENERIC_UNIGRAM_STOPWORDS
                    and word_lower not in FILLER_WORDS
                    and word_lower not in INVALID_PHRASE_ENDINGS
                )
            )

            if is_valid_unigram:
                candidates.append((word_lower, global_pos))

            if (
                word_lower in STOPWORDS
                or word_lower in GENERIC_UNIGRAM_STOPWORDS
                or word_lower in FILLER_WORDS
                or word_lower in INVALID_PHRASE_ENDINGS
                or len(word_lower) < 2
                or word_lower.isdigit()
            ):
                continue

            # Multi-word technical phrase (1 to 4 words MAX within the SAME clause)
            phrase_words = [word_lower]
            max_words_window = 4 if high_recall_mode else 3
            for j in range(i + 1, min(i + max_words_window, num_words)):
                next_word_lower = words[j].lower()
                if (
                    next_word_lower in STOPWORDS
                    or len(next_word_lower) < 2
                    or next_word_lower.isdigit()
                ):
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
                if (
                    first_word not in FILLER_WORDS
                    and first_word not in FILLER_PREFIXES
                    and last_word not in GENERIC_UNIGRAM_STOPWORDS
                    and last_word not in INVALID_PHRASE_ENDINGS
                    and last_word not in FILLER_WORDS
                ):
                    if (
                        len(last_word) <= 2
                        and not last_word.isupper()
                        and last_word not in ["lp", "ip", "ml", "ai", "nn"]
                    ):
                        continue
                    phrase_str = " ".join(phrase_words)
                    candidates.append((phrase_str, global_pos))

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
            if re.search(r"\b" + re.escape(term) + r"\b", raw_text, re.IGNORECASE):
                matches = re.findall(r"\b" + re.escape(term) + r"\b", raw_text)
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
                        if re.search(r"\b" + re.escape(canonical) + r"\b", term):
                            seed_boost = 2.2
                            break

            # Tri-Hybrid Score combining YAKE + TF-IDF + POS boosts
            scores[term] = (
                tf_val * pos_score * length_boost * casing_boost * tfidf_boost * seed_boost
            )

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
            print(
                f"  Candidate {idx + 1}: '{term}' (POS-YAKE Score: {scores[term]:.5f}, Count: {term_tf[term]})"
            )

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
    phrase_entries = extract_noun_phrase_candidates(
        full_paper_text, canonical_seeds, high_recall_mode=True
    )
    if not phrase_entries:
        return []

    term_tf = {}
    first_pos = {}

    for term, pos in phrase_entries:
        term_tf[term] = term_tf.get(term, 0) + 1
        if term not in first_pos:
            first_pos[term] = pos

    # Filter candidate terms: focus on terms appearing >= 2 times (or canonical seeds)
    # to avoid wasting thousands of operations on 1-occurrence noise strings.
    sorted_by_freq = sorted(term_tf.items(), key=lambda x: x[1], reverse=True)
    candidate_terms = [
        t for t, cnt in sorted_by_freq if cnt >= 2 or (canonical_seeds and t in canonical_seeds)
    ]
    if len(candidate_terms) < max_candidates:
        candidate_terms = [t for t, _ in sorted_by_freq[: max(max_candidates * 2, 200)]]

    all_headings_str = (title + " " + " ".join([sec["label"] for sec in sections])).lower()
    sec_texts_lower = [sec["raw_text"].lower() for sec in sections]

    # Fast O(1) vectorized casing and section spread checks
    casing_counts = {}
    section_spread = {}
    for term in candidate_terms:
        c_term = term.lower()
        title_term = term.title()
        casing_counts[term] = 1 if (title_term != term and title_term in full_paper_text) else 0
        section_spread[term] = sum(1 for st in sec_texts_lower if c_term in st)

    total_tokens = max(1, len(phrase_entries))
    scores = {}
    for term in candidate_terms:
        count = term_tf[term]
        words_in_term = term.split()
        word_len = len(words_in_term)

        tf_score = (1.0 + math.log(count)) / math.log(1.0 + total_tokens)
        pos_score = 1.0 / (1.0 + math.log(1.0 + first_pos[term]))
        length_boost = 1.0 + 0.35 * (word_len - 1)
        casing_boost = 1.0 + 0.5 * min(2, casing_counts.get(term, 0))
        dispersion_boost = 1.0 + 0.45 * math.log(1.0 + section_spread.get(term, 1))

        heading_boost = 1.0
        if re.search(r"\b" + re.escape(term) + r"\b", all_headings_str):
            heading_boost = 2.0

        seed_boost = 1.0
        if canonical_seeds:
            if term in canonical_seeds:
                seed_boost = 3.5
            else:
                for canonical in canonical_seeds:
                    if re.search(r"\b" + re.escape(canonical) + r"\b", term):
                        seed_boost = 2.2
                        break

        scores[term] = (
            tf_score
            * pos_score
            * length_boost
            * casing_boost
            * dispersion_boost
            * heading_boost
            * seed_boost
        )

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

    return selected


def filter_terms_offline(candidates, canonical_seeds=None, max_terms=None):
    """Deterministically filter and deduplicate candidates without an API call."""
    canonical_seeds = {str(term).strip().lower() for term in (canonical_seeds or set())}
    rejected_edges = STOPWORDS | {
        "based",
        "using",
        "via",
        "from",
        "with",
        "will",
        "can",
        "may",
        "also",
        "thereby",
        "making",
        "support",
        "supporting",
        "allowing",
        "resulted",
        "essential",
        "success",
        "full",
        "abstract",
        "paper",
        "study",
        "method",
    }
    accepted = []
    seen = set()
    for raw_term in candidates:
        term = re.sub(r"\s+", " ", str(raw_term).strip().lower())
        words = term.split()
        if not term or term in seen or len(words) > 4:
            continue
        if any(not re.search(r"[a-zA-Z]", word) for word in words):
            continue
        if words[0] in rejected_edges or words[-1] in rejected_edges:
            continue
        if len(words) == 1 and (len(words[0]) < 3 or words[0] in STOPWORDS):
            continue
        if re.fullmatch(r"[a-z]", term) or re.fullmatch(r"[a-z]\d+", term):
            continue
        if any(
            fragment in words for fragment in ("figure", "table", "section", "page", "et", "al")
        ):
            continue
        if term not in canonical_seeds and len(words) == 1 and term.islower() and len(term) < 5:
            continue
        seen.add(term)
        accepted.append(term)

    # Prefer the longest informative phrase over its shorter nested fragments.
    reduced = []
    for term in accepted:
        if any(
            term != other and term in other and len(other.split()) > len(term.split())
            for other in accepted
        ):
            continue
        reduced.append(term)
    if max_terms:
        reduced = reduced[:max_terms]
    print(
        f"Offline filtering: Input {len(candidates)} candidates -> Output {len(reduced)} concepts."
    )
    return reduced


def filter_terms_via_ai(candidates, title, canonical_seeds):
    """
    Uses Gemini API to validate scientific research paper terms, filtering out math variables,
    citations, boilerplates, common words, and grammar fragments.
    """
    model, api_key = get_gemini_model()
    if not model:
        print("Warning: GEMINI_API_KEY not set. Using deterministic offline filtering.")
        return filter_terms_offline(candidates, canonical_seeds)

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
            model, prompt, generation_config={"response_mime_type": "application/json"}
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

        print(
            f"AI Filtering: Input {len(candidates)} candidates -> Output {len(final_verified)} verified concepts."
        )
        return final_verified
    except Exception as e:
        print(
            f"Warning: Gemini API call failed with error: {e}. Falling back to offline filtering."
        )
        return filter_terms_offline(candidates, canonical_seeds)


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


def clean_sentence_definition(sentence):
    """Strips narrative preambles to convert raw paper sentences into clean context definitions."""
    s = re.sub(
        r"^(The (circuit|architecture|algorithm|model|system|framework) operates in [^:]+:\s*–?\s*|As (shown|discussed) in [^,]+,\s*|In this paper,\s*|We (propose|observe|find|introduce) (that\s*)?)",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    s = s.strip()
    if s:
        s = s[0].upper() + s[1:]
    return s


def extract_concept_context_sentences(sections, verified_terms):
    """
    Extracts the first occurrence sentence from paper text for each verified concept,
    serving as grounding context for AI synthesis or direct-text fallback.
    """
    context_map = {}
    full_text = "\n".join([sec.get("raw_text", "") for sec in sections])

    # Split text into sentences
    raw_sentences = re.split(r"(?<=[.!?])\s+", full_text)
    clean_sentences = []
    for s in raw_sentences:
        st = s.strip()
        if st and 25 <= len(st) <= 300:
            if not re.match(r"^(Figure|Table|Fig\.|Tab\.|\[\d+\])", st, re.IGNORECASE):
                clean_sentences.append(re.sub(r"\s+", " ", st))

    for term in verified_terms:
        term_clean = term.strip().lower()
        if not term_clean:
            continue
        pattern = re.compile(r"\b" + re.escape(term_clean) + r"\b", re.IGNORECASE)
        found_sentence = None
        for sentence in clean_sentences:
            if pattern.search(sentence):
                found_sentence = sentence
                break
        if found_sentence:
            clean_def = clean_sentence_definition(found_sentence)
            context_map[term_clean] = {
                "text": clean_def,
                "found_sentence": found_sentence,
            }

    return context_map


def format_fallback_definitions(verified_terms, raw_context_map):
    """Option B: Direct paper context sentence labeled as direct text."""
    fallback_map = {}
    for term in verified_terms:
        term_clean = term.strip().lower()
        ctx_info = raw_context_map.get(term_clean, {})
        clean_def = ctx_info.get("text")
        if clean_def:
            fallback_map[term_clean] = (
                f"{clean_def} [Role: Paper Context Extract] [Source: direct_text]"
            )
        else:
            fallback_map[term_clean] = (
                "Technical concept identified in paper text. [Role: Paper Context Extract] [Source: direct_text]"
            )
    return fallback_map


def generate_concept_definitions(sections, verified_terms, title, max_ai_definitions=None):
    """
    Generates definitions for verified concepts:
    - Option A: Synthesize crisp 1-2 sentence definition + operational paper role via Gemini
      using mined context sentences. Runs concurrently across batches for low latency.
    - Option B: If AI is unavailable or terms exceed max_ai_definitions, fall back cleanly
      to raw context sentence labeled as direct text.
    """
    raw_context_map = extract_concept_context_sentences(sections, verified_terms)

    model, api_key = get_gemini_model()
    if not model or not verified_terms:
        print(
            "Notice: AI model unavailable or no verified terms. Using Option B (Direct Paper Context)."
        )
        return format_fallback_definitions(verified_terms, raw_context_map)

    try:
        terms_list = sorted(list(verified_terms))

        # Priority Tiering: Synthesize AI definitions for up to max_ai_terms (default 35)
        # Long-tail concepts cleanly use Option B direct paper sentences.
        if max_ai_definitions is None:
            env_limit = os.environ.get("MAX_AI_DEFINITIONS")
            max_ai_terms = int(env_limit) if env_limit and env_limit.isdigit() else 35
        else:
            max_ai_terms = max_ai_definitions

        ai_candidates = terms_list[:max_ai_terms] if max_ai_terms > 0 else []
        batch_size = 20
        batches = [
            ai_candidates[i : i + batch_size] for i in range(0, len(ai_candidates), batch_size)
        ]
        final_definitions = {}

        def _process_definition_batch(batch_idx, batch):
            prompt_items = []
            for idx, term in enumerate(batch):
                term_lower = term.lower().strip()
                ctx = (
                    raw_context_map.get(term_lower, {}).get("found_sentence")
                    or "Mentioned in paper text."
                )
                prompt_items.append(f'{idx + 1}. Concept: "{term}"\n   Context: "{ctx}"')

            prompt_text = "\n\n".join(prompt_items)
            prompt = f"""You are an expert scientific dictionary editor and domain specialist.
The research paper is titled: "{title}".
Synthesize concise, high-fidelity formal definitions and operational roles for each concept based on its context in the paper.

{prompt_text}

Instructions:
1. "definition": Synthesize a clear, formal 1-2 sentence definition explaining what this concept is in the context of this paper. Do not simply repeat the raw context sentence verbatim.
2. "role": What specific operational role does this concept play in this paper (e.g., "Primary proposed architecture", "Loss function", "Baseline comparison", "Mathematical framework", "Evaluation metric", "Hardware gate")? Keep role under 6 words.

Return your response strictly in JSON format matching this schema:
{{
  "definitions": [
    {{
      "term": "concept name",
      "definition": "Synthesized 1-2 sentence definition.",
      "role": "Operational role in paper"
    }}
  ]
}}
"""
            batch_defs = {}
            try:
                response = call_gemini_with_retry(
                    model,
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                )
                data = parse_json_robust(response.text)
                defs_list = data.get("definitions", []) if isinstance(data, dict) else []
                for item in defs_list:
                    t = (item.get("term") or "").lower().strip()
                    d = (item.get("definition") or "").strip()
                    r = (item.get("role") or "").strip() or "Key concept in paper"
                    if t and d:
                        batch_defs[t] = f"{d} [Role: {r}] [Source: ai_generated]"
            except Exception as batch_err:
                print(
                    f"Warning: Batch {batch_idx + 1} AI definition synthesis failed ({batch_err}). Using Option B fallback."
                )
            return batch_defs

        if batches:
            max_workers = min(3, len(batches))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(_process_definition_batch, b_idx, b)
                    for b_idx, b in enumerate(batches)
                ]
                for f in as_completed(futures):
                    final_definitions.update(f.result())

        # Fill all remaining terms with Option B direct paper sentences
        for term in verified_terms:
            t_lower = term.lower().strip()
            if t_lower not in final_definitions:
                ctx_info = raw_context_map.get(t_lower, {})
                clean_def = ctx_info.get("text") or "Technical concept identified in paper text."
                final_definitions[t_lower] = (
                    f"{clean_def} [Role: Paper Context Extract] [Source: direct_text]"
                )

        ai_count = sum(1 for v in final_definitions.values() if "ai_generated" in v)
        direct_count = sum(1 for v in final_definitions.values() if "direct_text" in v)
        print(
            f"Synthesized definitions for {len(final_definitions)} concepts ({ai_count} AI synthesized, {direct_count} direct paper context)."
        )
        return final_definitions
        return final_definitions

    except Exception as e:
        print(
            f"Warning: AI definition synthesis failed ({e}). Falling back to Option B (Direct Paper Context)."
        )
        return format_fallback_definitions(verified_terms, raw_context_map)


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_paper_concepts.py <pdf_or_tex_path> <output_json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(input_path):
        print(f"Error: input file not found at: {input_path}")
        sys.exit(1)

    output_dir = os.path.dirname(output_path)
    log_path = (
        os.path.join(output_dir, "paper_extraction_trace.log")
        if output_dir
        else "paper_extraction_trace.log"
    )
    logger = TraceLogger(log_path)
    logger.console_print(f"Extracting key terms from: {input_path}")

    logger.start()

    # 1. Segment text
    logger.console_print("Phase 1: Segmenting paper sections and pruning references...")

    if input_path.lower().endswith(".tex"):
        # --------------------------------------------------------- .tex path
        logger.console_print("[.tex mode] Parsing LaTeX source for sections...")
        sections = extract_tex_sections(input_path)
        with open(input_path, encoding="utf-8", errors="replace") as _f:
            _raw = _f.read()
        metadata_title = get_tex_title(_raw)
    else:
        # --------------------------------------------------------- PDF path
        sections = parse_pdf_into_sections(input_path, "")
        doc = fitz.open(input_path)
        metadata_title = doc.metadata.get("title") if hasattr(doc, "metadata") else None
        doc.close()

    if not sections:
        logger.stop()
        logger.console_print("Error: Could not extract paper sections.")
        sys.exit(1)

    # 0. Extract Dynamic Metadata
    logger.console_print(
        "Phase 0: Extracting paper title and canonical seeds dynamically from all sections..."
    )
    intro_snippet = "\n".join([sec["raw_text"] for sec in sections[:2]])
    title, canonical_seeds = extract_paper_metadata_via_ai(intro_snippet, metadata_title)

    logger.console_print(f"  - Extracted Title: '{title}'")
    logger.console_print(
        f"  - Extracted Canonical Seeds ({len(canonical_seeds)}): {list(canonical_seeds)}"
    )

    # 2. Local Candidate Extraction & Global Full-Paper Scan
    logger.console_print(
        "Phase 2: Calculating Local (Per-Section) & Global (Full-Doc) Candidate Terms via POS-YAKE..."
    )
    section_candidates = calculate_pos_yake_concepts(sections, canonical_seeds)

    full_paper_text = "\n".join([sec["raw_text"] for sec in sections])
    global_doc_candidates = extract_global_doc_concepts(
        sections, title, canonical_seeds, max_candidates=75
    )
    logger.console_print(f"  - Extracted {len(global_doc_candidates)} Global Full-Paper Concepts.")

    # Deduplicate and consolidate globally
    logger.console_print(
        "Phase 3: Merging Local + Global concepts into consolidated unique key terms list..."
    )
    all_terms = set(global_doc_candidates)
    for label, candidates in section_candidates.items():
        for term in candidates:
            all_terms.add(term.strip().lower())

    # Post-processing Canonical verification pass
    raw_paper_text_lower = clean_text(full_paper_text.lower())
    boosted_additions = []
    if canonical_seeds:
        for canonical in canonical_seeds:
            if canonical not in all_terms:
                matches = len(
                    re.findall(r"\b" + re.escape(canonical) + r"\b", raw_paper_text_lower)
                )
                if matches >= 1:  # Lower frequency threshold for sparse terms in shorter papers
                    boosted_additions.append(canonical)

    if boosted_additions:
        all_terms.update(boosted_additions)
        logger.console_print(
            f"Post-Processing Pass: Recovered {len(boosted_additions)} canonical terms: {boosted_additions}"
        )

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

    logger.console_print("Phase 5: Synthesizing concept definitions and operational roles...")
    concept_definitions = generate_concept_definitions(sections, verified_set, title)

    logger.stop()

    output_data = {
        "paper_title": title,
        "sections": filtered_section_candidates,
        "global_document_concepts": [c for c in global_doc_candidates if c.lower() in verified_set],
        "unique_key_terms": sorted(list(verified_set)),
        "concept_definitions": concept_definitions,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    logger.console_print(
        f"\nSuccessfully wrote {len(verified_set)} unique key terms (Local + Global) to {output_path}!"
    )
    logger.console_print(f"Detailed step-by-step trace saved to: {log_path}")


if __name__ == "__main__":
    main()
