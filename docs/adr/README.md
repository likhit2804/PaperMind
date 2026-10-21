# Architecture Decision Records (ADRs)

This directory documents all significant architectural and engineering decisions made in **PaperMind**. 
Records are permanent historical artifacts: decisions are superseded by new ADRs, never edited in hindsight.

---

## Index of Records

| ADR | Title | Date | Status | Scope |
| :---: | :--- | :---: | :---: | :--- |
| **[ADR-0001](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0001-adopt-code-quality-and-reliability-standards.md)** | Adopt Phased Code Quality, Boot Validation, and Subprocess Timeout Controls | 2026-10-21 | **Accepted** | Fullstack Architecture, Reliability & Tooling |
| **[ADR-0002](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0002-isolate-prompts-and-schema-validation.md)** | Isolate Prompts as Code and Enforce Schema Validation | 2026-10-21 | **Accepted** | AI Pipeline, Prompt Registry & Pydantic Schemas |
| **[ADR-0003](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0003-automated-ci-and-pull-request-gates.md)** | Automated CI Pipeline, Security Scanning & Pull Request Gates | 2026-10-21 | **Accepted** | CI/CD, GitHub Actions & PR Review Quality |
| **[ADR-0004](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0004-offline-golden-benchmarks-and-evaluation-harness.md)** | Offline Golden Benchmarks and Automated Evaluation Harness | 2026-10-21 | **Accepted** | AI Evaluation, Schema Conformity & Hermetic Testing |
| **[ADR-0005](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0005-rag-citation-verification-and-hallucination-defense.md)** | RAG Citation Verification and Hallucination Defense | 2026-10-21 | **Accepted** | RAG Reliability, HexiBot Citations & Grounding Metrics |
| **[ADR-0006](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0006-direct-paper-text-transparency-and-source-indicators.md)** | Direct Paper Text Transparency and Non-Intrusive Source Indicators | 2026-10-21 | **Accepted** | UI/UX, AI Transparency & Provenance Communication |
| **[ADR-0007](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/docs/adr/0007-concept-definition-synthesis-and-context-fallback.md)** | Concept Definition Synthesis with Resilient Direct-Text Fallback | 2026-10-21 | **Accepted** | Concept Pipeline, Gemini Batching & Fault-Tolerant Fallback |

---

## How to Propose a New ADR
1. Copy the standard template from [code_quality_guide/templates/adr_template.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/templates/adr_template.md).
2. Save it as `docs/adr/NNNN-short-descriptive-title.md`.
3. Set status to `Proposed` and submit as a pull request for team discussion.
