# 06. Code Review & Collaboration

> **Module:** Team Processes, PRs & Peer Review  
> **Source:** Section 7 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [01. Clean Code](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) | [03. Automated Enforcement](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md)

---

## 1. Writing High-Quality Pull Requests

A pull request is an asynchronous proposal to change a shared production system. A well-crafted PR respects your teammates' time and accelerates time-to-merge.

### Guidelines for Authors
1. **Keep Pull Requests Small (< 300 Lines of Code):**  
   *Heuristic:* Review quality degrades sharply above 300–400 changed lines. Massive PRs receive superficial "LGTM" rubber stamps that conceal subtle edge-case bugs. Split large features into a sequence of stacked PRs or feature-flagged increments.
2. **One Logical Purpose Per PR:**  
   Never bundle a 400-line code formatting or refactoring change with a 10-line feature or bug fix. Ship the refactor in PR #1, verify CI stability, and ship the feature in PR #2.
3. **Conduct a Thorough Self-Review First:**  
   Before requesting review, read your own entire Git diff line by line on GitHub. Authors catch an estimated 30–40% of their own mistakes simply by viewing their diff from a reviewer’s perspective.
4. **Attach Evidence:**  
   Include local test outputs, terminal logs, UI screenshots, database query plans (`EXPLAIN ANALYZE`), or evaluation score diffs for prompt changes.
5. **Open Draft PRs Early for Architecture Direction:**  
   If unsure about an architectural approach, open an early Draft PR with interface stubs to solicit directional feedback before spending days writing implementation details.

---

## 2. Standard Pull Request Template

Place this file at `.github/pull_request_template.md`:

```markdown
## What and Why
<!-- Briefly explain the business requirement, architectural motivation, or bug being addressed. Link related tickets. -->

## How It Was Tested
<!-- Detail the test steps executed. Mention unit/integration tests added. -->

## Risks, Rollout & Rollback
<!-- Are there database migrations? Feature flags? External API impacts? What is the rollback plan if production errors spike? -->

## Checklist
- [ ] Tests added or updated (including regression test if fixing a bug)
- [ ] Documentation, README, or Architecture Decision Record (ADR) updated if applicable
- [ ] For AI/LLM changes: Prompt version bumped, changelog updated, smoke evals run and results attached
- [ ] No secrets, credentials, or sensitive test data included
```

---

## 3. The Art of Effective Code Review

Let automated linters, formatters, and type checkers handle mechanical rules so that human reviewers can dedicate their mental energy to things machines cannot judge.

### The 5-Stage Hierarchy of Code Review
Review code strictly in this order; a fatal flaw in an earlier stage renders feedback on later stages pointless:

```
1. Architecture & Design ──► Does this approach fit system constraints? Is it the right abstraction?
          │
          ▼
2. Correctness & Logic ────► Edge cases, concurrency races, error handling, backward compatibility.
          │
          ▼
3. Automated Tests ────────► Are failure modes covered? Is there a regression test?
          │
          ▼
4. Readability & Names ────► Do function names and domain concepts reflect true intent?
          │
          ▼
5. Nits & Micro-style ─────► Non-blocking stylistic preferences (always label as "nit:").
```

---

## 4. Clear & Constructive Review Communication

Feedback should be objective, educational, and focused on the code rather than the person.

### Standardized Comment Prefixes
Use explicit prefixes on review comments so the author immediately knows the priority of the request:

- `blocking:` A mandatory requirement. Code cannot be merged until resolved (e.g., security flaw, missing timeout, data loss risk).
- `suggestion:` A recommended improvement or refactoring idea. The author may adopt it or explain why an alternative was chosen.
- `question:` A request for clarification or explanation of tradeoffs.
- `nit:` A minor cosmetic preference. Non-blocking; the author may ignore or adopt at their discretion.

### Examples of Weak vs. Constructive Feedback

| Weak Comment | High-Impact Constructive Feedback |
| :--- | :--- |
| *"This function is too confusing."* | `suggestion: process_paper()` mixes PDF stream parsing with database writes. Extracting the parser into a pure function would let us test it without a test database. |
| *"Wrong error handling."* | `blocking:` Catching bare `except:` here swallows `KeyboardInterrupt` and hides missing file errors. Can we catch `FileNotFoundError` specifically and log the missing path? |
| *"Why didn't you use Redis?"* | `question:` What was the tradeoff for using an in-memory dictionary instead of Redis here? Just want to understand if we need to support multi-instance horizontal scaling. |

### Resolving Review Deadlocks
If a comment thread exceeds two rounds of back-and-forth debate:
1. **Switch to Synchronous Discussion:** Hop on a quick 5-minute call or pair in person.
2. **Record the Resolution:** Summarize the agreed-upon decision in the PR comments for future reference.

---

## 5. Reviewing AI-Assisted Code

When reviewing code generated by AI coding assistants:
- **The Human Author Retains 100% Responsibility:** *"The AI generated it"* is never an acceptable explanation for buggy, insecure, or unmaintainable code.
- **Watch for Hallucinated APIs:** Verify that all library methods and external parameters actually exist in the installed package versions.
- **Check Missing Edge Cases:** AI assistants excel at generating happy-path code but routinely omit network timeouts, connection drop retries, and boundary validation.
- **Beware of Tautological Tests:** Ensure generated unit tests genuinely assert system behavior rather than mirroring the mock implementation.

---

## 6. Shared Team Conventions

### Conventional Commits
Enforce the Conventional Commits specification (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). This structure enables automated changelog generation, clean Git bisect operations, and searchable repository histories.

### Definition of Done (DoD)
A shared team definition of when a feature is truly "done":
- Code compiles, formats, and passes all linter and type checks.
- Unit and integration tests pass with required diff coverage.
- PR approved by at least one designated peer.
- Documentation or runbooks updated for operational alerts.
- Feature deployed behind a temporary release flag where appropriate.
