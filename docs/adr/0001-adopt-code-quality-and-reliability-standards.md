# ADR-0001: Adopt Phased Code Quality, Boot Validation, and Subprocess Timeout Controls

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & AI Guidelines

---

## 1. Context & Problem Statement
PaperMind is a hybrid fullstack AI research paper intelligence workbench comprising:
- A Node.js / Express backend (`backend-node`) that serves APIs, manages document uploads, and orchestrates Python subprocesses.
- A 7-stage Python 3.11+ autonomous extraction pipeline (`pipeline/`) integrating Google Gemini LLMs for concept and equation extraction.
- A React 18 / Vite frontend (`frontend-react`) for user exploration.

As query volume and paper complexity grew, several reliability and maintainability risks emerged:
1. **Unvalidated Environment Configuration:** Environment variables were accessed loosely with `process.env` and `os.getenv`. Missing or malformed keys caused late runtime failures mid-request.
2. **Zombie Subprocesses on Timeout:** In `backend-node/src/routes/paper.js`, `runPythonWithTimeout` rejected a promise on timeout but never terminated the spawned `python.exe` process, allowing orphaned processes to consume server CPU and memory indefinitely.
3. **Unbounded Pipeline Stages:** Individual extraction scripts lacked per-stage execution timeouts, causing a hung script to freeze the entire pipeline.
4. **Lack of Automated Linting & Style Standards:** Style debates and syntax discrepancies existed across the codebase with no centralized formatter or static type checker.

---

## 2. Decision

We decided to adopt the **Code Quality and Maintainability Guide** through a non-disruptive phased brownfield rollout:

### A. 12-Factor Boot-Time Configuration Validation
- In `backend-node/src/config.js`, we integrated **Zod** schema validation. The server validates all environment variables at startup and prints structured diagnostic logs if invalid, failing fast before traffic is served.
- In `pipeline/config.py`, we created a typed `PipelineSettings` class using **Pydantic-Settings**, masking API keys with `SecretStr` to prevent accidental log leakage.

### B. Subprocess Timeout Hardening & Zombie Elimination
- In `backend-node/src/routes/paper.js`, `runPythonWithTimeout` was refactored to actively track the spawned child process. On timeout, it issues `SIGTERM` followed by a fallback `SIGKILL` after 3 seconds.
- In `pipeline/research_paper/unified_paper_pipeline.py`, `run_script` was equipped with an asynchronous log-streaming thread and a strict 300-second (5 minute) per-stage timeout guard that kills hung child processes.

### C. Static Tooling & Ratchet Baseline
- In `pyproject.toml`, we configured **Ruff** for high-speed formatting and linting, and **Mypy** for strict typing.
- We applied the **Ratchet Principle**: legacy extraction modules (`pipeline.research_paper.*`) have temporary overrides so existing code runs without blocking builds, while all new modules adhere to strict type checking.
- In `.pre-commit-config.yaml`, we introduced fast local hooks for file hygiene, Ruff, Prettier, and Gitleaks secret scanning.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Complete Big-Bang System Rewrite
- **Tradeoffs:** High probability of introducing subtle regressions in PDF parsing and equation extraction algorithms; halts product feature delivery for weeks.
- **Verdict:** **Rejected.**

### Option B: Ad-Hoc Exception Handling Patches
- **Tradeoffs:** Adding individual try-catch blocks without schemas or architectural boundaries leads to brittle, unmaintainable code with inconsistent error shapes.
- **Verdict:** **Rejected.**

### Option C: Phased Brownfield Adoption (Chosen)
- **Tradeoffs:** Requires maintaining backward compatibility during transition, but guarantees zero regressions, bit-for-bit local verification, and non-disruptive delivery.
- **Verdict:** **Accepted.**

---

## 4. Consequences & Operational Impact
- **Positive:**
  - Zero zombie Python processes lingering on the server after pipeline timeouts.
  - Failures due to missing configuration occur at boot within 50ms rather than mid-extraction.
  - Fast local formatting and secret scanning before commits.
- **Negative / Maintenance:**
  - Developers must ensure new environment variables are declared in both Zod (`config.js`) and Pydantic (`config.py`).
  - Pre-commit hooks add a ~2-second check on local commits (can be run via `make check`).

---

## 5. Revisit Trigger
We will revisit this architecture if:
- Pipeline throughput demands migrating from child process execution (`spawn`) to an asynchronous task queue (e.g., Celery or BullMQ with Redis).
- Concurrent user uploads exceed the vertical scaling capacity of the single-host worker model.
