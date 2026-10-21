# 08. Documentation Standards

> **Module:** Architecture Records & Living Documentation  
> **Source:** Section 9 of the Revised Code Quality Guide  
> **Related:** [06. Code Review](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/06_code_review_and_collaboration.md) | [09. Project Structure](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/09_project_structure_and_design.md) | [10. Dependencies & Observability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/10_dependencies_releases_observability.md)

---

## 1. Core Documentation Philosophy

Document what the code **cannot say**: historical intent, rejected alternatives, business context, operational procedures, and incident recovery instructions. 

> Documentation that merely restates the code falls out of date quickly and actively misleads engineers.

---

## 2. README: The Onboarding Gateway

Every repository must contain a high-quality `README.md`. A new engineer should be able to clone the repository and get a fully functional development environment running using the README alone.

### Required README Sections
1. **Project Vision & Target Audience:** What does this project do in 2 sentences?
2. **Local Setup in 2 Commands:** (e.g., `make setup && make run` or Docker setup).
3. **Running Verification Commands:** How to run linters, tests, and AI evaluation suites.
4. **Directory Structure Overview:** Where key logic resides and where a newcomer should look first.
5. **Contributing Guidelines & Ownership:** Who owns the repository and how to submit pull requests.
6. **Links to Deep Documentation:** Pointers to ADRs, API specs, and runbooks.

---

## 3. Architecture Decision Records (ADRs)

An **Architecture Decision Record (ADR)** captures a significant architectural choice: the problem context, the decision made, the alternatives evaluated, and the consequences. 

Store ADRs directly in the Git repository (`docs/adr/0007-use-pgvector.md`) so that they are version-controlled alongside the code. When a future developer asks *"Why on earth did we build it this way?"*, the ADR provides the complete historical context.

### Standard ADR Template

```markdown
# ADR-0007: Use pgvector Instead of a Dedicated Vector Database

- **Status:** Accepted
- **Date:** 2026-03-12
- **Deciders:** Backend & AI Team

## Context
We need semantic vector search over approximately 2,000,000 document chunk embeddings. 
Our team has 4 engineers, we currently operate PostgreSQL in production, and query volume 
is moderate (tens of queries per second at peak).

## Decision
We will use the `pgvector` extension with an HNSW index within our existing PostgreSQL database cluster.

## Alternatives Evaluated
- **Managed Vector Database (Pinecone/Qdrant Cloud):** Excellent performance at scale, but introduces an additional vendor, external billing, and a separate data silo for an initial workload we can comfortably serve today.
- **Dedicated Self-Hosted Vector Store (Milvus):** High operational overhead for a 4-person engineering team.

## Consequences & Tradeoffs
- **Positive:** Simplifies operations, unifies database backups, and guarantees ACID transactional consistency between document text and its embeddings.
- **Negative:** Vector queries compete with relational queries for database CPU and RAM.
- **Trigger to Revisit:** Re-evaluate if document chunks exceed 20M, if p95 vector latency exceeds 200ms under load, or if complex metadata filtering exceeds pgvector capabilities.
```

### Essential ADR Rules
- **One Page, One Decision:** Keep each record concise and focused.
- **Never Rewrite History:** When a past decision changes, write a new ADR that supersedes the previous one (e.g., *Status: Superseded by ADR-0012*).
- **Good AI ADR Topics:** Model selection and pinning strategies, vector chunking algorithms, eval methodologies, LLM prompt caching vs. response caching, and agent tool execution permissions.

---

## 4. RFCs and Design Documents

An **RFC (Request for Comments)** explores a large, ambiguous problem and proposes a technical solution **before** significant code is written, inviting team feedback and alignment.

| Dimension | RFC / Design Document | Architecture Decision Record (ADR) |
| :--- | :--- | :--- |
| **Purpose** | Explore, debate, and persuade before building. | Record the decision permanently after it is agreed upon. |
| **Length** | Comprehensive (3–10 pages). | Concise (~1 page). |
| **Lifecycle** | Active during debate; archived after implementation. | Permanent repository fixture; superseded rather than edited. |
| **When to Use** | High-risk, multi-month, or cross-team initiatives. | Any architectural choice costly to reverse. |

---

## 5. Operational Runbooks

A runbook is a practical, step-by-step emergency guide for mitigating an alert. 

> **Writing Standard:** Write runbooks for an exhausted on-call engineer at 3:00 AM who has never seen this alert before. Link every alert in your monitoring dashboard directly to its runbook.

### Standard Runbook Template

```markdown
# Runbook: High Semantic Search Latency

## Alert Description
p95 latency of the `/api/v1/search` endpoint exceeded 2.0 seconds for 10 consecutive minutes.

## Business Impact
Users experience severe UI lag or timeouts when querying research papers. Ingestion is unaffected.

## Triage & Diagnostics
1. Open the **Search Overview Dashboard**: Is the latency bottleneck in the vector database query or the Gemini LLM completion?
2. Check LLM provider status page and our outbound HTTP 429 rate-limit metrics.
3. Check PostgreSQL connection pool saturation and CPU utilization (`pg_stat_activity`).

## Immediate Mitigation
- **If LLM Provider is Degrading:** Toggle the feature flag `search.enable_fast_fallback_model` to route queries to our lightweight secondary model.
- **If Database CPU is Saturated:** Toggle feature flag `search.disable_reranker` to skip the secondary cross-encoder step and reduce database load.

## Escalation Path
If latency remains unmitigated after 30 minutes, page the Secondary Backend Lead.

## Post-Incident Action
File a blameless postmortem if user disruption exceeded 15 minutes.
```

---

## 6. Living Documentation Standards

- **OpenAPI / Swagger:** Generate API documentation automatically from typed schemas (Pydantic / FastAPI / Swagger Express) so docs cannot drift from real code.
- **Diagrams as Code (Mermaid):** Embed Mermaid diagrams in Markdown files so architecture diagrams are version-controlled and reviewed during pull requests.
- **Blameless Postmortems:** Write postmortems after significant outages covering:
  - Incident timeline and detection lag.
  - Multiple root causes (incidents never have a single root cause).
  - Remediation actions with explicit owners and completion dates.
- **AI Feature Documentation:** Document prompt versions running in production, temperature and token limits, golden eval baseline scores, and safety fallback mechanisms.
