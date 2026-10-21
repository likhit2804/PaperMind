# 10. Dependencies, Releases & Observability

> **Module:** Operational Excellence & System Health  
> **Source:** Section 11 of the Revised Code Quality Guide  
> **Related:** [02. Backend Reliability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md) | [08. Documentation](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/08_documentation_standards.md) | [11. Measuring Quality](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/11_measuring_quality.md)

---

## 1. Dependency Hygiene & Supply-Chain Risk

Every third-party dependency is code you now own, execute, and must maintain. Unvetted dependencies introduce security vulnerabilities, license conflicts, and supply-chain attacks.

### Dependency Management Rules
1. **Mandatory Lockfiles:** Always commit exact lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`). In CI and production deployments, strictly install from lockfiles (`pip install --no-deps` or `npm ci`) to guarantee bit-for-bit reproducible builds.
2. **Automated Vulnerability Scanning:** Run `pip-audit` or `npm audit` on every CI build. Block pull requests that introduce known CVEs.
3. **Automate Updates in Small Batches:** Use tools like Dependabot or Renovate. Merge small dependency updates weekly rather than attempting a painful, breaking multi-year upgrade every two years.
4. **Vetting New Packages Before Installation:**
   - Is the repository actively maintained? (Recent commits, responsive maintainers).
   - Is the license compatible with your product? (MIT, Apache 2.0 vs. AGPL).
   - Could this functionality be implemented in 20 lines of your own code instead of importing a 5MB library with 40 transitive dependencies?
5. **Prune Unused Dependencies:** Periodically audit the repo using tools like `deptry` (Python) or `depcheck` (Node.js) to delete dead packages.

---

## 2. Making Change Safe in Production

### Feature Flags: Decoupling Deployment from Release
Feature flags allow engineers to deploy code to production continuously while controlling when functionality is exposed to users.

- **Types of Flags:**
  - *Release Flags:* Temporary flags used to roll out a new feature gradually. Must have an expiration date (e.g., delete 2 weeks post-rollout).
  - *Operational Flags / Kill Switches:* Permanent switches that disable heavy background tasks, third-party rerankers, or expensive LLM steps during upstream outages.
- **Prevent Flag Debt:** Unused, abandoned feature flags clutter code with dead branches and make testing exponential. Every release flag must have an assigned owner and deletion ticket.

### Progressive Delivery & Rollbacks
- **Canary Releases:** Expose new application versions to 5% of traffic first. Monitor error rates, p95 latency, and exception logs before routing 100% of traffic.
- **Make Rollback Boring:** Reverting code, database migrations, prompt versions, or model parameters must be a fast, standard, rehearsed procedure. If rollback requires manual database surgery at 2 AM, the deployment architecture is flawed.

---

## 3. Observability as Maintainability

You cannot maintain, optimize, or debug what you cannot see. Observability is not merely an operations concern; it is a fundamental code quality attribute.

### 1. Structured JSON Logging with Correlation IDs
Every log line emitted in production must be formatted as structured JSON and carry a unique `request_id` (or `correlation_id`). This allows developers to trace an entire user journey across multiple services and async queues.

```python
import logging
import json

logger = logging.getLogger("app")

def log_event(event_name: str, **kwargs):
    payload = {"event": event_name, **kwargs}
    logger.info(json.dumps(payload))

# Production output example:
# {"event": "paper_extraction_started", "request_id": "req_19283", "paper_id": "p_881", "pages": 14}
```

> **Logging Rules:**
> - Log once at the boundary; do not catch and log at every stack layer.
> - Never log passwords, API keys, tokens, or personal identifiable information (PII).

### 2. The Four Golden Signals
Monitor the health of every backend service using the Google SRE Golden Signals:
1. **Latency:** How long does it take to serve requests? (Track p50, p95, and p99).
2. **Traffic:** How much demand is being placed on the system? (HTTP requests/sec).
3. **Errors:** What percentage of requests are failing? (HTTP 5xx rate, unhandled exceptions).
4. **Saturation:** How full are system resources? (CPU, memory, database connection pool usage, queue backlog depth).

### 3. Distributed Tracing (OpenTelemetry)
Instrument network boundaries and LLM calls with OpenTelemetry traces. When a user asks a question to HexiBot, the trace should show the exact time breakdown:
- 40ms: RRF Vector and Keyword Retrieval
- 15ms: PostgreSQL Context Fetch
- 1200ms: Gemini LLM Streaming Completion
- 10ms: Output Validation and JSON Parsing

### 4. Service Level Objectives (SLOs) & Error Budgets
Define clear SLOs in user-facing terms:
> *"99.5% of valid paper extraction requests complete successfully within 15 seconds over any rolling 30-day window."*

The remaining 0.5% represents your **Error Budget**. If the error budget is depleted due to outages, feature delivery slows down and engineering focus pivots immediately to reliability and debt paydown.
