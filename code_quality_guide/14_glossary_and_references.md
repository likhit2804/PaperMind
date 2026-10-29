# 14. Glossary & Annotated References

> **Module:** Architectural Lexicon & Curated Reading List  
> **Source:** Section 15 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [README Hub](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/README.md)

---

## 1. Comprehensive Engineering Glossary

- **ADR (Architecture Decision Record):** A lightweight document capturing an architectural decision, its context, alternatives considered, and consequences.
- **Backpressure:** Throttling, rejecting, or shedding incoming load when a system is overwhelmed rather than allowing memory or queues to expand unboundedly.
- **Boy Scout Rule:** The habit of leaving any file you touch cleaner than you found it.
- **Bulkhead:** An isolation pattern partitioning resources (connection pools, memory, threads) so that an outage in one feature cannot consume all system capacity.
- **Canary Release:** Exposing a newly deployed software version to a small percentage of real traffic before rolling it out globally.
- **Characterization Test:** An automated test that records the existing behavior of legacy code as an immutable safety harness prior to refactoring.
- **Circuit Breaker:** A resilience wrapper that halts calls to an external failing dependency for a cooldown period before probing recovery.
- **Code Smell:** A surface-level symptom in source code that indicates a deeper architectural or design flaw.
- **Composition Root:** The single location in an application (usually `main.py` / `server.js`) where concrete dependencies are instantiated and wired together.
- **Conventional Commits:** A structured commit message specification (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- **Cyclomatic Complexity:** A metric counting the number of linearly independent execution paths through a block of code.
- **Dead-Letter Queue (DLQ):** A secondary queue where messages that repeatedly fail processing are parked for diagnostic inspection.
- **Diff Coverage:** The percentage of newly written or modified lines covered by automated tests within a pull request.
- **DORA Metrics:** Research-backed software delivery metrics (Deployment Frequency, Lead Time for Changes, Change Failure Rate, Failed-Deployment Recovery Time).
- **DRY (Don't Repeat Yourself):** Every piece of business knowledge must have a single, unambiguous representation within a system.
- **Eval (Evaluation):** An automated, repeatable measurement of AI model output quality against a curated dataset and scoring rubric.
- **Expand and Contract:** A zero-downtime database migration pattern where new columns are added, dual-written, backfilled, and then deprecated old columns are removed.
- **Fake:** A lightweight, working in-memory implementation of an interface contract used in automated tests (e.g., `InMemoryUserRepository`, `FakeLLMClient`).
- **Feature Flag:** A configuration switch enabling behavior to be enabled or disabled dynamically without deploying new code.
- **Golden Dataset:** A curated, version-controlled set of inputs with verified expected outputs used to benchmark AI model performance.
- **Golden Signals:** The four vital metrics of service monitoring: Latency, Traffic, Errors, and Saturation.
- **HNSW (Hierarchical Navigable Small World):** A graph-based indexing algorithm used for fast approximate nearest-neighbor vector similarity search.
- **Idempotency:** A property where executing an operation multiple times produces the identical side-effect and outcome as executing it once.
- **Keyset Pagination:** Paginating database records using the last seen primary key (`WHERE id > :last_id LIMIT 50`) rather than expensive `OFFSET` scans.
- **KISS (Keep It Simple, Stupid):** Prioritizing simple, understandable designs over clever, complicated abstractions.
- **LLM-as-Judge:** Using a capable frontier model to evaluate another model's completions against an explicit rubric.
- **N+1 Query Problem:** An ORM anti-pattern where an application executes 1 initial query to fetch a list of entities and then executes $N$ subsequent queries to fetch child data.
- **Outbox Pattern:** Writing events to an `outbox` database table within the same ACID transaction as the business entity, ensuring guaranteed message publishing.
- **Prompt Injection:** An attack where untrusted text read by an LLM overrides system instructions to hijack model execution.
- **Property-Based Testing:** Testing system invariants across hundreds of randomized inputs rather than hardcoding static example inputs.
- **RAG (Retrieval-Augmented Generation):** Enhancing model generation by retrieving relevant domain documents from a vector or keyword index and injecting them into the prompt.
- **Ratchet:** A quality adoption strategy that records existing violations as a baseline and fails CI strictly on new or modified violations.
- **Refactoring:** Restructuring internal software architecture without altering external observable behavior.
- **RFC (Request for Comments):** A comprehensive design document proposing a major architectural change before code implementation begins.
- **Runbook:** Step-by-step diagnostic and remediation instructions for on-call engineers resolving specific production alerts.
- **SLO (Service Level Objective):** A measurable target for system reliability defined in user-centric terms (e.g., 99.5% success rate).
- **SOLID:** Five object-oriented design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion.
- **Strangler Fig Pattern:** Incrementally replacing a legacy monolithic system by deploying new features behind a facade until the old system is completely drained.
- **Technical Debt:** The implied future cost of additional rework caused by choosing an expedient, shortcut solution today over an architecturally sound approach.
- **Twelve-Factor App:** Architectural best practices for building scalable, portable, and cloud-native backend services.
- **YAGNI (You Aren't Gonna Need It):** The principle of refusing to write speculative functionality until concrete requirements demand it.

---

## 2. Annotated Recommended Reading

- **Refactoring** *(Martin Fowler)* — The definitive catalog of code refactoring patterns and the foundational reasoning behind safe restructuring.
- **Clean Code** *(Robert C. Martin)* — Influential guidance on naming, small functions, and readability. Read critically, as some dogmatic rules are debated.
- **A Philosophy of Software Design** *(John Ousterhout)* — A brilliant modern counterweight emphasizing deep modules, red flags, and managing cognitive complexity.
- **Working Effectively with Legacy Code** *(Michael Feathers)* — The master guide on introducing characterization tests, identifying seams, and safely modifying legacy codebases.
- **Designing Data-Intensive Applications** *(Martin Kleppmann)* — Essential reading on distributed systems, data consistency, transactions, replication, and messaging architectures.
- **Release It!** *(Michael Nygard)* — The canonical reference on production resilience: timeouts, circuit breakers, bulkheads, and stability patterns.
- **Accelerate** *(Nicole Forsgren, Jez Humble, Gene Kim)* — The rigorous scientific research behind the DORA metrics and high-performing engineering organizations.
- **Site Reliability Engineering (SRE)** *(Google Engineering)* — Google's foundational playbook for SLOs, error budgets, blameless postmortems, and on-call operational hygiene.
- **OWASP Top 10 for LLM Applications** *(OWASP Foundation)* — The primary security standard for prompt injection, data leakage, and insecure tool use in AI systems.

---

## 3. Closing Philosophy

Code quality is not a one-time event, an annual sprint, or an aesthetic ideal. It is a set of **small, consistent daily habits backed by automated tooling**.

Start with the automated tools that eliminate style debates. Make failure handling, timeouts, and measurement explicit—especially around non-deterministic AI components. Build a collaborative, blameless review and testing culture, and record significant decisions as you build.

> The ultimate goal is simple: **a production codebase where software change is fast, safe, and inexpensive.**
