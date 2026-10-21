# 12. Team Adoption Roadmap

> **Module:** Organizational Rollout & Change Management  
> **Source:** Section 13 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [03. Automated Enforcement](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md) | [07. Refactoring](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/07_refactoring_and_technical_debt.md)

---

## 1. Core Principles of Adoption

You cannot do everything at once. A team that is instructed to change every habit simultaneously changes nothing. Three practical principles make standards stick:

1. **Start with Pain:**  
   Begin with the issues developers already complain about: flaky builds, 3-day PR review bottlenecks, or recurring weekend outages. When improvements eliminate real developer frustration, the team champions the new standards.
2. **Make the Right Thing the Easy Thing:**  
   Automated tools, templates, and pre-commit scripts beat reminders, nagging, and Slack arguments every time.
3. **Ratchet, Do Not Big-Bang:**  
   Hold new code to the high standard, improve legacy files incrementally when touched, and measure progress over time.

---

## 2. The Recommended Chronological Adoption Timeline

| Milestone | Key Action Items | Practical Notes |
| :--- | :--- | :--- |
| **Week 1** | • Add code formatter (`ruff format` / `prettier`).<br>• Add linter and run in CI.<br>• Commit all formatting changes in a single commit added to `.git-blame-ignore-revs`. | Maximum payoff for the least effort. Baselined so legacy warnings do not block builds. |
| **Weeks 2–3** | • Add type checking on all new and modified code.<br>• Setup pre-commit hooks for fast checks.<br>• Standardize developer commands via a `Makefile` or `npm run` scripts. | Relax strict type rules per legacy module rather than disabling globally. |
| **Month 1 (Core)** | • Implement standardized PR description template.<br>• Adopt Conventional Commits.<br>• Enable GitHub branch protection.<br>• Write a newcomer-friendly README.<br>• Audit outbound network calls for missing timeouts. | Focus human reviews on design and correctness. |
| **Month 1 (AI Focus)** | • Wrap provider SDKs behind a single `LLMClient` protocol.<br>• Move prompts out of strings into versioned files.<br>• Implement schema validation on all model outputs with bounded 1-retry repair.<br>• Assemble initial 20–50 case golden evaluation dataset. | **Do not delay this step:** Retrofitting untracked prompts and unmeasured LLM outputs is extremely difficult once scaled. |
| **Month 2** | • Raise test quality around core revenue/permission paths.<br>• Mandate regression tests for all bug fixes.<br>• Parallelize CI pipeline jobs to keep builds under 8 minutes.<br>• Introduce automated secret and dependency CVE scanning. | Use characterization tests when touching legacy modules without tests. |
| **Month 3** | • Begin writing Architecture Decision Records (ADRs) for non-trivial choices.<br>• Create operational runbooks for top production alerts.<br>• Establish a visible Technical Debt Register.<br>• Formulate initial Service Level Objectives (SLOs). | Write the first runbook for the alert that last paged an on-call engineer. |
| **Ongoing** | • Refactor top 2–3 churn/complexity hotspots per quarter.<br>• Review DORA and quality metrics monthly.<br>• Rehearse model upgrades and prompt rollbacks.<br>• Conduct blameless incident retrospectives.<br>• Reserve steady 10–20% capacity for debt paydown. | Sustainable, high-velocity engineering habits. |

---

## 3. Adopting Standards on an Existing Codebase

When introducing these guidelines to an active, established project:

1. **Stabilize the Pipeline First:** Make CI fast, reliable, and deterministic. Nothing else sticks while the build is red, slow, or flaky.
2. **Freeze the Baseline:** Record existing lint and type errors into a baseline file. Configure CI to fail **only on new violations or modified lines**.
3. **Protect Critical Areas:** Write characterization and integration tests around the code handling authorization, billing, data parsing, and external mutations.
4. **Fix on Touch (Boy Scout Rule):** When an engineer modifies a file for a feature, they bring that file into compliance proportionally.
5. **Target 2–3 Hotspots per Quarter:** Use Git churn and cyclomatic complexity to identify the highest-risk files and refactor them deliberately.
6. **Retire, Do Not Rewrite:** Use the Strangler Fig pattern for legacy modules that are too fragile to refactor in-place.
