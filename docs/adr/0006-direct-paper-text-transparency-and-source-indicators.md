# ADR-0006: Direct Paper Text Transparency and Non-Intrusive Source Indicators

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & UI/UX Guidelines

---

## 1. Context & Problem Statement

PaperMind provides intelligent paper navigation through conceptual definitions and an interactive conversational assistant (HexiBot). Under normal conditions, these features leverage generative AI (Google Gemini) to synthesize formal definitions, explain mathematical equations, and synthesize answers to user inquiries.

However, when external AI providers are unavailable (e.g., API quota exhaustion, network outages, offline execution, or aggressive request timeouts), the system falls back to deterministic extraction—supplying raw context sentences or BM25 keyword-matched paragraphs directly from the paper.

Two key user-experience problems arose:
1. **Lack of Provenance Transparency:** Users could not distinguish whether a displayed sentence was a synthesized, authoritative definition or an isolated verbatim sentence lifted directly from the text.
2. **Badge Clutter and Redundancy:** Initial UI implementations displayed dual badges (`AI Synthesized` in green and `Direct Paper Text` in amber), while appending `(AI Synthesized)` to section headers. Because AI synthesis is the expected primary mode of the application, labeling normal operations created visual noise, redundant text, and distracted the user.

---

## 2. Decision

We decided to adopt an **asymmetric, non-intrusive source indicator architecture**:

### A. Asymmetric Source Badging
- **Normal Operation (AI-Synthesized):** The primary view renders the clean header **`Concept Definition`** with no badges, suffixes, or explanatory tags. Generative AI is the baseline assumption.
- **Direct Text Fallback:** When a definition is an un-synthesized verbatim extract from paper text, the system displays an amber badge **`Direct Paper Text`** adjacent to the header.
- **RAG Assistant Transparency:** If the conversational assistant falls back to direct section extraction without an LLM, the chat response displays a distinct source badge and an explanatory banner informing the user that generative AI was bypassed.

### B. Strict Emoji-Free Design System
- In alignment with professional scientific UI guidelines, all source badges, warning banners, and status indicators strictly use CSS status indicators, typography, and SVG icons. No emojis are used anywhere in badges or notification components.

### C. Backward-Compatible Provenance Detection
- Historical session records created by earlier pipeline versions contain legacy metadata strings such as `[Role: Key structural concept used in paper execution]`.
- The frontend detail renderer in `frontend-react/src/components/PaperExplorer/PaperExplorer.jsx` inspects concept strings for both modern metadata tags (`[Source: direct_text]`, `[Role: Paper Context Extract]`) and legacy indicators, ensuring pre-existing cached sessions correctly render as Direct Paper Text without data corruption or breaking changes.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Asymmetric Source Indication (Chosen)
- **Pros:** Zero visual clutter during normal operation; clear, high-contrast warning when raw extracted text is displayed; immediate provenance transparency without duplicate labels.
- **Cons:** Requires client-side parsing of provenance metadata tags.

### Option B: Symmetric Badging (Both "AI Synthesized" and "Direct Paper Text")
- **Pros:** Explicitly marks every single card with its origin.
- **Cons:** Heavy visual noise; redundant when 95%+ of items are AI-synthesized; duplicates header labels.
- **Reason for Rejection:** Evaluated and rejected after user feedback confirmed redundant and cluttered presentation.

### Option C: Modal Alerts or Toast Warnings on Fallback
- **Pros:** Unmistakable notification to the user.
- **Cons:** Disrupts exploration flow and requires user dismissal on every item click.
- **Reason for Rejection:** Degrades user experience during extended offline or quota-limited usage.

---

## 4. Consequences & Operational Impact

- **Positive:** Users always know when a definition is a raw sentence excerpt versus a synthesized concept definition. Clean, uncluttered UI during normal AI operation.
- **Negative / Risks:** Requires client and pipeline coordination on source tags (`[Source: direct_text]`, `[Source: ai_generated]`).
- **Compliance & Trust:** Enhances academic grounding and reduces perceived hallucination risks by explicitly declaring raw text excerpts.

---

## 5. Review & Revisit Trigger

We will revisit this architectural choice if:
- PaperMind adds multi-model ensemble synthesis where displaying specific model names (e.g., Gemini vs Claude vs Local SLM) becomes necessary.
- User study telemetry indicates confusion regarding the source of definitions.
