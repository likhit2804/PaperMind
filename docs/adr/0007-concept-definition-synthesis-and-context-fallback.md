# ADR-0007: Concept Definition Synthesis with Resilient Direct-Text Fallback

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & AI Guidelines

---

## 1. Context & Problem Statement

In the PaperMind autonomous pipeline, `pipeline/research_paper/extract_paper_concepts.py` is responsible for extracting, verifying, and defining technical concepts across research papers.

Previously, concept definitions were generated solely by `extract_concept_context_sentences()`, which searched the paper text for the first sentence mentioning the concept and appended a hardcoded metadata string:
`[Role: Key structural concept used in paper execution]`

This resulted in significant usability and architectural shortcomings:
1. **Raw Narrative Sentences Instead of Definitions:** Instead of concise, dictionary-grade explanations of what a concept is (e.g., "A spatial pooling strategy that creates fixed-size representations..."), the UI displayed narrative paper sentences (e.g., "In Section 3, we evaluate SPP-net under varying scale conditions...").
2. **Missing Operational Context:** The hardcoded role string provided no differentiation between a loss function, a primary architecture, a baseline model, or an evaluation metric.
3. **LLM Fragility vs Hermetic Execution:** If the pipeline switched to a pure LLM approach without offline resilience, any rate limit, API quota failure, or network disruption would abort the entire paper extraction.

---

## 2. Decision

We decided to implement a **hybrid two-tier definition architecture (Option A with Option B fallback)** in `pipeline/research_paper/extract_paper_concepts.py`:

### A. Option A: Batched AI Definition Synthesis
- Grounding: When Gemini is configured and available, `extract_concept_context_sentences()` first gathers verbatim occurrence sentences from the paper.
- Batching: Concepts are batched into chunks of 15 with their extracted context sentences and paper title.
- Generation: A structured JSON prompt directs Gemini to synthesize:
  1. A formal 1-2 sentence definition explaining what the concept is in the context of the paper.
  2. A concise operational role (e.g., "Primary proposed architecture", "Evaluation metric", "Loss function", "Baseline comparison") under 6 words.
- Tagging: Generated records are tagged with `[Source: ai_generated]` and `[Role: <role>]`.

### B. Option B: Deterministic Direct-Text Fallback
- If Gemini is unavailable, unauthenticated, rate-limited, or raises an exception:
  1. The pipeline catches the error and logs a clear console diagnostic.
  2. It automatically switches to Option B via `format_fallback_definitions()`.
  3. Context sentences are extracted and tagged with `[Role: Paper Context Extract] [Source: direct_text]`.
- This guarantees the pipeline never crashes during concept definition generation.

### C. Client-Side Tag Sanitization
- To prevent internal bracketed tags (`[Role: ...]`, `[Source: ...]`, `[Connections: ...]`) from leaking into list previews and chat answers:
  1. In `PaperExplorer.jsx`, added `cleanPreviewDefinition()` to strip metadata tags from the left-hand master list items (`.ktp-item-def`).
  2. In `RagAssistant.jsx`, added clean regex stripping before returning semantic search answers.
  3. The detail pane in `PaperExplorer.jsx` parses tags into structured UI badges and cleanly separated fields.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A + Option B Hybrid (Chosen)
- **Pros:** High-quality formal definitions and roles when LLM is available; guaranteed 100% pipeline reliability and zero crashes when offline or quota-limited; clear metadata provenance.
- **Cons:** Two code paths to maintain; requires prompt schema synchronization.

### Pure LLM Generation (No Fallback)
- **Pros:** Single code path.
- **Cons:** Brittle; pipeline crashes if API quota is exceeded or network drops during a paper run.
- **Reason for Rejection:** Violates reliability and offline execution principles established in ADR-0001.

### Pure Rule-Based Regex Extraction (Status Quo)
- **Pros:** Zero API costs; fast execution.
- **Cons:** Fails to provide true definitions; outputs confusing paper narrative fragments.
- **Reason for Rejection:** Directly rejected due to low definition quality and repetitive hardcoded roles.

---

## 4. Consequences & Operational Impact

- **Positive:** Concepts now present accurate, high-fidelity definitions and accurate paper roles. Offline developers and CI runs without Gemini API keys complete successfully using Option B.
- **Negative / Risks:** Batched LLM generation adds approximately 2-5 seconds to Stage 5 of the pipeline when online.
- **Monitoring:** Batch size of 15 is optimized to fit within token limits and single-request latency boundaries.

---

## 5. Review & Revisit Trigger

We will revisit this architectural choice if:
- Gemini JSON schema validation error rate exceeds 2% across production papers.
- Local small language models (e.g., Ollama / Llama 3 8B) are introduced for hermetic, zero-cost local synthesis.
