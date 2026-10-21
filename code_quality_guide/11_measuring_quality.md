# 11. Measuring Quality & Engineering Metrics

> **Module:** Engineering Health, DORA Metrics & Performance Indicators  
> **Source:** Section 12 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [05. AI Engineering](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md) | [10. Dependencies & Observability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/10_dependencies_releases_observability.md)

---

## 1. Principles of Engineering Measurement

Engineering metrics should start constructive team conversations, not punish or evaluate individuals. 

> **Goodhart’s Law:**  
> *"When a measure becomes a target, it ceases to be a good measure."*  
> If you evaluate engineers by lines of code written, you will receive bloated, copy-pasted code. If you evaluate engineers by total closed tickets, tickets will be broken into trivial one-line tasks.

### Core Measurement Principles
- **Measure at the Team Level:** Never track metrics per individual contributor.
- **Watch Trends Over Time:** An individual data point is noise; a 3-month upward or downward trend reveals architectural reality.
- **Pair Counter-Balancing Metrics:** Always pair speed metrics with stability metrics so improving throughput cannot mask quality degradation.

---

## 2. The Four DORA Delivery Metrics

The DevOps Research and Assessment (DORA) metrics represent research-backed measures of software delivery performance:

| DORA Metric | Category | Plain Definition | Target / Industry Benchmark |
| :--- | :--- | :--- | :--- |
| **Deployment Frequency** | Throughput | How frequently code is successfully deployed to production. | Multiple times per week (or on-demand). |
| **Lead Time for Changes** | Throughput | The time elapsed from first commit to production deployment. | Under 1–2 days. |
| **Change Failure Rate** | Stability | The percentage of production deployments requiring a rollback, hotfix, or causing an incident. | Under 5–10%. |
| **Failed-Deployment Recovery Time** | Stability | Time required to restore service after an incident or bad deployment (formerly MTTR). | Under 1 hour (via fast rollback). |

*Note:* Pair **Deployment Frequency** with **Change Failure Rate** to ensure that shipping faster is not destabilizing production.

---

## 3. Code Health & Process Indicators

| Indicator | What It Reveals | Health Warning Threshold | Action to Take |
| :--- | :--- | :--- | :--- |
| **PR Size & Review Time** | Team collaboration velocity and PR review quality. | PRs $> 400$ lines, or reviews taking $> 2$ business days. | Enforce small PR norm; break work into feature-flagged increments. |
| **Test Flakiness Rate** | Trust in the automated test suite. | $> 1\%$ of test runs failing on non-code issues. | Quarantine flaky tests immediately; assign 1-week fix SLA. |
| **Diff Coverage** | Quality and safety of newly merged code. | Changed lines having $< 80\%$ test coverage. | Require unit tests for new logic before PR merge. |
| **Cyclomatic Complexity Trend** | Whether system architecture is growing harder to reason about. | Hotspot functions with complexity $> 10$. | Extract helper functions or parameter objects during feature work. |
| **Dependency Age & CVEs** | Supply-chain hygiene and maintenance debt. | Dependencies un-upgraded for $> 1$ year or open high-severity CVEs. | Enable Dependabot / Renovate; dedicate time in sprint planning. |
| **Git Churn vs. Complexity** | Identifies where bugs cluster in the codebase. | Files changing $> 20$ times in 6 months with high complexity. | Target for characterization tests and Strangler Fig refactoring. |

---

## 4. AI & LLM Quality Metrics

For applications powered by generative AI and LLMs, track these specialized metrics per prompt version and model:

```
┌────────────────────────────────────────────────────────┐
│                   AI System Health                      │
├──────────────────────────┬─────────────────────────────┤
│ Quality & Accuracy       │ • Golden Dataset Eval Score │
│                          │ • Hallucination / Drift %   │
├──────────────────────────┼─────────────────────────────┤
│ Reliability & Robustness │ • Schema Validation Failure %│
│                          │ • Model Refusal / Length %  │
├──────────────────────────┼─────────────────────────────┤
│ Operational Efficiency   │ • Token Cost Per Operation  │
│                          │ • p95 Model Latency (ms)    │
│                          │ • User Feedback (Up/Down)   │
└──────────────────────────┴─────────────────────────────┘
```

- **Validation Failure Rate:** The percentage of model completions that fail schema validation on the first attempt. If $> 5\%$, the prompt instructions or JSON schema require refinement.
- **Truncation Rate:** How often the model hits `max_tokens` before completing valid JSON. A rising rate indicates context window starvation.
- **Cost Per Operation:** Track average token consumption per paper extraction. Sudden spikes signal prompt bloat or unoptimized retrieval context injection.
- **Eval Regression Gate:** A pull request that drops golden evaluation scores below historical baselines cannot be merged without explicit team sign-off.
