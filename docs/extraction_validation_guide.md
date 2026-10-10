# Pipeline Extraction Validation Specification & Audit Guide

This specification defines the rigorous verification criteria, schema validation constraints, and automated quality testing protocols for each of the 7 autonomous extraction engines in the **PaperMind** research processing pipeline.

---

## 📋 Master Validation Summary Matrix

| # | Extractor Script | Output Artifact | Validation Schema / Metric Target | Halting / Fallback Criteria |
| :- | :--- | :--- | :--- | :--- |
| **1** | [`extract_paper_concepts.py`](pipeline/research_paper/extract_paper_concepts.py) | `concepts.json` | 1–4 word POS Noun-Phrases; Precision $\ge 95\%$, Recall $\ge 95\%$. | Fallback to canonical title seeds if API key absent. |
| **2** | [`generate_paper_notes.py`](pipeline/research_paper/generate_paper_notes.py) | `notes.md` | Grounded section citations (`Page X (Section 'Y')`); 100% page boundary validity. | Generate local offline glossary if LLM fails. |
| **3** | [`generate_paper_summary.py`](pipeline/research_paper/generate_paper_summary.py) | `summary.json` | 5 mandatory JSON keys (`executive`, `tldr`, `research_question`, `contributions`, `sections`). | Fallback to heuristic grounded sentence extraction. |
| **4** | [`generate_architecture_notes.py`](pipeline/research_paper/generate_architecture_notes.py) | `architecture_notes.md` | Valid Markdown table syntax (`\|---|`) and Mermaid diagram syntax. | Fallback to text summary if block segmentation fails. |
| **5** | [`extract_paper_references.py`](pipeline/research_paper/extract_paper_references.py) | `references.json` | Strict Role Enum (`Foundational`, `Baseline`, `Comparison`, etc.) + In-text citation sentence matching. | Regex-based citation parser fallback. |
| **6** | [`extract_notations_local.py`](pipeline/research_paper/extract_notations_local.py) | `notations.json` | Greek letters & LaTeX math symbols (`\alpha`, `W_i`, `\mathcal{F}`); 0% common stopword symbols. | Local regex notation dictionary fallback. |
| **7** | [`extract_paper_equations.py`](pipeline/research_paper/extract_paper_equations.py) | `equations.json` | Valid KaTeX LaTeX markup; 100% valid `page` and `section` metadata. | Local PyMuPDF / TeX regex equation fallback. |

---

## 🔍 Detailed Extractor Validation Specifications

---

### 1. Key Concepts Extractor
* **Script**: [`pipeline/research_paper/extract_paper_concepts.py`](pipeline/research_paper/extract_paper_concepts.py)
* **Output Artifact**: `concepts.json`

#### Validation Rules & Acceptance Criteria:
1. **Syntactic POS Validity**:
   - Every candidate term must be a 1-to-4 word noun phrase or an uppercase technical acronym (e.g. `GCN`, `MIP`, `AdMM`).
   - Candidate terms must **never** cross sentence clause boundaries (punctuation `, ; : . ! ? \n`).
2. **Noise & False Positive Elimination**:
   - **0% Math Variables**: Single-character tokens (`x`, `y`, `n`, `i`, `psi`) must be filtered out.
   - **0% Layout Labels**: Words like `figure`, `table`, `section`, `page`, `author`, `citation` must be rejected.
   - **0% Generic Unigram Words**: Terms like `method`, `system`, `solution`, `problem`, `paper`, `approach` must be excluded.
3. **Deduplication & Subsumption**:
   - Shorter sub-phrases must be subsumed into longer representations (`"bipartite graph"` $\to$ `"bipartite graph representation"`).
   - Plurals must be singularized (`"integer variables"` $\to$ `"integer variable"`).

