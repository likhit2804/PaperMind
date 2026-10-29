# AGENTS.md — AI Agent Operating Protocol

> **Target Audience:** AI Coding Assistants (Antigravity, Claude, Copilot, Cursor, etc.)  
> **Purpose:** Machine-readable operational instructions for interpreting requirements, selecting relevant guidelines, and applying quality standards to projects safely.

---

## 🚨 MANDATORY INVARIANT: Human-in-the-Loop (HITL) Execution

> **CRITICAL RULE FOR ALL AGENTS:**  
> **NEVER apply changes across multiple guideline files or multiple architectural layers in a single unreviewed batch.**  
> 
> 1. You must execute changes based on **EXACTLY ONE guideline/file or one specific step at a time**.
> 2. Immediately after applying changes for that step, run local verification (lint/test).
> 3. **STOP AND PAUSE.** Present your changes, test results, and rationale to the human user.
> 4. **Wait for explicit human confirmation / approval** before proceeding to the next file or step.

---

## 1. Project & Requirement Triage Decision Tree

When an agent is summoned to improve code quality or apply these standards, follow this triage procedure:

```
                      [User Prompt / Task Received]
                                    │
                                    ▼
                     Step 1: Detect Project Archetype
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
  [AI / LLM System]        [Backend API / Svc]       [Fullstack / Hybrid]
  (Gemini, OpenAI,         (Node, Express,           (e.g., PaperMind:
   LangChain, RAG,         FastAPI, Postgres,         Python Pipeline +
   prompts, vectors)        Redis, Queues)            Node API + React)
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
                     Step 2: Detect Engagement Mode
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
[Mode 1: First-Time Brownfield Adoption]              [Mode 2: Incremental / Later Commits]
"Apply guide to existing project"                     "Add feature", "Fix bug", "Refactor"
         │                                                     │
         ▼                                                     ▼
Follow Section 2: Sequential Phased Rollout          Follow Section 3: Daily Commit Protocol
(1 file at a time + Human approval each)             (Boy Scout rule + Diff coverage)
```

---

## 2. Mode 1: First-Time Application to an Existing Project

When tasked with applying the guide to an already created, active project, execute these steps **strictly in order**. Do **NOT** skip ahead.

### Execution Table for First-Time Adoption

| Step | Objective | Primary Guide File | What the Agent Does | Human-in-the-Loop Gate |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Hotspot & Risk Audit** | [07_refactoring_and_technical_debt.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/07_refactoring_and_technical_debt.md) | Run Git churn + complexity checks to identify the top 5 danger files. Do not change code. | **STOP:** Present hotspot list & proposed priority to user. Wait for confirmation. |
| **2** | **Formatter Baseline** | [03_automated_enforcement.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md) | Run formatter (`ruff format` / `prettier`) across repo in a single dedicated commit. Add commit SHA to `.git-blame-ignore-revs`. | **STOP:** Show git blame ignore setup & diff count to user. Wait for approval. |
| **3** | **Linter with Baseline** | [03_automated_enforcement.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md) | Configure Ruff/ESLint. Record existing violations in a baseline file so legacy code doesn't block CI. Enforce zero warnings on *new* files. | **STOP:** Verify baseline generation. Show config to user. Wait for approval. |
| **4** | **12-Factor Typed Config** | [09_project_structure_and_design.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/09_project_structure_and_design.md) | Replace loose `process.env` / `os.getenv` with a validated settings class (`pydantic-settings`). Wrap secrets in `SecretStr`. | **STOP:** Run startup test with valid and missing env vars. Present to user. Wait for approval. |
| **5** | **Outbound Call Timeouts** | [02_backend_reliability_patterns.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md) | Audit all HTTP/DB/LLM network calls. Add explicit connect and read timeouts. Add jittered retries on transient errors. | **STOP:** Present list of protected endpoints and timeout configurations. Wait for approval. |
| **6** | *(If AI Project)* **Fenced AI Layer** | [05_ai_engineering_practices.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md) | Extract inline prompts into versioned files (`prompts/`). Add Pydantic schema validation for model output with 1-retry repair. Create fake LLM for tests. | **STOP:** Run pipeline tests using `FakeLLM`. Present prompt structure to user. Wait for approval. |
| **7** | **Pre-Commit & CI Setup** | [03_automated_enforcement.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md) | Install `.pre-commit-config.yaml` (fast format, lint, secret scan) and create parallel GitHub Actions CI workflow. | **STOP:** Run pre-commit hooks locally. Present CI config to user. Wait for approval. |

