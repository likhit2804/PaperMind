# ADR-0003: Automated CI Pipeline, Security Scanning & Pull Request Gates

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** PaperMind Core Engineering Team
- **Consulted:** Architecture & Quality Guidelines ([03_automated_enforcement.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md), [06_code_review_and_collaboration.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/06_code_review_and_collaboration.md))

---

## 1. Context & Problem Statement
Prior to this decision, code changes in PaperMind were verified manually on individual developer machines. Without automated pull request gates:
1. Syntax, formatting, and type errors could be merged undetected.
2. Inadvertent leaks of sensitive credentials (such as Google Gemini API keys) in code or tests were a critical security risk.
3. PR reviews spent time discussing formatting style rather than architecture and correctness.
4. Developers lacked a standardized PR template to document risks, testing evidence, and AI prompt eval deltas.

---

## 2. Decision

We implemented a multi-layered automated CI and PR gating system:
1. **GitHub Actions Workflow (`.github/workflows/ci.yml`):**
   - Configured 4 parallel, fast execution jobs:
     - **Static Checks:** Runs Ruff format check, Ruff lint, and Mypy typecheck on `pipeline/`.
     - **Pipeline Unit Tests:** Runs `pytest` using `FakeGeminiModel` test doubles (completing in seconds with zero network I/O or token costs).
     - **Backend Checks:** Performs `npm ci` and boot verification of `backend-node`.
     - **Security Audit:** Scans entire Git history and PR diffs with **Gitleaks** to block committed API keys or tokens.
2. **Pull Request Description Template (`.github/pull_request_template.md`):**
   - Mandates sections for *What and Why*, *Testing Evidence*, *Risks / Rollout*, and a dedicated *AI & Prompt Versioning Checklist*.
3. **Git Blame Preservation (`.git-blame-ignore-revs`):**
   - Established the ignore-revs file so large repository formatting commits do not overwrite line authorship in `git blame`.

---

## 3. Alternatives Evaluated & Tradeoffs

### Option A: Monolithic Sequential CI Job
- **Tradeoffs:** Slower builds (15–20 minutes) causing developer idle time.
- **Verdict:** **Rejected.** We chose fast, independent parallel jobs targeting $< 5$ minutes total pipeline time.

### Option B: Pre-Commit Only (No CI)
- **Tradeoffs:** Local git hooks can be skipped with `git commit --no-verify`.
- **Verdict:** **Rejected.** Pre-commit hooks are for local convenience; CI remains the immutable final authority.

---

## 4. Consequences
- **Positive:**
  - Automated detection of regressions, syntax bugs, and leaked API keys before merge.
  - Reviews focus exclusively on high-level logic and architecture.
  - Repeatable, reproducible pipeline unit tests run on every commit.
- **Negative / Maintenance:**
  - Changes to dependencies in `requirements.txt` or `package.json` must pass CI checks before merge.
