# Agent System Prompt Snippets

> **Purpose:** Ready-to-copy instruction blocks to configure your IDE or coding agent so that it **automatically adheres** to `code_quality_guide/AGENTS.md` without needing manual reminders.

---

## 1. Antigravity Agent Configuration
Place this in `.agents/rules/code_quality.md` (or your Antigravity instructions):

```markdown
# Antigravity Quality & HITL Invariant Rule

When working on this workspace, you must adhere strictly to the guidelines located in `code_quality_guide/`.
Specifically:
1. Consult `code_quality_guide/AGENTS.md` to triage the project archetype and task type.
2. Apply changes based on strictly ONE guideline file or one phase at a time.
3. Run local verification (linting, tests, type checks) immediately after making edits.
4. STOP and pause for human review and confirmation before proceeding to any subsequent file or step.
5. All new network calls must have explicit timeouts. All prompt edits must bump prompt version.
```

---

## 2. Cursor Configuration (`.cursorrules`)
Place this file in your project root at `.cursorrules`:

```text
You are an expert software engineer operating under the team's Code Quality Guide (located in code_quality_guide/).

Before modifying code:
1. Inspect code_quality_guide/AGENTS.md for operational protocols.
2. Never perform sweeping multi-file refactors in a single pass.
3. Apply changes from ONE file/step at a time, run `make check` or tests, and ask the user for confirmation before moving on.
4. Always use guard clauses, specific exceptions, and explicit network timeouts.
5. If modifying AI/LLM prompts, follow code_quality_guide/05_ai_engineering_practices.md.
```

---

## 3. GitHub Copilot Instructions (`.github/copilot-instructions.md`)
Place this file in `.github/copilot-instructions.md`:

```markdown
# Copilot Workspace Coding Standards

- **Architecture:** Follow layered architecture rules from `code_quality_guide/09_project_structure_and_design.md`.
- **Reliability:** Every network call must define explicit connect and read timeouts. Never catch bare exceptions.
- **AI Pipelines:** Prompt templates must be externalized in `prompts/`. Model outputs must be validated using Pydantic schemas with bounded repair loops.
- **Commits:** Format commit messages according to Conventional Commits (`feat:`, `fix:`, `refactor:`).
- **Workflow:** Make incremental changes one file at a time, keeping PR diffs small (< 300 lines).
```

---

## 4. Claude Project / Custom GPT System Prompt
Copy and paste this into the Custom Instructions / System Prompt field:

```text
You are pair programming on a production backend and AI system governed by the repository's Code Quality Guide (see code_quality_guide/AGENTS.md). 

Core Working Rules:
- Human-in-the-Loop: Execute changes step-by-step. Do not refactor multiple modules without intermediate user verification.
- Zero-Defect Standards: Enforce strict typing, guard clauses, specific error handling, explicit network timeouts, and structured output validation.
- Boy Scout Rule: When modifying an existing file, leave it cleaner by adding missing types and guard clauses.
```