---

## 3. Mode 2: Targeted Tasks & Later Commits

When the user asks you to implement a feature, fix a bug, or refactor code in an existing project where the guide is already established:

### Task Type Routing Matrix

| Task Type | Files to Consult & Apply | What the Agent Must Do |
| :--- | :--- | :--- |
| **Fixing a Bug** | • [04_testing_strategy.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/04_testing_strategy.md)<br>• [01_clean_code_fundamentals.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) | 1. Write an automated regression test reproducing the defect.<br>2. Apply minimal fix using guard clauses and specific exceptions.<br>3. Verify test passes.<br>4. Stop and request user review. |
| **Adding a Backend Endpoint / Database Query** | • [02_backend_reliability_patterns.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md)<br>• [09_project_structure_and_design.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/09_project_structure_and_design.md) | 1. Add request schema validation at outer controller boundary.<br>2. Ensure explicit timeouts and idempotency key handling.<br>3. Prevent N+1 queries using batch lookups.<br>4. Stop and request user review. |
| **Modifying or Adding an AI/LLM Feature** | • [05_ai_engineering_practices.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md)<br>• [13_checklists_and_cheat_sheets.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/13_checklists_and_cheat_sheets.md) | 1. Bump prompt version and add entry to `prompts/CHANGELOG.md`.<br>2. Validate output through strict schema with bounded repair loop.<br>3. Test with `FakeLLM` in unit tests.<br>4. Run smoke eval and attach score diff.<br>5. Stop and request user review. |
| **Refactoring Legacy Code** | • [07_refactoring_and_technical_debt.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/07_refactoring_and_technical_debt.md)<br>• [04_testing_strategy.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/04_testing_strategy.md) | 1. Write characterization test recording current behavior.<br>2. Apply micro-refactoring (e.g. replace conditional with table).<br>3. Verify tests pass.<br>4. Stop and request user review. |

---

## 4. Mandatory Verification Checklist Before Requesting User Review

Before the agent pauses to ask for user approval, it must complete this internal checklist:

```markdown
- [ ] Did I apply changes based strictly on ONE guideline file/step?
- [ ] Did I run local linting / typecheck / tests to ensure zero regressions?
- [ ] Are all new network calls protected with explicit timeouts?
- [ ] Are all exceptions specific (no bare `except:` or `catch (e) {}`)?
- [ ] Did I format the output to show:
      1. Which guideline was applied
      2. Files touched
      3. Verification / test command results
      4. Clear prompt asking the user for permission to proceed
```

---

## 5. Standard Output Template for Agents

Whenever an agent finishes applying changes for a step, use this structured response format:

```markdown
### 🛠️ Completed Step: [Step Name, e.g., Phase 2 — Formatter Baseline]
- **Guideline Applied:** `code_quality_guide/[file_name.md]`
- **Files Modified:**
  - `path/to/file1.ext` (Explanation of change)
  - `path/to/file2.ext` (Explanation of change)

### 🧪 Verification Output:
- Ran: `ruff check .` -> ✅ Passed (0 errors)
- Ran: `pytest tests/unit` -> ✅ Passed (14 tests passed in 0.42s)

### 🛑 Human-in-the-Loop Checkpoint:
Please review the changes above. Once you confirm these changes look good, let me know and I will proceed to **[Next Step Name, e.g., Phase 3 — Linter with Baseline]**.
```