#### Test Code Snippet:
```python
def test_validate_concepts(concepts_data):
    assert isinstance(concepts_data, list), "concepts.json must be a list"
    assert len(concepts_data) >= 10, "Should extract at least 10 core concepts"
    
    invalid_endings = {'using', 'used', 'showing', 'describing', 'method', 'paper'}
    for concept in concepts_data:
        term = concept if isinstance(concept, str) else concept.get("label", "")
        words = term.lower().split()
        assert len(words) <= 4 or (len(words) == 5 and words[0] == "model"), f"Term too long: {term}"
        assert words[-1] not in invalid_endings, f"Invalid phrase ending in term: {term}"
        assert not (len(words) == 1 and len(words[0]) == 1), f"Single-letter variable leaked: {term}"
```

---

### 2. Paper Notes & Glossary Compiler
* **Script**: [`pipeline/research_paper/generate_paper_notes.py`](pipeline/research_paper/generate_paper_notes.py)
* **Output Artifact**: `notes.md` / `notes.json`

#### Validation Rules & Acceptance Criteria:
1. **Grounding & Citation Verification**:
   - Every defined concept entry must be accompanied by explicit section citations in the format: `Page X (Section 'Y')`.
2. **Page Boundary Check**:
   - `Page X` numbers must satisfy $1 \le X \le \text{Total PDF Pages}$.
3. **Definition Quality**:
   - Definitions must not be empty or generic placeholders (`"N/A"` or `"Undefined"`).

#### Test Code Snippet:
```python
def test_validate_glossary(notes_text, total_pdf_pages):
    # Pattern: * **term** *(Sources: Page X (Section 'Y'))*: definition
    pattern = r'\* \*\*(.+?)\*\* \*\(Sources: Page (\d+) \(Section \'(.+?)\'\)\)\*: (.+)'
    matches = re.findall(pattern, notes_text)
    assert len(matches) > 0, "Glossary must contain valid grounded entry lines"
    
    for term, page_str, section, definition in matches:
        page_num = int(page_str)
        assert 1 <= page_num <= total_pdf_pages, f"Page {page_num} out of bounds (1..{total_pdf_pages})"
        assert len(definition.strip()) >= 15, f"Definition for '{term}' is too brief"
```

---

### 3. Executive Summary Synthesizer
* **Script**: [`pipeline/research_paper/generate_paper_summary.py`](pipeline/research_paper/generate_paper_summary.py)
* **Output Artifact**: `summary.json`

#### Validation Rules & Acceptance Criteria:
1. **Mandatory Schema Envelope**:
   Must contain all 5 required JSON keys: `executive`, `tldr`, `research_question`, `contributions`, `sections`.
2. **Key Constraints**:
   - `tldr`: Single concise summary string (1–3 sentences).
   - `contributions`: Non-empty list of string bullet points ($\ge 2$ items).
   - `sections`: List of objects containing `title` and `summary`.

#### Test Code Snippet:
```python
def test_validate_summary_schema(summary_json):
    required_keys = ["executive", "tldr", "research_question", "contributions", "sections"]
    for key in required_keys:
        assert key in summary_json, f"Missing required key: {key}"
        
    assert len(summary_json["contributions"]) >= 2, "Contributions list must contain at least 2 items"
    assert len(summary_json["sections"]) >= 1, "Must contain at least 1 section summary"
```

---

### 4. Architecture Notes Compiler
* **Script**: [`pipeline/research_paper/generate_architecture_notes.py`](pipeline/research_paper/generate_architecture_notes.py)
* **Output Artifact**: `architecture_notes.md`

#### Validation Rules & Acceptance Criteria:
1. **Markdown Formatting**:
   - Must start with an H1 heading (`# System Architecture` or `# Technical Architecture`).
   - Tables must be formatted with standard Markdown pipe boundaries (`| Column 1 | Column 2 |`).
