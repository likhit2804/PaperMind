# 13. Checklists & Cheat Sheets

> **Module:** Operational Checklists & Team Cheat Sheets  
> **Source:** Section 14 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [05. AI Engineering](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md) | [06. Code Review](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/06_code_review_and_collaboration.md)

---

## 1. Pull Request Review Checklist

Use this checklist during self-review before requesting peer feedback, and during code review:

### Design & Clarity
- [ ] Does this PR do one single thing, and is it small enough to review thoroughly (< 300 lines)?
- [ ] Are names descriptive and precise? Are functions small, focused, and free of side-effects?
- [ ] Are preconditions checked via early guard clauses instead of deep indentation?
- [ ] Are illegal states made unrepresentable using the type system?
- [ ] Is all external user input validated strictly at the outer system boundary?

### Correctness & Reliability
- [ ] Are specific exceptions caught and handled? Are bare `except:` / `catch (e)` blocks eliminated?
- [ ] Do **all** outbound network calls (HTTP, DB, cache, LLM) have explicit timeouts?
- [ ] Are retries restricted strictly to transient errors, bounded in count, and jittered?
- [ ] Are state-changing operations protected by idempotency keys and unique database constraints?
- [ ] Are database transactions short, and are external network/LLM calls kept strictly outside transactions?
- [ ] Are database migrations backward compatible (expand-and-contract) with a clear rollback path?

### Testing & Observability
- [ ] Are new tests added for both the happy path and edge/failure cases?
- [ ] If fixing a defect, is a regression test included that reproduces the bug without the fix?
- [ ] Are secrets, API keys, and sensitive PII kept out of code and log statements?
- [ ] Are structured JSON logs emitted with a `request_id` / `correlation_id`?
- [ ] Are documentation, README, or ADR files updated if architecture changed?

### For AI & LLM Changes
- [ ] Is the prompt stored in a versioned template file (not an inline string) and has its version been bumped?
- [ ] Is prompt history documented in `prompts/CHANGELOG.md`?
- [ ] Is the model output validated through a strict schema with a bounded (max 1 retry) repair loop?
- [ ] Are token limits, latency budgets, and costs accounted for?
- [ ] Did you run the smoke evaluation suite against the golden dataset and attach the score diff to the PR?

---

## 2. New Service Setup Checklist (12-Point Gate)

1. **Repository Setup:** Git repository initialized with a clean `.gitignore`, license, and a clear `README.md`.
2. **Automated Enforcement:** Formatter, linter, and type checker configured with local commands matching CI.
3. **Pre-Commit Hooks:** Local pre-commit hooks configured for formatting, fast lint, and secret scanning.
4. **Automated Testing:** Test framework initialized with an initial passing unit test and a real containerized integration test.
5. **Continuous Integration (CI):** Parallelized CI pipeline running static checks, unit tests, integration tests, and security audits.
6. **Reproducible Dependencies:** Lockfile committed, with an automated update bot (Dependabot / Renovate) configured.
7. **Branch Protection:** Protected `main` branch requiring passing CI and at least one peer approval.
8. **Containerization:** Multi-stage `Dockerfile` running as an unprivileged, non-root user.
9. **12-Factor Configuration:** Strongly-typed environment configuration validated at startup; secrets fetched securely without logging.
10. **Observability Baseline:** Structured JSON logging with request IDs, metrics instrumentation, and distinct `/health/live` and `/health/ready` endpoints.
11. **Graceful Shutdown:** Intercepts `SIGTERM`/`SIGINT`, halts traffic intake, finishes active tasks, and closes connections cleanly.
12. **Architecture Documentation:** `docs/adr/` initialized with ADR-0001 explaining the technology stack choice, accompanied by an initial operational runbook.

---

## 3. AI Feature Launch Checklist (12-Point Gate)

1. **Unified Client Interface:** All model calls flow through an internal client protocol with explicit timeouts, bounded retries, and token accounting.
2. **Prompts as Code:** Prompts reside in versioned template files with strict rendering; prompt ID and version are logged with every request.
3. **Model Version Pinning:** Model identifiers are managed via configuration, pinned to immutable snapshot versions (avoiding unpinned floating aliases).
4. **Strict Schema Validation:** Every model response consumed by code is schema-validated, with truncation (`finish_reason == 'length'`) explicitly handled.
5. **Golden Evaluation Dataset:** A curated dataset of 20–50 representative, edge-case, and adversarial inputs exists; smoke evals run in CI and full evals run before release.
6. **Independent RAG Metrics:** Retrieval quality (Recall@K, Precision@K, MRR) is measured and tuned independently from generation quality.
7. **Access Control Before Retrieval:** User/tenant access control is enforced *before* context reaches the prompt.
8. **Least-Privilege Agent Tools:** Tools exposed to models are strictly-typed functions with bounded loops and human approval gates for destructive actions.
9. **Security & Prompt Injection Defenses:** Systems are architected assuming the model *will* be manipulated; secrets are hidden, and outputs are treated as untrusted.
10. **Cost & Latency Controls:** Token caps and latency budgets are enforced with alerts on usage spikes.
11. **Replay Capability:** Production requests can be captured and replayed deterministically in a staging environment to debug poor completions.
12. **Operational Runbook:** Runbook created documenting fallback models, kill switches, and prompt rollback procedures.

---

## 4. Weekly Engineering Habits

Cultivate these micro-habits during everyday development:

- 🗑️ **Delete Dead Code:** If you encounter commented-out code or unused endpoints, delete them immediately.
- 🏷️ **Rename One Confusing Thing:** Improve a misleading variable or function name you had to re-read twice.
- 🧪 **Add a Missing Test:** Write an automated test around an uncovered function you had to modify.
- 📖 **Update One Stale Document:** Fix an outdated README step, comment, or runbook instruction.
- 📦 **Merge a Dependency Update:** Review and merge one automated minor/patch dependency update PR.
- 🎯 **Capture a Production Failure:** Turn a real-world bug or poor LLM output into an automated regression test or golden eval case.
