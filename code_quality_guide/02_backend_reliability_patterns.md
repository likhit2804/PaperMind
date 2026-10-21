# 02. Backend Reliability Patterns

> **Module:** Production Reliability & Resilience  
> **Source:** Section 3 of the Revised Code Quality Guide  
> **Related:** [01. Clean Code](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) | [05. AI Engineering](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md) | [10. Dependencies & Observability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/10_dependencies_releases_observability.md)

---

## 1. Introduction: Why Systems Fail in Production

Most serious backend outages do not stem from complex algorithmic bugs. They occur because of how code behaves when its surrounding ecosystem experiences partial degradation: a slow external API, a dropped network packet, a duplicate webhook delivery, or a database connection pool starvation.

Writing maintainable backend code means designing for partial failure deliberately and consistently.

---

## 2. Timeouts on Every Network Call

Many network libraries (including Python `requests` and Node HTTP clients) wait indefinitely by default. A single slow dependency without an explicit timeout can tie up all worker threads or event loop connections, bringing down an otherwise healthy service.

### Essential Rules
1. **Explicit Timeouts Everywhere:** Outbound HTTP, database queries, Redis caches, message brokers, and LLM endpoints.
2. **Separate Connect vs. Read Timeouts:** Connect timeouts should be fast (1–2 seconds) because TCP handshakes are swift. Read timeouts should be sized to the specific operation.
3. **Database Statement Timeouts:** Always configure `statement_timeout` and lock timeouts in your database connection pool so a single runaway query cannot lock tables indefinitely.
4. **Deadline Propagation:** If a user request has a 5-second SLA, downstream calls executed 3 seconds into the request must not be permitted a 10-second timeout.
5. **LLM Calls:** LLMs legitimately take longer (5–30 seconds). Use appropriate read timeouts, enable token streaming where applicable, and maintain a hard global cap.

```python
import httpx

# Proper explicit timeout configuration
client = httpx.Client(
    timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
)
```

---

## 3. Retries with Exponential Backoff and Jitter

Retries turn transient blips into invisible non-events. However, naive retries act as a distributed denial-of-service attack against a struggling dependency.

### Retry Rules
- **Retry Only Transient Failures:** Network resets, DNS timeouts, HTTP 429 (Too Many Requests), 502, 503, and 504. **Never retry 4xx client errors** (400, 401, 403, 404, 422).
- **Retry Only Idempotent Calls:** Retrying a non-idempotent call (`POST /charge_credit_card`) risks charging a customer multiple times unless protected by an idempotency key.
- **Always Add Full Jitter:** Add randomized delay so multiple competing clients do not retry in synchronized lockstep.
- **Cap Attempts & Elapsed Time:** Limit to 3–4 attempts; respect upstream `Retry-After` response headers.
- **Retry at One Layer Only:** If three stacked layers each retry 3 times, a single failure cascades into $3 \times 3 \times 3 = 27$ calls against a failing dependency.

```python
import random
import time
from typing import Callable, TypeVar

T = TypeVar('T')

def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay_s: float = 0.5,
    max_delay_s: float = 8.0,
    retry_on: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == attempts:
                raise
            # Exponential backoff with Full Jitter
            ceiling = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
            sleep_duration = random.uniform(0, ceiling)
            time.sleep(sleep_duration)
```

> **Recommendation:** In production codebases, use a standard library like `tenacity` (Python) or `p-retry` (Node.js), but keep the policy centralized so all services behave consistently.

---

## 4. Idempotency

An operation is idempotent if performing it multiple times produces the exact same outcome as performing it once. Because networks, message queues, and users deliver duplicates, all state-changing endpoints must be idempotent.

### Implementing Idempotency Keys
1. Require an `Idempotency-Key` header on state-changing endpoints (`POST /api/v1/extract`).
2. Store the key in a database table alongside a hash of the request payload and the resulting response.
3. Enforce uniqueness with a **database unique constraint**. Never use application-level "check-then-insert" logic, which races under concurrent requests.
4. If a duplicate key arrives with an identical body, return the cached previous response. If it arrives with a different body, reject with HTTP 409 Conflict.

```python
def create_payment(request: PaymentRequest, idempotency_key: str) -> Payment:
    try:
        with db.transaction():
            return payments.insert(request, idempotency_key=idempotency_key)
    except UniqueViolation:
        # A concurrent or previous request already processed this key
        return payments.get_by_key(idempotency_key)
```

---

## 5. Transactions & Data Consistency

- **Transaction Boundaries Belong in the Service Layer:** Never open transactions in HTTP controllers or low-level repositories. The service layer defines the single logical unit of work.
- **Keep Transactions Short:**
  > ⚠️ **CRITICAL WARNING:** Never execute an outbound HTTP request, file upload, or LLM call inside an open database transaction! It holds open database connections and locks while waiting on an unpredictable external network.
- **The Dual-Write Problem & Transactional Outbox:**  
  Updating a database table and publishing a message to a queue in two separate steps leads to data inconsistency if the process crashes between writes.  
  *Solution:* Write the event to an `outbox` table within the same database transaction. A separate background worker safely reads and relays outbox records.
- **Optimistic Locking:** Protect concurrent updates using a `version` column or conditional atomic update rather than application read-modify-write loops:
  ```sql
  UPDATE accounts 
  SET balance_cents = balance_cents - 500, version = version + 1
  WHERE id = 42 AND version = 3 AND balance_cents >= 500;
  ```

---

## 6. Database Access & Schema Evolution

