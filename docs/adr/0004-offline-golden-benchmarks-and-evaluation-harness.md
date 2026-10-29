# ADR-0004: Offline Golden Benchmarks and Automated Evaluation Harness

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & AI Guidelines ([05_ai_engineering_practices.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md), [04_testing_and_quality_assurance.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/04_testing_and_quality_assurance.md))

---

## 1. Context & Problem Statement
The PaperMind pipeline extracts key scientific concepts, domains, mathematical formulas, and notation definitions from complex research papers.
Previously:
1. Extraction evaluation relied on `evaluate_public_benchmarks.py`, which attempted to dynamically download XML papers from external GitHub repositories over raw HTTP at runtime.
2. In CI/CD or offline local development environments, external network failures, rate-limiting, or altered remote URLs caused test runs to fail or hang unpredictably.
3. There was no standardized local benchmark dataset tracking recall, precision, and schema conformity across prompt changes or algorithm updates.

---

## 2. Decision

We established a hermetic, offline-first evaluation harness:
1. **Curated Golden Benchmark Dataset (`pipeline/evals/golden_benchmark.jsonl`):**
   - Packaged 6 canonical benchmark cases spanning Transformers, Mixed Integer Linear Programming (MIP), Residual Networks (ResNet), Stochastic Optimization (Adam), Reinforcement Learning (PPO), and Parameter-Efficient Fine-Tuning (LoRA).
   - Each entry defines verified canonical seed concepts, display-math LaTeX equations, and notation definitions.
2. **Automated Evaluation Runner (`pipeline/evals/run_eval.py`):**
   - Implemented an offline evaluation script measuring:
     - **Schema Conformity Rate:** Verification against `ConceptMetadataOutput` and `BatchedEquationsOutput`.
     - **Token Overlap / Recall:** F1 and recall across domain terms.
     - **LaTeX Delimiter Adherence:** Strict `$$...$$` display math formatting and notation validity.
3. **CI Integration (`pipeline/tests/test_fakes.py`):**
   - Registered `test_golden_benchmark_suite()` into the pytest suite, enforcing that any regression in concept recall or schema compliance halts CI pull request checks.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Continue Relying on Runtime Network Downloads
- **Tradeoffs:** Avoids storing benchmark JSONL in repository, but introduces flaky network dependencies and breaks CI hermeticity.
- **Verdict:** **Rejected.**

### Option B: Heavy External Eval Frameworks (DeepEval / Ragas)
- **Tradeoffs:** Adds substantial dependencies, requires cloud API keys for evaluation-as-a-judge, and significantly slows down CI test cycles.
- **Verdict:** **Rejected.** Lightweight, deterministic local metrics provide fast sub-second feedback in CI without recurring LLM costs.

---

## 4. Consequences
- **Positive:**
  - 100% offline reproducibility: evaluation runs locally and in CI with zero network calls and zero API cost.
  - Objective regression gates for prompt revisions and heuristic improvements.
  - Explicit baseline metrics: 100% schema conformity and >90% canonical seed recall.
- **Negative / Maintenance:**
  - Engineers introducing new paper domains (e.g. quantum algorithms or bioinformatics) should add representative test cases to `golden_benchmark.jsonl`.
