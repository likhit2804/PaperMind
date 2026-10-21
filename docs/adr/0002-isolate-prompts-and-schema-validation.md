# ADR-0002: Isolate Prompts as Code and Enforce Schema Validation

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & AI Guidelines ([05_ai_engineering_practices.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md))

---

## 1. Context & Problem Statement
The PaperMind 7-stage extraction pipeline makes LLM completions to extract canonical metadata, concepts, and complex LaTeX equations.
Previously:
1. Prompts were hardcoded inline within business logic functions as Python f-strings.
2. Modifying a prompt required editing executable code, making prompt diffs difficult to isolate in PR reviews.
3. There was no versioning or changelog tracking *why* prompts changed or whether an update caused regression.
4. Model outputs were parsed through ad-hoc regex and dictionary lookups without formal schema validation.

---

## 2. Decision

We implemented a dedicated **Prompts as Code** architecture:
1. **Versioned Prompt Registry (`pipeline/prompts/`):**
   - Externalized prompts into dedicated files (`metadata_extraction_v1.txt`, `equation_extraction_v1.txt`).
   - Implemented `load_prompt()` in `pipeline/prompts/__init__.py` with strict variable placeholder checking.
2. **Prompts Changelog (`pipeline/prompts/CHANGELOG.md`):**
   - Established a mandatory changelog tracking prompt versions, target models, motivations, and before/after evaluation deltas.
3. **Pydantic Output Schemas (`pipeline/schemas.py`):**
   - Defined strict Pydantic schemas (`ConceptMetadataOutput`, `BatchedEquationsOutput`, `EquationItem`, `NotationItem`) to enforce structured boundary validation.
4. **Deterministic Unit Testing Harness (`pipeline/tests/test_fakes.py`):**
   - Created `FakeGeminiModel` allowing extraction pipeline stages to be tested in CI deterministically without live API keys or incurring token billing.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Retain Inline Python f-strings
- **Tradeoffs:** Avoids creating a new folder, but couples prompt iteration to code deploys and obscures prompt drift.
- **Verdict:** **Rejected.**

### Option B: External LLM Frameworks (LangChain / LlamaIndex Prompt Hubs)
- **Tradeoffs:** High dependency bloat, external network calls during bootstrap, and heavy abstractions for simple prompt rendering.
- **Verdict:** **Rejected.** We chose native zero-dependency file-based templates.

---

## 4. Consequences
- **Positive:**
  - Clear separation between deterministic extraction algorithms and non-deterministic prompt templates.
  - Transparent prompt history in Git and `CHANGELOG.md`.
  - Zero-cost, fast automated pipeline unit testing via `FakeGeminiModel`.
- **Negative / Maintenance:**
  - Developers must ensure dynamic variables passed to `load_prompt()` match template placeholders.