### Eliminate N+1 Queries
Loading a parent entity and subsequently issuing a query for every child item in a loop destroys database performance. It often goes unnoticed in development datasets but cripples production.

```python
# ❌ N+1 Query Anti-Pattern: 1 query for orders + N queries for items
orders = repo.list_orders(customer_id)
for order in orders:
    order.items = repo.list_items(order.id)

# ✅ Efficient Batch Query: Exactly 2 queries total
orders = repo.list_orders(customer_id)
order_ids = [o.id for o in orders]
items_by_order = repo.list_items_for_orders(order_ids)
```

### Additional Database Rules
- **Index Hot Paths:** Add indexes on columns used in `WHERE`, `JOIN`, and `ORDER BY` clauses; verify with `EXPLAIN ANALYZE`.
- **Keyset Pagination:** Replace slow `OFFSET` pagination (`OFFSET 100000`) with keyset pagination (`WHERE id > :last_id ORDER BY id ASC LIMIT 50`).
- **Connection Pools:** Size pools to ensure total connections across all container instances do not exceed database connection limits.

### Zero-Downtime Schema Migrations (Expand and Contract)
Never deploy a migration requiring atomic deployment of application code and database schemas. Follow the 5-step lifecycle:
1. **Expand:** Add the new column/table as nullable or with defaults. Old code continues functioning.
2. **Deploy Dual-Write Code:** Application writes to both old and new columns.
3. **Backfill:** Backfill historical data in small off-peak batches.
4. **Switch Reads:** Update code to read from the new structure and verify stability.
5. **Contract:** Remove deprecated code paths, then drop the legacy column in a subsequent release.

---

## 7. Concurrency & Async Best Practices

- **Never Block the Event Loop:** In async runtimes (FastAPI/asyncio, Node.js), never execute synchronous CPU-heavy algorithms or blocking file/network I/O on the main event loop. Offload to worker threads (`asyncio.to_thread` or Node worker threads).
- **Bound All Concurrency:** Never launch unbounded concurrent tasks (`Promise.all` or `asyncio.gather` over 10,000 items). Use semaphores to cap concurrent operations:

```python
import asyncio

async def fetch_all_bounded(urls: list[str], max_concurrency: int = 10) -> list[dict]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch_one(url: str):
        async with semaphore:
            return await http_client.get(url)

    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(fetch_one(url)) for url in urls]
    return [task.result() for task in tasks]
```

- **Retain References to Background Tasks:** Unreferenced asyncio tasks can be garbage collected before completion, silently dropping errors.
- **Graceful Shutdown:** Intercept `SIGTERM`/`SIGINT` signals. Stop accepting new requests, finish in-flight workloads with a grace period (e.g., 15–30s), and close connections cleanly.

---

## 8. Caching Strategy

Treat caches purely as **performance accelerators**: your system must continue to behave *correctly* if the cache is cold, corrupted, or completely unavailable.

| Decision Vector | Architecture Guidance |
| :--- | :--- |
| **What to Cache** | Computationally expensive, frequently read, staleness-tolerant data. Always measure before adding. |
| **Key Construction** | Include all scope parameters: tenant ID, user ID (if personalized), locale, and schema version. A missing tenant in a key is a security data leak. |
| **TTL with Jitter** | Always set a TTL. Add randomized jitter (e.g., $300 \pm 30$ seconds) so bulk entries do not expire concurrently. |
| **Invalidation** | Combine short TTLs with explicit write invalidation for critical data. |
| **Cache Stampede Prevention** | Protect expired hot keys using single-flight execution (locking/mutex) so only one worker computes the missing value while others wait. |
| **Negative Caching** | Cache "Not Found" lookups for a brief period (e.g., 30s) to protect the database from query floods on non-existent keys. |
| **Hit-Rate Observability** | Alert on low cache hit rates; a cache with a 10% hit rate is wasted latency and infrastructure cost. |

---

## 9. Queues, Backpressure & Failure Isolation

- **At-Least-Once Delivery:** Message brokers guarantee at-least-once delivery; consumers must be strictly idempotent.
- **Dead-Letter Queues (DLQ):** Route poisoned messages to a DLQ after $N$ failed processing attempts. Alert on DLQ depth; never let bad messages loop forever.
- **Apply Backpressure:** When downstream components are saturated, throttle incoming work, reject with HTTP 429, or shed load rather than letting server memory balloon.
- **Circuit Breakers:** Wrap unreliable third-party integrations with a circuit breaker. After consecutive errors, fail fast immediately for a cooldown window before probing health.
- **Bulkheads:** Isolate resource pools (thread pools, queue workers) so that a failure in one feature cannot starve unrelated system operations.

---

## 10. API Design & Compatibility

- **RFC 9457 Problem Details:** Use a single, standardized JSON error format across all endpoints:
  ```json
  {
    "type": "https://api.example.com/errors/insufficient-credits",
    "title": "Insufficient Credits",
    "status": 403,
    "detail": "Account requires 15 additional credits to process paper.",
    "instance": "/requests/req_98124"
  }
  ```
- **Accurate HTTP Status Codes:** Never return HTTP 200 OK with `{"error": true}` in the response body.
- **Mandatory Pagination:** Always paginate collection endpoints from day one. Retrofitting pagination into an unpaginated API is a breaking change.
- **Backward Compatibility:** Adding optional fields is non-breaking. Renaming, deleting, or altering field types is a breaking change requiring versioning.
- **Health Probes:** Expose distinct endpoints for `/health/live` (process is up) and `/health/ready` (database and dependencies connected and ready for traffic).
