# Prompts Changelog — PaperMind Extraction Pipeline

All prompt modifications across the 7-stage research paper extraction pipeline must be version-tracked in this file. 
Before updating a prompt in production, verify quality against the golden eval dataset.

---

## Format:
```markdown
### [prompt_name] vX.Y — YYYY-MM-DD
- **Target Extraction Stage:** (e.g. Concept Metadata, Equation Mapping)
- **Model Target:** e.g. gemini-1.5-flash
- **Motivation:** What failure mode or hallucination inspired this change?
- **Changes Made:** Specific prompt adjustments, delimiters, or few-shot examples.
- **Eval Delta:** Before vs After benchmark accuracy.
```

---

## Log Entries

### `metadata_extraction` v1.0 — 2026-10-21
- **Target Extraction Stage:** Stage 1 — Paper Metadata & Seed Canonical Concepts
- **Model Target:** `gemini-1.5-flash`
- **Motivation:** Initial migration from inline Python f-string to versioned template file.
- **Changes Made:** Externalized template with explicit JSON schema delimiters and `{text_snippet}` variable placeholder.
- **Eval Delta:** Baseline parity established.

### `equation_extraction` v1.0 — 2026-10-21
- **Target Extraction Stage:** Stage 2 — Complex LaTeX Equation & Notation Parser
- **Model Target:** `gemini-1.5-flash`
- **Motivation:** Decouple inline batched math prompt from Python parsing code into versioned template.
- **Changes Made:** Externalized template with `{title}` and `{consolidated_input}` placeholders and double-bracketed JSON schema.
- **Eval Delta:** Baseline parity established.