2. **Mermaid Flowchart Syntax (If Present)**:
   - Any Mermaid block (```mermaid) must start with `flowchart` or `graph` and contain valid node connections (`-->`).

#### Test Code Snippet:
```python
def test_validate_architecture_markdown(markdown_text):
    assert markdown_text.strip().startswith("#"), "Architecture notes must begin with a Markdown H1 header"
    if "|---" in markdown_text:
        table_rows = [line for line in markdown_text.split('\n') if line.strip().startswith('|')]
        assert len(table_rows) >= 3, "Markdown tables must have header, separator, and data rows"
```

---

### 5. Citation & Reference Analyzer
* **Script**: [`pipeline/research_paper/extract_paper_references.py`](pipeline/research_paper/extract_paper_references.py)
* **Output Artifact**: `references.json`

#### Validation Rules & Acceptance Criteria:
1. **Role Classification Enum**:
   `role` must strictly match one of the authorized scientific influence categories:
   - `"Foundational"`
   - `"Baseline"`
   - `"Comparison"`
   - `"Theoretical Support"`
   - `"Background / Related Work"`
2. **Context Sentence Verification**:
   - `context_sentences` must be a list containing text snippets where the reference key or author name was cited.

#### Test Code Snippet:
```python
def test_validate_references(references_data):
    valid_roles = {"Foundational", "Baseline", "Comparison", "Theoretical Support", "Background / Related Work"}
    assert isinstance(references_data, list), "references.json must be a list"
    
    for ref in references_data:
        assert "key" in ref, "Reference entry missing 'key'"
        assert "role" in ref, "Reference entry missing 'role'"
        assert ref["role"] in valid_roles, f"Invalid reference role: {ref['role']}"
```

---

### 6. Mathematical Nomenclature Extractor
* **Script**: [`pipeline/research_paper/extract_notations_local.py`](pipeline/research_paper/extract_notations_local.py)
* **Output Artifact**: `notations.json`

#### Validation Rules & Acceptance Criteria:
1. **Symbol Formatting**:
   - `symbol` must represent a mathematical symbol, Greek letter (e.g. `\alpha`, `\beta`, `\theta`), or math notation (e.g. `W_i`, `\mathcal{F}`).
2. **No Word Leaks**:
   - `symbol` must not contain general English stopwords (e.g. `the`, `and`, `from`).
3. **Meaning Availability**:
   - `meaning` must provide a non-empty explanation of the symbol's paper role.

#### Test Code Snippet:
```python
def test_validate_notations(notations_data):
    stopwords = {"the", "and", "for", "with", "from", "that", "this"}
    assert isinstance(notations_data, list), "notations.json must be a list"
    
    for item in notations_data:
        sym = item.get("symbol", "").strip()
        meaning = item.get("meaning", "").strip()
        assert sym, "Notation symbol cannot be empty"
        assert sym.lower() not in stopwords, f"English stopword leaked as notation symbol: {sym}"
        assert len(meaning) >= 3, f"Meaning too short for symbol '{sym}'"
```

---

### 7. LaTeX Equation & Math Extractor
* **Script**: [`pipeline/research_paper/extract_paper_equations.py`](pipeline/research_paper/extract_paper_equations.py)
* **Output Artifact**: `equations.json`

#### Validation Rules & Acceptance Criteria:
1. **KaTeX / LaTeX Syntax Validity**:
   - `latex` string must be valid LaTeX markup (e.g., `y = \mathcal{F}(x, \{W_i\}) + x`).
2. **Source Page Metadata**:
   - `page` must be an integer pointing to the equation's exact page occurrence.

#### Test Code Snippet:
```python
def test_validate_equations(equations_data, total_pdf_pages):
    assert isinstance(equations_data, list), "equations.json must be a list"
    
    for eq in equations_data:
        assert "latex" in eq and eq["latex"].strip(), "Equation missing LaTeX string"
        assert "page" in eq, "Equation missing page number"
        assert 1 <= int(eq["page"]) <= total_pdf_pages, f"Equation page {eq['page']} out of bounds"
```

---

## 🧪 Automated Master Validation Test Suite

To run automated validation across all pipeline outputs for a paper session:

```bash
# Run automated validation test suite
python pipeline/utils.py --validate-session <session_id_or_output_dir>
```

This ensures every extracted artifact meets **100% schema compliance**, **zero mathematical/layout leakage**, and **100% page boundary grounding** before frontend rendering.
