# Prompts Changelog

All prompt template revisions must be recorded in this log before merging to `main`. Every prompt version must be accompanied by an evaluation score diff against the golden dataset.

---

## Format
```markdown
### [Prompt Identifier] vX.Y — YYYY-MM-DD
- **Target Feature / Task:** e.g., Concept Extraction
- **Author:** @username (or Agent name)
- **Model Version Tested:** e.g., gemini-1.5-pro-002
- **Motivation / Why:** What behavior or hallucination motivated this change?
- **Changes Made:** Specific modifications to instructions, negative examples, or delimiters.
- **Eval Benchmark Results:**
  - Previous Accuracy: __%
  - New Accuracy:      __% (Delta: +__%)
- **Breaking Schema Changes:** None / Yes (explain)
```

---

## Example Log Entries

### `concept_extraction` v2.0 — 2026-03-20
- **Target Feature:** Pipeline Key Concept Extractor
- **Author:** @alex
- **Model Version Tested:** gemini-1.5-flash-002
- **Motivation:** Eval run showed a 14% hallucination rate where isolated Greek math variables ($\alpha$, $\beta$) were being classified as architectural concepts.
- **Changes Made:** Added explicit negative constraints and 3 few-shot counter-examples defining what constitutes an architectural concept vs. a notation symbol.
- **Eval Benchmark Results:**
  - Baseline v1.0 Accuracy: 78.4%
  - New v2.0 Accuracy:      91.2% (Delta: +12.8%)
- **Breaking Schema Changes:** None

### `hexi_rag_assistant` v1.1 — 2026-03-15
- **Target Feature:** HexiBot RAG Answer Synthesis
- **Author:** @sarah
- **Model Version Tested:** gemini-1.5-pro-002
- **Motivation:** Users reported answers were too wordy and failed to cite exact page numbers.
- **Changes Made:** Added strict formatting instruction requiring bracketed page citations `[Page X]` after every factual claim.
- **Eval Benchmark Results:**
  - Citation Accuracy: 64% -> 96%
- **Breaking Schema Changes:** None
