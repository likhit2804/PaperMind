# ADR-0005: RAG Citation Verification and Hallucination Defense

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & AI Guidelines ([05_ai_engineering_practices.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md), [02_backend_architecture_and_design.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_architecture_and_design.md))

---

## 1. Context & Problem Statement
HexiBot (the interactive conversational assistant in PaperMind) answers researcher questions using a continuous Reciprocal Rank Fusion (RRF) retrieval engine over extracted concepts, equations, and passage chunks.
Previously:
1. Candidate citations returned by the backend were compiled directly from retrieved items without verifying whether the LLM actually grounded its answer on those pages.
2. If the LLM hallucinated page references in its text (e.g., claiming a formula was derived on "Page 42" when the document was only 12 pages), the response was returned verbatim with unverified citation anchors.
3. There were no grounding metrics or hallucination detection signals returned to the client UI.

---

## 2. Decision

We implemented a dedicated **RAG Citation Verifier & Hallucination Defense Layer**:
1. **Citation Grounding Engine (`backend-node/src/ragCitationVerifier.js`):**
   - Parses explicit page citations mentioned in synthesized LLM answers using regex pattern matching (`Page (\d+)`, `p. (\d+)`).
   - Cross-references mentioned pages against the set of verified pages in retrieved passage chunks and entities.
   - Enforces document boundary limits (`totalPages`) to catch phantom citations.
   - Computes a normalized grounding score (`0.0` to `1.0`) and flags hallucinated page numbers.
2. **API Response Enhancement (`backend-node/src/routes/paper.js`):**
   - In `/paper/rag/query`, candidate citations are filtered through `verifyRagCitations` before returning to the frontend.
   - Added a `grounding` metadata object (`isFullyGrounded`, `hallucinatedPages`, `groundingScore`, `totalMentionedPages`) to the response payload.
3. **Automated Unit Testing (`backend-node/src/ragCitationVerifier.test.js`):**
   - Implemented unit tests verifying detection of out-of-bounds pages, calculation of grounding scores, and filtering of phantom citations.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Trust LLM Output Verbatim
- **Tradeoffs:** Zero additional backend logic, but allows researchers to receive fabricated citations, eroding trust in the application's core value proposition ("Read less. Understand more.").
- **Verdict:** **Rejected.**

### Option B: Reject Responses Completely on Single Hallucinated Page Mention
- **Tradeoffs:** High precision, but causes unacceptable availability loss and degraded user experience when the synthesized answer itself is conceptually correct despite an inaccurate page mention.
- **Verdict:** **Rejected.** We chose graceful defense: filtering the citation list and returning grounding telemetry so the client can display grounding badges.

---

## 4. Consequences
- **Positive:**
  - Guaranteed citation validity: researchers are never directed to non-existent pages.
  - Transparent telemetry: client applications can visually highlight grounding status.
  - Isolated, pure function design enables fast Node.js unit testing.
- **Negative / Maintenance:**
  - Document total page count should be preserved in `summary.json` or metadata for tightest upper-bound validation.
