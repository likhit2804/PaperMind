# 5-Minute Project Health Scorecard

> **Target Audience:** Tech Leads, Senior Engineers, and Autonomous AI Agents  
> **Purpose:** Rapid diagnostic assessment (0–100 points) to evaluate any existing project before starting refactoring or quality adoption.

---

## 🧭 How to Use This Scorecard

1. Audit the repository against the 5 quality pillars below (20 points each).
2. Calculate the total score out of 100.
3. Use the **Action Threshold Table** at the bottom to determine your starting phase.

---

## Pillar 1: Static Enforcement & Styling (20 Points)

| Criteria | Points | Check |
| :--- | :---: | :---: |
| Automated code formatter is configured (`ruff format`, `prettier`) and runs in CI. | 5 | [ ] |
| Automated linter (`ruff`, `eslint`) runs in CI with a zero-warning policy on new files. | 5 | [ ] |
| Pre-commit hooks (`.pre-commit-config.yaml`) run formatting and secret scanning locally. | 5 | [ ] |
| Static type checking (`mypy --strict` or `tsc --strict`) is enforced on all new/modified code. | 5 | [ ] |
| **Pillar 1 Subtotal:** | **/ 20** | |

---

## Pillar 2: Backend Reliability & Network Hardening (20 Points)

| Criteria | Points | Check |
| :--- | :---: | :---: |
| **Every** outbound network call (HTTP, DB, cache, LLM) has explicit connect and read timeouts. | 5 | [ ] |
| Retries are restricted exclusively to transient errors (502, 503, 429) and use **full jitter**. | 5 | [ ] |
| State-changing API endpoints accept an `Idempotency-Key` and enforce uniqueness in DB. | 5 | [ ] |
| Database transactions are short, and zero network/LLM calls occur inside transactions. | 5 | [ ] |
| **Pillar 2 Subtotal:** | **/ 20** | |

---

## Pillar 3: Test Safety Net & Verification (20 Points)

| Criteria | Points | Check |
| :--- | :---: | :---: |
| Unit test suite executes fully in-memory without live external network dependencies (< 30s). | 5 | [ ] |
| All reported production bugs ship with a reproducible regression test before fix. | 5 | [ ] |
| Pull requests enforce $> 80\%$ **diff coverage** on newly changed lines. | 5 | [ ] |
| Zero flaky tests quarantined or ignored in the main branch. | 5 | [ ] |
| **Pillar 3 Subtotal:** | **/ 20** | |

---

## Pillar 4: AI Layer Architecture & Quality (20 Points)
*(If non-AI project, award full 20 points)*

| Criteria | Points | Check |
| :--- | :---: | :---: |
| All LLM calls flow through a unified internal client protocol (`LLMClient`), not raw SDK calls. | 5 | [ ] |
| Prompts reside in versioned files (`prompts/`) with strict Jinja2 template rendering. | 5 | [ ] |
| All model outputs are schema-validated (Pydantic/Zod) with bounded (max 1 retry) repair. | 5 | [ ] |
| A curated golden evaluation dataset (20–50 cases) runs in CI before model/prompt updates. | 5 | [ ] |
| **Pillar 4 Subtotal:** | **/ 20** | |

---

## Pillar 5: Architecture, Config & Observability (20 Points)

| Criteria | Points | Check |
| :--- | :---: | :---: |
| Environment configuration is validated at boot (`pydantic-settings`), failing loudly if invalid. | 5 | [ ] |
| Zero secrets, tokens, or plaintext passwords committed to Git or printed in logs. | 5 | [ ] |
| Structured JSON logs emitted with a `request_id` / `correlation_id` on every line. | 5 | [ ] |
| A newcomer can clone the repository and run it locally in $\le 2$ commands using the README. | 5 | [ ] |
| **Pillar 5 Subtotal:** | **/ 20** | |

---

## 📊 Score Diagnostic & Starting Action Plan

| Total Score | Health Grade | Diagnostic & Immediate Action Plan |
| :---: | :--- | :--- |
| **0 – 39** | 🔴 **Critical Fragility** | **Emergency Stabilization:** High risk of production outages. Start with [AGENTS.md Step 2 & 3 (Formatter & Linter)](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/AGENTS.md) and [Step 5 (Timeouts)](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md). Do not attempt large refactors. |
| **40 – 69** | 🟡 **Moderate Debt** | **Systematic Ratchet:** The project delivers features but suffers from regressions and slow reviews. Execute [Phase 2 (Typing/Config)](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) and [Phase 4 (AI Layer Fencing)](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md). |
| **70 – 89** | 🟢 **Healthy & Maintainable** | **Continuous Polishing:** Strong foundation. Focus on paydown of the top 2 churn hotspots ([07_refactoring_and_technical_debt.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/07_refactoring_and_technical_debt.md)) and golden eval coverage. |
| **90 – 100** | 🏆 **World-Class Engineering** | **Exemplary:** Follow the [Daily Commit Workflow](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) and monitor DORA metrics monthly. |
