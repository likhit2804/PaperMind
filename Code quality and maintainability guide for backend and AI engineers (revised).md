# Code quality and maintainability guide for backend and AI engineers

*Revised edition. A practical reference for engineers who build backend services and LLM-powered systems: what maintainable code looks like, which reliability patterns matter, how to test and evaluate AI components, and how to adopt all of it on a real team, including a legacy one. Code examples are in Python; the principles transfer to any language.*

## How to read this guide

- Numbers marked **(heuristic)** are starting points drawn from common practice, not laws. Adjust them to your team and codebase.
- Sections 3 and 6 are the backend-specific and AI-specific core. Sections 2, 4, 5 and 7 to 12 apply to any engineering team.
- If you only have ten minutes, read section 13 (adoption roadmap) first, then come back for detail.
- Further reading at the end lists the books and reports behind much of this material.

## 1. Why code quality matters

Code is read far more often than it is written. A shortcut that saves an hour today is usually paid for later by whoever has to understand, debug or extend it, and that person is often you in six months.

Quality is not perfection or style preference. It is three practical outcomes:

- **Changeability:** features and fixes are cheap because the code is easy to navigate and safe to modify.
- **Reliability:** fewer defects reach production, and the ones that do are easy to find and fix.
- **Team speed:** new people become productive quickly, and reviews focus on design and correctness instead of formatting arguments.

For AI systems the stakes are higher. LLM-backed code adds sources of unpredictability (model output, prompts, retrieval quality, cost, vendor model changes), so the deterministic parts of the system must be as clean, typed and testable as possible. The goal is a thin, well-fenced layer of non-determinism surrounded by boring, reliable code.

**A useful mindset:** optimize for the reader. Ask “could a new teammate understand this in five minutes?” before asking “is this clever?”

## 2. Clean code fundamentals

### 2.1 Naming

Good names remove the need for many comments and make bugs visible. Guidelines:

- Name by meaning, not type: `retry_count`, not `n` or `int_value`.
- Functions are verbs (`fetch_user`, `validate_token`); classes and variables are nouns (`UserRepository`, `max_retries`).
- Booleans read as questions: `is_active`, `has_permission`, `should_retry`.
- Avoid vague words such as `data`, `info`, `manager`, `helper`, `util`, `temp`. If you cannot name it precisely, the design may be unclear.
- Put units in names: `timeout_seconds`, `size_bytes`, `price_cents`. Unit confusion is a classic production bug.
- Use one word per concept. Do not mix `fetch`, `get`, `retrieve` and `load` for the same idea.
- Name domain concepts the way the business does. If product calls it a “workspace”, do not call it a `tenant` in one file and an `org` in another.

```python
# Before: the reader must reverse-engineer intent
def proc(d, t):
    r = []
    for x in d:
        if x["ts"] > t:
            r.append(x)
    return r


# After: the signature and body explain themselves
def events_after(events: list[Event], cutoff: datetime) -> list[Event]:
    return [event for event in events if event.timestamp > cutoff]
```

### 2.2 Small, focused functions

A function should do one thing at one level of abstraction. Warning signs **(heuristic)**:

- You need to scroll to read it.
- It nests more than three levels deep.
- Its name needs “and” (`validate_and_save_and_notify`).
- It takes more than about four parameters.
- It mixes high-level orchestration with low-level detail (business rule next to string parsing).

**Use guard clauses.** Each precondition becomes its own early exit, which flattens the happy path. Note that merging all conditions into one `or` chain is *not* a guard clause; it just hides the nesting.

```python
# Deeply nested: the happy path is buried
def ship_order(order: Order) -> bool:
    if order.is_paid:
        if order.items:
            if order.address is not None:
                carrier.ship(order)
                return True
    return False


# Guard clauses: one precondition per line, happy path at the end
def ship_order(order: Order) -> bool:
    if not order.is_paid:
        return False
    if not order.items:
        return False
    if order.address is None:
        return False
    carrier.ship(order)
    return True
```

Two further improvements are worth considering. First, if “cannot ship” is exceptional rather than routine, raise a specific exception so the caller learns *why* instead of receiving a bare `False`. Second, do not accept `None` for the order itself; reject bad input at the system boundary (section 2.8) so inner functions can trust their arguments.

**Group related parameters into an object** and prefer keyword-only arguments for options:

```python
@dataclass(frozen=True)
class SearchFilters:
    tenant_id: TenantId
    created_after: datetime | None = None
    tags: tuple[str, ...] = ()


def search_documents(query: str, filters: SearchFilters, *, limit: int = 20) -> list[Document]: ...
```

**Avoid boolean flag arguments.** `send(message, True, False)` is unreadable, and a flag usually means the function does two jobs.

```python
# Unclear at the call site, and the function does two things
export_report(report, True)

# Clear: two functions, or a named enum
export_report_as_pdf(report)
export_report_as_csv(report)
```

**Separate commands from queries.** A function that changes state should not also return a surprising computed value, and a function that reads should not secretly write. Hidden side effects are the most common violation of the principle of least surprise.

### 2.3 Core principles and how they get misused

| Principle | Meaning | Common misuse |
| --- | --- | --- |
| DRY | Do not duplicate *knowledge* in several places | Merging code that merely looks similar, producing a wrong abstraction full of flags |
| KISS | Prefer the simplest design that works | Confusing “simple” with “short” or “clever” |
| YAGNI | Do not build what you do not need yet | Skipping basic extensibility that known requirements already imply |
| Separation of concerns | Keep distinct responsibilities apart | Splitting so finely that nothing can be followed end to end |
| Least surprise | Code behaves as a reader expects | Hidden side effects in innocent-looking functions |

**Duplication versus the wrong abstraction.** Duplicated *knowledge* (a tax rate, a validation rule, a status list) must live in one place. Duplicated *shape* is different: two functions that format an invoice and format a receipt may look alike today and diverge next month. Merging them early forces every change through a shared function full of `if kind == ...` branches. A useful rule of thumb **(heuristic)** is to tolerate duplication until you have seen the same pattern three times and understand how it varies, then abstract.

### 2.4 SOLID in plain language

Treat SOLID as vocabulary for design discussions, not a checklist.

| Principle | Plain meaning | What it looks like in a backend service |
| --- | --- | --- |
| Single responsibility | A module has one reason to change | Pricing rules live apart from HTTP handlers and database code |
| Open/closed | Add behavior by adding code, not by editing stable code everywhere | New payment provider = new class implementing an interface, not a new `if` in five places |
| Liskov substitution | A subtype works anywhere its parent is expected | A `ReadOnlyRepository` subclass must not throw on `save()` if callers are promised a normal repository |
| Interface segregation | Small, specific interfaces beat one giant one | Consumers depend on `Notifier`, not on a 30-method `MessagingPlatform` |
| Dependency inversion | High-level logic depends on abstractions, and dependencies are passed in | Domain code accepts a `Notifier` protocol rather than importing an email SDK |

A concrete dependency-inversion example using a Python `Protocol`:

```python
from typing import Protocol


class Notifier(Protocol):
    def send(self, user_id: UserId, message: str) -> None: ...


class SignupService:
    def __init__(self, users: UserRepository, notifier: Notifier) -> None:
        self._users = users
        self._notifier = notifier

    def register(self, email: EmailAddress) -> User:
        user = self._users.add(email)
        self._notifier.send(user.id, "Welcome!")
        return user


# Production wires in an SES or SMTP notifier; tests pass a FakeNotifier
# that records messages in a list. No mocking library required.
```

### 2.5 Code smells

Smells are warning signs, not automatic bugs. Investigate; do not reflexively rewrite.

| Smell | Why it hurts | Typical fix |
| --- | --- | --- |
| Long function or class | Does too much; hard to test | Extract functions or collaborators |
| Magic numbers and strings (`if status == 3`) | Meaning is invisible | Named constants or enums |
| Deep nesting | Hard to reason about | Guard clauses, extract function |
| Long parameter list | A concept is missing | Parameter object |
| Boolean flag arguments | Function has two jobs | Split the function |
| God object | One class knows everything; every change touches it | Split by responsibility |
| Primitive obsession | Raw strings and ints invite mix-ups | Small types such as `EmailAddress`, `UserId`, `Money` |
| Feature envy | A function mostly uses another object's data | Move it to that object |
| Dead or commented-out code | Noise and false leads | Delete it; version control remembers |
| Swallowed exceptions (`except: pass`) | Hides real failures | Catch specifically, log with context, or let it propagate |
| Shotgun surgery | One change requires edits in many files | Consolidate the scattered responsibility |
| Mutable shared state | Order-dependent bugs, especially under concurrency | Immutable data, explicit ownership |

### 2.6 Comments and docstrings

Comments explain **why**, not **what**. The code already shows what happens.

```python
# Bad: restates the code
# loop over users and send email
for user in users:
    send_email(user)

# Good: records a constraint the code cannot express
# The vendor API silently drops requests above 50 items (see INC-2231),
# so we send in batches.
BATCH_SIZE = 50
```

Useful comments include business rules, links to tickets or incident write-ups, workarounds for known bugs, and warnings about surprising behavior. A `TODO` should carry an owner or ticket number, otherwise it is just clutter. A wrong comment is worse than none, so update or delete comments when the code changes.

Docstrings belong on public functions and modules. With good type hints you rarely need to repeat types; focus on behavior: what the function guarantees, which exceptions it raises, units, and one example for anything non-obvious.

### 2.7 Error handling

Start by classifying failures, because each class needs a different response:

| Failure type | Example | Response |
| --- | --- | --- |
| Programmer error | `None` where a value is required, violated invariant | Fail fast and loudly; fix the code |
| Expected domain failure | Insufficient funds, validation failure | Raise a specific domain exception or return a typed result; show a useful message |
| Infrastructure failure | Timeout, connection reset, 503 | Retry if safe (section 3.2), otherwise surface a clear error |

Practices:

- Catch specific exceptions. Never use a bare catch-all unless you log with context and re-raise.
- Preserve the cause when wrapping: `raise NewError(...) from exc`.
- Add context to messages (what was being attempted, which IDs), but never include secrets, tokens or personal data.
- **Log once, at the boundary.** Logging and re-raising at every layer produces duplicate noise that hides the real incident.
- Use custom exception types for domain failures so callers can react precisely.

```python
class DomainError(Exception):
    """Base class for expected, business-level failures."""


class InsufficientFunds(DomainError):
    def __init__(self, account_id: AccountId, shortfall_cents: int) -> None:
        super().__init__(f"Account {account_id} is short by {shortfall_cents} cents")
        self.account_id = account_id
        self.shortfall_cents = shortfall_cents


def load_profile(user_id: UserId) -> Profile:
    try:
        row = db.fetch_one(PROFILE_QUERY, user_id)
    except DatabaseError as exc:
        raise ProfileUnavailable(f"could not load profile for user {user_id}") from exc
    return Profile.from_row(row)
```

### 2.8 Make illegal states unrepresentable

Use the type system so invalid data cannot exist. Prefer enums to free-form strings, frozen dataclasses or Pydantic models to loose dictionaries, and small wrapper types to raw primitives. Use `Optional` only where `None` is a legitimate value.

```python
from dataclasses import dataclass
from enum import Enum
from typing import NewType

UserId = NewType("UserId", str)


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"


@dataclass(frozen=True)
class Money:
    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValueError("amount_cents must be non-negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be a 3-letter ISO code")
```

**Validate at system boundaries** (HTTP bodies, queue messages, file contents, LLM output), then trust the validated types inside. A schema library makes the boundary explicit:

```python
from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0, le=1000)


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem] = Field(min_length=1)
```

## 3. Backend reliability patterns

Most serious incidents in services come not from algorithm bugs but from how the code behaves when something around it fails: a slow dependency, a duplicate message, a half-finished write. Maintainable backend code handles these cases deliberately and in a consistent way. This section covers the patterns that matter most.

### 3.1 Timeouts on every network call

Many client libraries wait forever by default. A single slow dependency without a timeout can exhaust your worker pool and take down an otherwise healthy service.

- Set explicit timeouts on every outbound call: HTTP, database, cache, queue, LLM provider.
- Separate connect timeouts (short, a second or two) from read timeouts (sized to the operation).
- Set a database `statement_timeout` and lock timeout so one bad query cannot hold resources indefinitely.
- Propagate a deadline: if a request has 5 seconds in total, a downstream call must not be allowed to use 30.
- LLM calls are legitimately slower (often tens of seconds). Use longer read timeouts, prefer streaming for user-facing output, and still cap the total.

```python
import httpx

client = httpx.Client(
    timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
)
```

### 3.2 Retries with exponential backoff and jitter

Retries turn transient failures into non-events, but careless retries amplify outages. Rules:

- Retry only **transient** failures: timeouts, connection resets, HTTP 429, 502, 503, 504. Never retry validation errors or other 4xx responses.
- Retry only **idempotent** operations, or operations protected by an idempotency key (section 3.3).
- Use exponential backoff **with jitter** so that many clients do not retry in lockstep.
- Cap both the number of attempts and the total elapsed time. Respect a `Retry-After` header when present.
- Retry at one layer only. If three stacked layers each make three attempts, one failure becomes up to 27 calls against a struggling dependency.
- Log each retry with the attempt number and reason, and expose retry counts as a metric.

```python
import random
import time


def call_with_retry(
    fn, *, attempts=4, base_delay_s=0.5, max_delay_s=8.0, retry_on=(TransientError,)
):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == attempts:
                raise
            ceiling = min(max_delay_s, base_delay_s * 2 ** (attempt - 1))
            time.sleep(random.uniform(0, ceiling))  # full jitter
```

In production, prefer a maintained library (for example `tenacity` in Python) over hand-rolled loops, but keep the policy in one shared place so every call site behaves consistently.

### 3.3 Idempotency

An operation is idempotent if doing it twice has the same effect as doing it once. Networks, queues and users all deliver duplicates, so any operation with side effects (charging a card, sending an email, creating an order) must tolerate repeats.

- For HTTP APIs, accept an `Idempotency-Key` header on non-idempotent endpoints such as `POST /payments`. Store the key with a **unique constraint** and the result.
- Store a hash of the request body with the key. If the same key arrives with a different payload, reject it rather than return a wrong answer.
- Let the database enforce uniqueness instead of a check-then-insert in application code, which races under concurrency.

```python
def create_payment(request: PaymentRequest, idempotency_key: str) -> Payment:
    try:
        with db.transaction():
            return payments.insert(request, idempotency_key=idempotency_key)
    except UniqueViolation:
        # An earlier or concurrent request with this key already won.
        return payments.get_by_key(idempotency_key)
```

### 3.4 Transactions and data consistency

- Put the transaction boundary in the service layer, around one logical unit of work, not in HTTP handlers or repositories.
- Keep transactions short. **Never call an external API or an LLM inside an open database transaction**: it holds a connection and locks while waiting on something you do not control.
- Avoid the dual-write problem. If you must update the database *and* publish an event, writing both independently can leave them inconsistent after a crash. The **transactional outbox** pattern writes the event to an `outbox` table in the same transaction, and a separate relay publishes it.
- Protect concurrent updates with optimistic locking (a `version` column) or a conditional atomic update, rather than read-modify-write in application code.

```sql
-- Atomic conditional update: no lost updates, no explicit lock needed
UPDATE accounts
SET balance_cents = balance_cents - 500, version = version + 1
WHERE id = 42 AND balance_cents >= 500;
-- If zero rows were updated, the funds check failed (or the row is missing).
```

- Know your database's default isolation level and what anomalies it permits. Choose stricter isolation or explicit locks only where an invariant truly requires it.

### 3.5 Database access

**Avoid N+1 queries.** Loading a list and then querying once per item is the most common performance bug in ORM-based code, and it hides well in small test datasets.

```python
# N+1: one query for the orders, then one more per order
orders = repo.list_orders(customer_id)
for order in orders:
    order.items = repo.list_items(order.id)

# Two queries total, regardless of how many orders
orders = repo.list_orders(customer_id)
items_by_order = repo.list_items_for_orders([o.id for o in orders])
```

Other practices:

- Index columns used in `WHERE`, `JOIN` and `ORDER BY` clauses, and confirm with `EXPLAIN ANALYZE` on realistic data volumes.
- Prefer **keyset pagination** (`WHERE id > :last_id ORDER BY id LIMIT 50`) over large `OFFSET` values, which get slower as the offset grows.
- Size connection pools deliberately: total connections across all service instances must stay below the database limit.
- Select only the columns you need on hot paths.

**Schema migrations: expand and contract.** Never ship a change that requires old and new code to be deployed atomically.

1. **Expand:** add the new column or table (nullable or with a default). Existing code keeps working.
2. **Deploy** code that writes to both old and new structures.
3. **Backfill** existing data in small batches, outside peak hours.
4. **Switch reads** to the new structure and verify.
5. **Contract:** stop writing the old structure, then drop it in a later release.

Also avoid long table locks: for example, build large indexes concurrently where your database supports it, and test migrations on a copy of production-sized data.

### 3.6 Concurrency and async code

- Never run blocking calls (synchronous HTTP, file or database drivers) inside an async event loop. Use an async driver or move the work to a thread (`asyncio.to_thread`).
- **Bound concurrency.** Unbounded `gather` over thousands of items overwhelms dependencies and memory.
- Keep references to background tasks you create, and handle their exceptions, otherwise failures vanish silently.
- Handle cancellation and shutdown: finish or safely abandon in-flight work when the process receives a stop signal.
- Prefer immutable data and explicit ownership over shared mutable state. If you must share state, protect it and keep the critical section tiny.

```python
import asyncio


async def fetch_all(urls: list[str], limit: int = 10) -> list[Response]:
    semaphore = asyncio.Semaphore(limit)

    async def fetch_one(url: str) -> Response:
        async with semaphore:
            return await client.get(url)

    # Use TaskGroup (Python 3.11+) or gather(..., return_exceptions=True)
    # and decide explicitly how partial failures are handled.
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(fetch_one(url)) for url in urls]
    return [task.result() for task in tasks]
```

### 3.7 Caching

Treat a cache as a performance optimization only: the system must remain *correct* if the cache is empty or unavailable.

| Decision | Guidance |
| --- | --- |
| What to cache | Expensive, frequently read, tolerant of slight staleness. Measure before adding. |
| Key design | Include everything that changes the value: tenant, user (if personalized), locale, and a schema or code version. A missing tenant in the key is a data leak. |
| TTL | Always set one. Add random jitter so many keys do not expire together. |
| Invalidation | Prefer short TTLs plus explicit invalidation on writes for data that must be fresh. |
| Stampede protection | When a hot key expires, allow only one caller to recompute (single-flight or a lock) while others wait or serve stale data. |
| Negative caching | Cache “not found” briefly to protect the database from repeated misses. |
| Observability | Track hit rate and latency. A cache with a low hit rate is just overhead. |

For LLM systems, caching of model responses has extra rules (cache keys must include the model, prompt version and parameters, and personalized data must never cross users); see section 6.

### 3.8 Queues, backpressure and failure isolation

- Most queues deliver **at least once**, so consumers must be idempotent (section 3.3).
- Route messages that keep failing to a **dead-letter queue** and alert on its depth. A poison message must never block the queue forever.
- Bound queue sizes and apply backpressure (reject, slow down or shed load) rather than letting memory grow without limit.
- Rate-limit by client or tenant so one noisy caller cannot starve others, and return `429` with `Retry-After`.
- Use a **circuit breaker** around unreliable dependencies: after repeated failures it opens and fails fast for a cooling-off period, then lets a few trial calls through (half-open) before closing again. Pair it with a sensible fallback or a clear error.
- Use **bulkheads**: separate pools or queues for separate workloads so a slow dependency cannot consume every worker.

### 3.9 API design and compatibility

- Use one consistent error format across the API. RFC 9457 (“problem details”) is a widely used standard.
- Use HTTP status codes accurately, and never return `200` with an error hidden in the body.
- Paginate every list endpoint from the start. Adding pagination later is a breaking change.
- Adding an optional field is backward compatible; removing, renaming or changing the meaning of a field is breaking. Version the API and publish a deprecation timeline.
- Return or generate a request ID on every call, include it in logs and error responses, and propagate it to downstream services.
- Provide separate **liveness** (is the process alive) and **readiness** (can it serve traffic) endpoints, and shut down gracefully: stop accepting work, finish in-flight requests, then exit.

## 4. Automated enforcement

Rules that depend on people remembering them will fail. Automate everything that can be automated so human review can focus on design and logic. The principle is simple: **the same commands run on a developer's laptop, in pre-commit hooks and in CI**, so there is one definition of “passes”.

### 4.1 The standard toolchain

| Layer | Python | JavaScript / TypeScript | Go |
| --- | --- | --- | --- |
| Formatter | `ruff format` (or black) | prettier (or Biome) | `gofmt` |
| Linter | `ruff` (replaces flake8 and many plugins) | ESLint | `golangci-lint`, `go vet` |
| Type checker | mypy or pyright | `tsc` with `strict` | built in |
| Test runner | pytest | vitest or jest | `go test` |
| Dependency audit | `pip-audit` | `npm audit` | `govulncheck` |
| Security lint | ruff `S` rules or bandit | eslint-plugin-security | `gosec` (via golangci-lint) |
| Secret scanning | gitleaks or trufflehog (all languages) | same | same |
| Dependency locking | `uv` or poetry lock files | `package-lock.json` or `pnpm-lock.yaml` | `go.sum` |

Examples in the rest of this guide use Python, but every row has an equivalent in the other ecosystems.

### 4.2 Formatter

A formatter ends style debates. Pick one, accept its output, and run it on save, in pre-commit and in CI. Nobody should ever comment on whitespace in a review.

### 4.3 Linter

Linters catch unused variables, unreachable code, shadowed names, risky patterns and many real bugs. Start from a recommended ruleset and tighten over time. A realistic starting configuration:

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = 'py311'

[tool.ruff.lint]
# E/F: pycodestyle and pyflakes, I: import order, B: likely bugs,
# UP: modern syntax, S: security, C90: complexity, SIM: simplifications
select = ['E', 'F', 'I', 'B', 'UP', 'S', 'C90', 'SIM']

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.per-file-ignores]
'tests/**' = ['S101']  # asserts are fine in tests
```

Treat lint failures as errors in CI so warnings do not pile up. Every suppression comment (`# noqa`) should include the specific rule and a reason.

### 4.4 Type checking

Type hints turn a large class of runtime errors into editor errors, and they double as documentation. Adopt them in this order: public functions and module boundaries first, then internals, then stricter modes.

```toml
[tool.mypy]
python_version = '3.11'
strict = true

# Legacy modules can be relaxed temporarily instead of blocking adoption:
[[tool.mypy.overrides]]
module = 'app.legacy.*'
disallow_untyped_defs = false
```

In TypeScript, enable `strict` from day one on new projects. Avoid `Any` and `# type: ignore` without a comment; each one is a hole in the safety net.

### 4.5 Pre-commit hooks

Run the **fast** checks (format, lint, secret scan) before each commit so trivial problems never reach review. Keep the hook under a few seconds, or developers will bypass it. Remember that hooks can be skipped with `--no-verify`, so **CI is the authority** and hooks are a convenience.

```yaml
# .pre-commit-config.yaml (pin each rev to a current release tag)
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <pinned-release-tag>
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: <pinned-release-tag>
    hooks:
      - id: gitleaks
```

### 4.6 Continuous integration

CI is the final gate. Good pipelines are **fast, parallel and deterministic**:

- Run independent checks in parallel jobs: lint and types, unit tests, integration tests, dependency and secret scans. Keep the whole pipeline fast; **(heuristic)** aim for under about ten minutes, because slow pipelines get bypassed.
- Build the container image after tests pass (or in parallel if integration tests need it) and scan it.
- Cache dependencies, and pin tool and base-image versions.
- Make required checks mandatory through branch protection.
- Wrap commands in a `Makefile` or task runner so CI and laptops use identical commands.

```yaml
# .github/workflows/ci.yml (sketch)
name: ci
on: [pull_request]
jobs:
  static:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make install
      - run: make lint typecheck
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make install
      - run: make test-unit
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test }
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - run: make install
      - run: make test-integration
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make audit secrets-scan
```

### 4.7 Static analysis and complexity

Tools such as SonarQube or CodeQL find deeper bugs and vulnerabilities than a linter. Track **cyclomatic complexity** (the number of independent paths through a function). Functions above roughly 10 **(heuristic)** are hard to test exhaustively and are candidates for splitting. Use the complexity trend, not a single number, to decide where to invest.

### 4.8 The ratchet: adopting strict rules on an existing codebase

Turning on strict tooling for a large legacy repo produces thousands of violations. Do not make the team fix them all at once, and do not turn the rules off. Use a **ratchet**:

- Record today's violations as a baseline (many tools support this), and fail CI only on **new** violations.
- Enforce strict rules on new and changed files first, and tighten module by module.
- When you apply a formatter to the whole repo, do it in one dedicated commit, and list that commit in `.git-blame-ignore-revs` so `git blame` stays useful.
- Track the violation count over time so progress is visible.

## 5. Testing

### 5.1 The test pyramid, and when to bend it

- **Unit tests (many):** fast, isolated, focused on one function or class. Best for business rules and data transformations.
- **Integration tests (some):** exercise real interactions with a database, queue or HTTP layer. For database-heavy services these often find more real bugs per test than units do, so do not under-invest.
- **End-to-end tests (few):** drive full user flows. They are slow and brittle, so keep them minimal and aimed at critical paths.

The pyramid is a default, not a law. A service that is mostly a thin layer over a database may deserve a thicker integration layer.

### 5.2 What makes a good test

- **Fast and deterministic:** no flakiness and no dependence on the clock, network, randomness or test order.
- **Readable:** follow arrange, act, assert. A failing test name should explain what broke.
- **Tests behavior, not implementation:** refactoring should not break tests unless behavior changed.
- **Independent:** each test sets up its own state and can run alone or in any order.
- **Precise failures:** assert on the specific outcome, not just “no exception”.

```python
NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def test_expired_coupon_is_rejected():
    # Arrange: the clock is injected, so the test never depends on today's date
    coupon = make_coupon(expires_at=NOW - timedelta(days=1))
    cart = make_cart(total_cents=5_000)

    # Act and assert
    with pytest.raises(CouponExpired):
        apply_coupon(cart, coupon, now=NOW)


@pytest.mark.parametrize(
    "total_cents, percent, expected",
    [
        (10_000, 10, 9_000),
        (999, 10, 899),  # rounding behavior is part of the contract
        (0, 50, 0),
    ],
)
def test_percentage_discount(total_cents, percent, expected):
    assert discounted_total(total_cents, percent) == expected
```

Notice the injected `now`: passing the clock (and randomness, and IDs) in as arguments is the cheapest way to make code testable.

### 5.3 Test doubles: prefer fakes and real local services

Heavy use of mocks couples tests to implementation details, so tests break during harmless refactors and pass while the real integration is broken. Prefer, in order:

1. **Real components** that are cheap to run locally (an in-memory function, a containerized Postgres or Redis started with a tool such as Testcontainers).
2. **Fakes:** small working implementations such as `InMemoryUserRepository` or `FakeNotifier`. They behave like the real thing and make assertions easy.
3. **Stubs** for fixed responses and **mocks** only when verifying an interaction itself is the point (for example, that an email was sent exactly once).

For database tests, run each test inside a transaction that is rolled back at the end, or recreate a clean schema, so tests stay independent and fast.

### 5.4 Flaky tests

A flaky test is worse than no test because it teaches the team to ignore red builds. Common causes are shared state, real time, real network, unordered collections, race conditions and test-order dependence. Policy: quarantine a flaky test immediately with a ticket and an owner, fix or delete it within a short window, and track the flakiness rate as a team metric (section 12).

### 5.5 Techniques worth adopting

- **Regression tests:** every bug fix ships with a test that fails without the fix.
- **Fixtures and factories:** build test data in one place with sensible defaults, overriding only what the test cares about.
- **Property-based testing** (Hypothesis, fast-check): state a property and let the tool search for counterexamples.
- **Contract tests:** verify that a service and its consumers agree on API shapes, so changes do not break clients silently.
- **Snapshot tests:** useful for stable, structured output, but overuse trains people to approve changes without reading them.
- **Mutation testing:** deliberately breaks the code to check that tests notice. A slow but honest measure of test quality, best used on critical modules.
- **Load and soak tests** before significant launches.
- **TDD:** writing the test first is excellent for tricky logic; it is not mandatory everywhere.

```python
from hypothesis import given, strategies as st


@given(st.text())
def test_slugify_is_idempotent(text):
    assert slugify(slugify(text)) == slugify(text)
```

### 5.6 Coverage

Coverage shows what code is *not* exercised, but high coverage does not prove the tests are good. Use it as a floor and a signal, never as a target to game:

- Measure **branch** coverage, not just line coverage.
- Prefer **diff coverage** (coverage of the lines changed in a PR) over a global percentage. It is fair to legacy code and keeps new code honest.
- Spend testing effort where risk is highest: money, permissions, data transformations, retries, concurrency, anything that is expensive to get wrong.

### 5.7 Testing code that has no tests

Before refactoring legacy code, write **characterization tests** that record what the code does *today*, including odd behavior. They are not a statement that the behavior is right; they are a safety net so you can see exactly what changes when you restructure.

### 5.8 AI components

Testing LLM-backed systems needs extra techniques (fakes for the model, recorded responses, evals, retrieval metrics). They are covered in section 6.

## 6. AI engineering practices

LLM-backed features add a component that is non-deterministic, slow, billed per token, controlled by a third party and changed without your consent. The central design goal is to **confine that unpredictability to a small, well-fenced layer** and surround it with ordinary, typed, tested code. Everything in this section follows from that idea.

### 6.1 Design principles

- **Treat model output as untrusted input.** Parse it, validate it against a schema and enforce business rules before anything depends on it. Never pass raw model text to `eval`, a shell, a SQL query or a URL fetcher.
- **Keep the model call at the edge.** Retrieval, prompt assembly, routing, validation and post-processing are deterministic and should be pure functions or small services you can test without a model.
- **Make every model call observable and replaceable.** One interface, one place that handles retries, timeouts, token accounting and logging.
- **Measure quality instead of eyeballing it.** A prompt change is a code change with unknown effects until an eval says otherwise.
- **Design for failure.** Models time out, refuse, truncate, return malformed output and get deprecated. Each of these needs a defined behavior.

### 6.2 A pipeline of small, separable steps

A typical question-answering or extraction feature decomposes as follows. Each step has its own inputs, outputs and tests:

| Step | Nature | How to test |
| --- | --- | --- |
| Input validation and sanitizing | Deterministic | Unit tests |
| Retrieval (search, filtering, ranking) | Deterministic given an index | Retrieval metrics on labeled queries (6.8) |
| Prompt assembly | Deterministic | Unit and snapshot tests on the rendered prompt |
| Model call | Non-deterministic | Fake in unit tests; evals for quality |
| Output parsing and validation | Deterministic | Unit tests with good and malformed samples |
| Post-processing and business rules | Deterministic | Unit tests |
| Persistence, caching and logging | Deterministic | Integration tests |

If a single function does all of this in one block of string concatenation and a regex, nothing in it can be tested separately and every change risks everything.

### 6.3 One client interface for every provider

Wrap each provider SDK behind a small interface your code owns. Application code depends on the interface, so swapping a provider or model, or substituting a fake in tests, touches one file.

```python
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: tuple[Message, ...]
    max_output_tokens: int
    temperature: float = 0.0
    prompt_version: str = ""  # recorded in logs for later analysis


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str  # the model that actually answered
    input_tokens: int
    output_tokens: int
    latency_ms: int
    finish_reason: str  # for example 'stop' or 'length' (truncated)


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

The production implementation is where cross-cutting concerns live, once:

```python
class ProviderClient:
    def __init__(self, sdk, *, timeout_s: float, usage_log: UsageLog) -> None:
        self._sdk = sdk
        self._timeout_s = timeout_s
        self._usage_log = usage_log

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.monotonic()
        raw = call_with_retry(  # section 3.2: only transient errors
            lambda: self._sdk_call(request),
            retry_on=(RateLimited, ProviderUnavailable, TimeoutError),
        )
        response = self._to_response(raw, latency_ms=int((time.monotonic() - started) * 1000))
        self._usage_log.record(request, response)  # tokens, latency, cost, prompt version
        return response
```

The client should also enforce a maximum output size, redact secrets and personal data from logs, apply per-tenant rate limits and budgets (6.11), and support an optional fallback model for outages.

### 6.4 Structured outputs and validation

Whenever code consumes model output, ask for a schema and validate it. Provider features such as JSON-schema modes and tool calling reduce malformed output, but they do not remove the need for validation: values can still be wrong, out of range or semantically absurd.

```python
from typing import Literal
from pydantic import BaseModel, Field, ValidationError


class TicketTriage(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    urgency: int = Field(ge=1, le=5)
    summary: str = Field(max_length=300)


MAX_REPAIR_ATTEMPTS = 1


def triage_ticket(llm: LLMClient, ticket_text: str) -> TicketTriage:
    request = build_triage_request(ticket_text)
    for _ in range(MAX_REPAIR_ATTEMPTS + 1):
        response = llm.complete(request)
        if response.finish_reason == "length":
            raise LLMOutputTruncated("triage output hit the token limit")
        try:
            return TicketTriage.model_validate_json(extract_json(response.text))
        except ValidationError as exc:
            # One bounded repair attempt: show the model its own error.
            request = with_repair_instruction(request, response.text, str(exc))
    raise LLMOutputInvalid("triage output failed validation after repair")
```

Points worth noting:

- Repair loops must be **bounded**. An unbounded “try again” loop is a cost and latency incident waiting to happen.
- Check `finish_reason`. A truncated answer that happens to parse is a silent data-quality bug.
- Decide what happens when validation finally fails: a safe default, a human review queue, or a clear error. Never let invalid output flow downstream.
- Keep schemas small and strict, with enums instead of free text wherever the set of values is known.

### 6.5 Prompts are code

Prompts determine behavior as much as any function does, so manage them with the same discipline:

- Keep prompts in **versioned files**, not in string concatenation scattered through the code. Review prompt changes in pull requests.
- Render them with a real template engine in strict mode, so a missing variable fails loudly instead of producing a prompt with a blank hole.
- Give each prompt an identifier and version, include it in every logged request, and keep a short changelog explaining *why* each change was made.
- Separate trusted instructions from untrusted content (user text, retrieved documents) with clear delimiters and explicit instructions, and remember this reduces, but does not eliminate, injection risk (6.10).
- Never rely on a prompt change alone for a critical guarantee. If something must never happen, enforce it in code after the model.

```
prompts/
  triage/
    v3.system.md
    v3.user.jinja
    CHANGELOG.md        # v3: added urgency rubric after eval showed over-escalation
```

```python
from jinja2 import Environment, FileSystemLoader, StrictUndefined

env = Environment(loader=FileSystemLoader("prompts"), undefined=StrictUndefined)


def render_triage_prompt(ticket_text: str) -> str:
    return env.get_template("triage/v3.user.jinja").render(ticket_text=ticket_text)
```

### 6.6 Testing the deterministic parts and faking the model

Use a fake client so unit tests are fast, free and fully deterministic:

```python
class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=self._responses.pop(0),
            model=request.model,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            finish_reason="stop",
        )


def test_triage_repairs_invalid_output_once():
    llm = FakeLLM(
        [
            "Sure! Here you go: category=bug",
            '{"category": "bug", "urgency": 4, "summary": "Login fails on mobile"}',
        ]
    )
    result = triage_ticket(llm, "I cannot log in on my phone")
    assert result.category == "bug"
    assert len(llm.requests) == 2  # exactly one repair attempt


def test_triage_gives_up_after_one_repair():
    llm = FakeLLM(["nope", "still nope"])
    with pytest.raises(LLMOutputInvalid):
        triage_ticket(llm, "anything")
```

Cover the failure modes explicitly, because they are where production bugs live: timeout, rate limit, refusal, empty output, truncated output, malformed JSON, valid JSON with out-of-range values, and context that exceeds the model's window.

Other techniques:

- **Record and replay:** for integration tests, capture real provider responses once and replay them from files (often called cassettes), so tests exercise realistic payloads without cost or flakiness. Refresh them deliberately and review the diffs.
- **Test prompt assembly:** assert that the rendered prompt contains the expected sections, and snapshot it so unexpected prompt changes are visible in review.
- **Never assert on exact model text** in tests that call a real model. Even at temperature zero, outputs can vary across runs, hardware and provider updates. Assert on structure, or use evals (6.7).

### 6.7 Evals: measuring model-output quality

Unit tests tell you the plumbing works. **Evals** tell you whether the model-driven behavior is actually good, and whether a change made it better or worse.

**Build a golden dataset.**

- Start with real (anonymized) examples and hand-check the expected results. A few dozen carefully chosen cases **(heuristic)** beat thousands of unchecked ones; grow the set over time.
- Include the awkward cases: ambiguous inputs, adversarial inputs, empty and very long inputs, and every failure that ever reached production. Each production bug becomes an eval case, just as it becomes a regression test.
- Version the dataset in the repository. Keep a held-out portion you do not tune prompts against, so you do not overfit to your own test set.

**Score in layers, cheapest first.**

1. **Deterministic checks:** schema validity, exact match for classification, numeric tolerance, required fields, citations that actually exist in the retrieved documents, banned content.
2. **Reference-based metrics** where a known answer exists.
3. **LLM-as-judge** for subjective qualities (helpfulness, tone, faithfulness), using a clear written rubric.

**LLM-as-judge has known pitfalls.** Judges favor longer answers, favor the first option shown, can favor text from their own model family, and shift when the judge model is updated. Mitigate by:

- Asking narrow, mostly binary questions (“does the answer contradict the source?”) rather than 1 to 10 scores.
- Randomizing or swapping order in pairwise comparisons.
- Pinning the judge model and prompt as versioned artifacts.
- **Calibrating against human labels**: periodically measure how often the judge agrees with careful human review, and fix the rubric when it does not.

**Handle variance.** Because outputs vary, a single run is weak evidence. Run multiple samples for important comparisons, report the spread, and require improvements to exceed noise before declaring a win.

```python
@dataclass(frozen=True)
class EvalCase:
    id: str
    ticket_text: str
    expected_category: str


def run_triage_eval(cases: list[EvalCase], llm: LLMClient) -> EvalReport:
    results = []
    for case in cases:
        try:
            predicted = triage_ticket(llm, case.ticket_text).category
        except LLMOutputError:
            predicted = None  # an invalid output counts as a failure
        results.append(CaseResult(case.id, predicted, predicted == case.expected_category))
    return EvalReport.from_results(results)


# Run on demand and in CI, not as part of the default fast unit suite
@pytest.mark.eval
def test_triage_has_not_regressed(real_llm):
    report = run_triage_eval(load_cases("evals/triage_smoke.jsonl"), real_llm)
    assert report.accuracy >= BASELINE_ACCURACY - TOLERANCE
```

**Wire evals into your workflow.**

- Run a small, cost-bounded **smoke eval** on every pull request that touches prompts, retrieval or model configuration.
- Run the **full eval** nightly and before any model or major prompt change.
- Store every result with the git SHA, prompt version, model and parameters, so you can compare runs and explain regressions.
- Add **online evaluation**: sample production traffic for review, collect user feedback signals, and use shadow or A/B comparison for risky changes.

### 6.8 Retrieval-augmented generation (RAG)

Most “the model is wrong” bugs in RAG systems are really retrieval bugs. Evaluate and engineer the two halves separately.

- **Version the index.** The embedding model, chunking parameters and preprocessing together define an index version. Changing any of them requires re-indexing and a new baseline. Record the index version in logs.
- **Make ingestion idempotent and incremental,** with a clear path for updates and deletions. Stale or deleted content that is still retrievable is both a quality and a compliance problem.
- **Enforce access control at retrieval time.** Filter by tenant and user permissions *before* content reaches the prompt. The model cannot be trusted to withhold what it has been shown.
- **Measure retrieval directly** on labeled queries: recall@k (is a relevant chunk in the top k?), precision@k, and ranking quality such as MRR. If recall is low, no prompt will fix the answers.
- Consider hybrid search (keyword plus vector) and a reranking step, and verify with the metrics that they help.
- **Budget the context.** Decide how many chunks fit, how they are ordered, and what is dropped when space runs out, and make that logic testable.
- **Handle “nothing relevant found” explicitly** with a defined response instead of letting the model improvise.
- Ask for citations and **verify them in code**: check that each cited source was actually in the retrieved set.

### 6.9 Agents and tools

An agent that can act on the world needs the same engineering rigor as any code that holds permissions.

- **Tools are strict, typed functions.** Validate arguments with a schema, check permissions in code, and return structured results. Never let the model construct raw SQL, shell commands or URLs without validation.
- **Least privilege.** A tool should expose the narrowest capability that works, scoped to the current tenant and user.
- **Confirm risky actions.** Side effects that are destructive, costly or irreversible should require explicit human approval or a policy check outside the model.
- **Bound every loop:** maximum steps, maximum tokens, maximum wall-clock time and a cost budget. Detect repeated identical tool calls. An agent without limits is an incident waiting to happen.
- **Keep state explicit** (typed data in your code or database), not implicit in a growing prompt, so you can checkpoint, resume and inspect it.
- **Treat tool results as untrusted** (6.10): a web page or document a tool returns may contain instructions aimed at the model.

```python
class RefundArgs(BaseModel):
    order_id: str
    amount_cents: int = Field(gt=0)
    reason: str = Field(max_length=200)


def refund_tool(args: RefundArgs, ctx: ToolContext) -> ToolResult:
    ctx.require_permission("refunds:create")  # authorization lives in code
    order = orders.get(args.order_id, tenant_id=ctx.tenant_id)
    if args.amount_cents > order.refundable_cents:
        raise ToolRejected("amount exceeds refundable balance")
    if args.amount_cents > AUTO_APPROVE_LIMIT_CENTS:
        return ToolResult.needs_human_approval(args)  # the model cannot self-approve
    refunds.create(order, args.amount_cents, args.reason, idempotency_key=ctx.call_id)
    return ToolResult.ok()
```

Test agents with a **scripted fake model** that replays a fixed sequence of tool calls, so you can verify limits, error handling and permission checks deterministically. Add trace-based evals that check *which tools were called in what order* for representative tasks.

### 6.10 Security and privacy

- **Prompt injection.** Any text the model reads (user messages, retrieved documents, web pages, tool output, emails) can contain instructions. Delimiters and warnings in the prompt help but are not a security boundary. The reliable defenses are architectural: least-privilege tools, no secrets in prompts, authorization decided in code, confirmation for sensitive actions, and treating anything the model produces as untrusted.
- **Never let the model decide who is allowed to do what.** Identity and permissions come from your authentication layer, not from text in a prompt.
- **Data minimization.** Send the model only what it needs. Redact or tokenize personal and confidential data where feasible, and understand your provider's retention and training terms.
- **Logs are sensitive data.** Full prompts and responses often contain personal information. Store them in access-controlled systems with defined retention, and never log secrets.
- **Tenant isolation** applies to retrieval, caches, conversation memory and fine-tuning data alike. A cache key missing a tenant ID is a cross-customer leak.
- **Output handling.** Escape model output before rendering it as HTML, and never execute generated code outside a sandbox.
- **Abuse and cost controls:** rate limits, per-user budgets and maximum input sizes.
- Include **adversarial cases** (injection attempts, requests for restricted data) in your eval set, and consult the OWASP Top 10 for LLM Applications as a checklist.

### 6.11 Cost, latency and caching

- **Account for every token.** Log input and output tokens and estimated cost per call, per feature and per tenant. Alert on anomalies.
- Set `max_output_tokens` deliberately, and control prompt size by limiting history and retrieved context instead of letting it grow unbounded.
- **Route by difficulty.** Cheaper, faster models often handle simple steps well; use a stronger model only where evals show it is needed. Let evals, not intuition, justify each choice.
- **Cache carefully.** An exact-match response cache must key on model, prompt version, parameters and the full input, plus tenant or user where output is personalized. Use provider-side prompt caching for long, stable prompt prefixes. Be cautious with semantic caches: a “similar enough” hit can return a wrong or private answer.
- Use streaming for user-facing latency, run independent calls in parallel, and use batch endpoints for offline work.
- Define **fallback behavior** for provider outages and rate limits: a secondary model, a degraded non-AI path, or a clear error.

### 6.12 Managing model and prompt changes

Providers update and retire models. Treat a model change as a deployment of untested code.

- Keep model identifiers in **configuration**, not scattered through the code. Where behavior stability matters, pin a specific model version rather than a floating alias, and track deprecation dates.
- Upgrade by procedure: run the full eval on the candidate, compare quality, cost and latency against the baseline, roll out gradually (shadow or canary), and keep rollback as a config change.
- Keep eval baselines **per model**, because a prompt tuned for one model often needs retuning for another.
- Record model choices and their rationale in an ADR (section 9.2).

### 6.13 Observability for AI systems

You cannot debug what you cannot see. For each request, capture a trace linking:

- the input (or a redacted form), retrieval results and index version;
- prompt ID and version, model, parameters;
- tokens, latency, estimated cost;
- validation outcome and any repair or retry attempts;
- tool calls and their results;
- the final output and any user feedback.

Track aggregate metrics: validation-failure rate, refusal rate, truncation rate, retry rate, p95 latency, cost per request, eval score trend and user-feedback rate. Make it possible to **replay** a production request in a test environment, because reproducing a bad answer is the first step to fixing it.

### 6.14 Data and ML pipelines

If your work includes data processing, training or notebooks:

- Notebooks are excellent for exploration. When logic is reused or reaches production, move it into tested modules, and keep notebooks thin. Strip outputs before committing.
- Make runs reproducible: fixed seeds, locked environments, versioned datasets and recorded model artifacts with the code version that produced them.
- Validate data at pipeline boundaries (schema, null rates, ranges, distribution drift) and fail loudly.
- Share feature and preprocessing code between training and serving to avoid training-serving skew.
- Monitor models in production for drift and track quality over time, not only at launch.

## 7. Code review and collaboration

### 7.1 Writing good pull requests

- Keep them **small** and focused on one purpose. **(Heuristic:)** reviews degrade sharply above a few hundred changed lines; split larger work into a sequence of reviewable steps (stacked PRs or feature-flagged increments).
- Explain *what* changed, *why*, *how it was tested* and *what could go wrong*. Link the ticket or design doc.
- Separate refactors and formatting from behavior changes, so reviewers can verify each kind of change appropriately.
- Review your own diff first. Reading it as a reviewer catches a surprising share of issues.
- Include evidence: test output, screenshots, query plans, or eval results for AI changes.
- Open a **draft PR** early when you want direction rather than approval.

```markdown
<!-- .github/pull_request_template.md -->
## What and why

## How I tested it

## Risks and rollout
(migrations, feature flags, rollback plan, cost or latency impact)

## Checklist
- [ ] Tests added or updated (regression test for bug fixes)
- [ ] Docs, README or ADR updated if needed
- [ ] AI changes: prompt version bumped, evals rerun, results attached
```

### 7.2 Reviewing well

Let automation handle formatting, lint and type errors so that human attention goes to what machines cannot judge. Review in this order, because early problems make later comments moot:

1. **Design:** does the approach fit the system, and is it the right size of solution?
2. **Correctness:** edge cases, error handling, concurrency, security, data migrations.
3. **Tests:** do they cover the change, the failure cases and any bug being fixed?
4. **Readability:** names, structure, comments.
5. **Nits last,** and label them as nits.

Communicating well matters as much as spotting issues:

- Critique the code, not the person, and explain the reason behind each request.
- Use prefixes so authors know what is required: `blocking:`, `question:`, `suggestion:`, `nit:`.
- Offer a concrete alternative when you can.
- If a thread goes beyond two rounds, talk synchronously, then record the outcome in the PR.
- Respond promptly **(heuristic: within one working day)** so work does not stall, and approve when the change improves the codebase even if it is not how you would have written it.

| Weak comment | Better comment |
| --- | --- |
| “This is confusing.” | “suggestion: `process()` mixes parsing and persistence. Splitting them would let us unit test parsing without a database. Want to pair on it?” |
| “Wrong.” | “blocking: if `items` is empty this divides by zero on line 42. Can we add a guard and a test for the empty case?” |
| “Why did you do it this way?” | “question: what was the reason for polling rather than using the webhook? Just want to understand the tradeoff.” |

**Reviewing AI-assisted code.** Code produced with the help of an AI assistant needs the same standards as any other, and the author remains responsible for understanding every line. Reviewers should watch for plausible-looking but wrong logic, invented APIs, missing edge cases, unnecessary complexity, copied patterns that do not fit the codebase, and tests that merely mirror the implementation.

### 7.3 Conventions that help

- **Conventional commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`) make history searchable and changelogs automatic. Write the commit body for *why*, not *what*.
- **PR templates** put the checklist in front of everyone automatically.
- **CODEOWNERS** routes reviews to the people who know each area.
- **Branch protection** requires passing CI and at least one approval before merging.
- **Short-lived branches** (or trunk-based development with feature flags) avoid painful long-running merges.
- **A definition of done** is a shared list: tests, docs, monitoring, feature flag state, evals for AI changes. Without one, “done” means different things to different people.

## 8. Refactoring and technical debt

### 8.1 Refactoring safely

Refactoring means changing structure without changing behavior. The rules:

- **Have tests first.** Without a safety net you are editing, not refactoring. If tests are missing, write characterization tests (section 5.7).
- Take small steps and run the tests after each one.
- Commit refactors **separately** from feature work.
- Use the *preparatory refactoring* approach: when a change is awkward, first reshape the code so the change becomes easy, then make the change.
- Apply the **Boy Scout rule** (leave each file a little cleaner than you found it), kept proportional to the task at hand. A drive-by rewrite is not a cleanup.

| If you see | Consider |
| --- | --- |
| Long function | Extract function |
| Confusing name | Rename |
| Repeated conditional on a type or mode | Replace conditional with polymorphism or a lookup table |
| Long parameter list | Introduce parameter object |
| Class doing two jobs | Extract class |
| Needless indirection | Inline function or class |
| Logic using another object's data | Move method |

A small example of replacing a growing conditional with data:

```python
# Before: every new shipping method edits this function
def shipping_cost_cents(order):
    if order.method == "standard":
        return 500
    elif order.method == "express":
        return 1500
    elif order.method == "overnight":
        return 3500
    raise ValueError(order.method)


# After: adding a method is a one-line data change
SHIPPING_COST_CENTS = {
    ShippingMethod.STANDARD: 500,
    ShippingMethod.EXPRESS: 1500,
    ShippingMethod.OVERNIGHT: 3500,
}


def shipping_cost_cents(order: Order) -> int:
    return SHIPPING_COST_CENTS[order.method]
```

### 8.2 Technical debt

Technical debt is the future cost of past shortcuts. Like financial debt, some is a rational choice (shipping quickly to learn something), and some is accidental or reckless. Classify it honestly, because the response differs: deliberate debt needs a repayment plan, accidental debt needs better practices.

- **Make it visible.** Keep a debt register or label tickets `tech-debt`. For each item, record the impact in plain terms (“every change to billing takes an extra day”, “two incidents this quarter”), the affected area and a rough size.
- **Prioritize by pain.** Fix debt that slows frequent work or causes incidents first. Debt in code nobody touches can safely wait, and sometimes forever.
- **Pay continuously.** Reserve a steady share of capacity rather than waiting for a heroic cleanup. **(Heuristic:)** many teams use 10 to 20 percent; the right number depends on how much debt you carry and how urgent delivery pressure is.
- **Attach debt work to feature work** in the same area where possible, so it ships with a clear business reason.
- **Delete code.** Unused features, flags and dependencies are debt with no upside.

**Avoid big-bang rewrites.** They routinely take longer than planned, freeze improvements to the old system and rediscover every edge case the old code handled. Use the **strangler fig** approach instead:

1. Put a seam (a facade, router or proxy) in front of the legacy component.
2. Build the replacement behind the seam for one slice of behavior.
3. Route a small share of traffic to it, compare results (shadow mode is ideal), and expand gradually.
4. Retire the old slice. Repeat until the old component is empty, then delete it.

### 8.3 Finding hotspots

Files that change often *and* are complex are where bugs and slowness cluster. Combine churn (how often a file changes) with complexity, and invest cleanup effort where both are high.

```bash
# Most frequently changed files in the last six months
git log --since='6 months ago' --name-only --pretty=format: \
  | sort | uniq -c | sort -rn | head -20

# Complexity of Python code (radon is one option)
radon cc -s -a src
```

The overlap of the two lists is your shortlist for refactoring, extra tests and extra review attention.

## 9. Documentation

Document what the code cannot say: intent, decisions, context and operating procedures. Documentation that restates the code goes stale and misleads.

### 9.1 README

Every repository needs one, and a new engineer should be able to get the project running from it alone. It should answer:

- What is this, and who is it for?
- How do I install dependencies and run it locally (ideally in one or two commands)?
- How do I run the tests, linters and evals?
- How is the code organized, and where do I look first?
- How do I contribute, and who owns it?
- Where is the deeper documentation (ADRs, runbooks, API docs)?

Test it periodically by having a new teammate follow it literally and fixing every place they get stuck.

### 9.2 Architecture decision records (ADRs)

An ADR is a short record of one significant decision: the context, the choice, the alternatives and the consequences. Store them in the repository (for example `docs/adr/0007-use-pgvector.md`) so they are versioned with the code and discoverable by the people who will wonder, a year later, “why on earth did we do it this way?”

```markdown
# ADR-0007: Use pgvector instead of a dedicated vector database

- Status: Accepted
- Date: 2026-03-12
- Deciders: backend team

## Context
We need semantic search over roughly 2M document chunks. The team is four
engineers, we already operate Postgres, and query volume is low (tens of
queries per second at peak).

## Decision
Use the pgvector extension with an HNSW index in our existing Postgres.

## Alternatives considered
- Managed vector database: strong at scale, but adds a vendor, cost and
  another system to secure and operate for a workload we can serve today.
- Self-hosted dedicated vector store: good performance, but one more
  service to run and monitor.

## Consequences
- Simpler operations, one backup story, and transactional consistency
  between documents and their embeddings.
- Vector search shares resources with the main database, so we must
  watch load and index build times.
- Revisit if the corpus grows by an order of magnitude, if p95 search
  latency exceeds our target, or if we need filtering features pgvector
  cannot provide efficiently. Benchmark first; do not assume.
```

Rules of thumb:

- One decision per ADR, about a page long.
- **Never rewrite history.** When a decision changes, write a new ADR that supersedes the old one, and update the old one's status to “Superseded by ADR-00NN”.
- Record only decisions that are costly to reverse or that people keep asking about.
- Include a trigger for revisiting the decision, but base thresholds on measurement, not guesses.
- Good AI-specific ADR topics: model and provider choice, chunking and embedding strategy, eval methodology, data retention for prompts and logs, build versus buy for agent frameworks.

### 9.3 RFCs and design docs

An RFC explores a problem and proposes a solution **before** significant work starts, inviting feedback. It is longer than an ADR. Typical sections: problem and context, goals, non-goals, proposed design, alternatives considered, risks and security implications, testing and rollout plan, open questions.

|  | RFC or design doc | ADR |
| --- | --- | --- |
| Purpose | Explore and persuade before building | Record the decision after it is made |
| Length | Several pages | About one page |
| When | Large, risky or cross-team changes | Any decision costly to reverse |
| Lifespan | Often archived after approval | Permanent, superseded rather than edited |

Many teams write an RFC first and distill the outcome into an ADR once the decision is final. Not every change needs either: small, reversible changes can be decided in a PR.

### 9.4 Runbooks

A runbook is a step-by-step guide for operating the system and responding to incidents. Write it for a tired engineer at 3 a.m. who has never seen this alert. Link every alert directly to its runbook.

```markdown
# Runbook: Search latency high

## What the alert means
p95 latency of /search above 2s for 10 minutes.

## Impact
Users see slow or timed-out search. Writes are unaffected.

## Diagnose
1. Open dashboard 'Search overview': is the slowdown in retrieval or in the LLM call?
2. Check LLM provider status and our rate-limit error rate.
3. Check database CPU and slow-query log.

## Mitigate
- LLM slow or erroring: enable the fallback model (flag `search.fallback_model`).
- Database saturated: disable reranking (flag `search.rerank`) to cut load.

## Escalate
If not mitigated in 30 minutes, page the on-call lead (see rota).

## After
File a postmortem if user impact exceeded 15 minutes.
```

### 9.5 Other documentation worth having

- **Docstrings** on public functions and modules: behavior, errors, units and one example for anything non-obvious.
- **API documentation** generated from an OpenAPI spec so it cannot drift from the implementation.
- **Diagrams as code** (Mermaid, PlantUML) so they live in version control and are reviewed like code.
- **Changelog** in a consistent format, generated from conventional commits where possible.
- **Onboarding guide:** environment setup, domain glossary, who to ask.
- **Postmortems:** blameless write-ups after incidents covering timeline, impact, root causes (plural: incidents rarely have just one), what went well, and follow-up actions with owners and dates. The goal is to fix systems, not to find someone to blame.
- **AI feature documentation:** what the feature is for, what data it uses, prompt and model versions in production, eval results, known failure modes, and the escalation path when it misbehaves.

Keep docs close to the code, review them in PRs, assign owners, and delete what is stale. A doc nobody maintains is worse than none.

## 10. Project structure and design

### 10.1 Layered architecture

Separate business logic from frameworks and infrastructure. Dependencies point **inward**: the domain never imports the web framework, the database driver or an LLM SDK.

- **Interface layer:** HTTP handlers, CLI commands, queue consumers. Thin: parse input, call a service, format output.
- **Service layer:** use cases that orchestrate the domain and the outside world.
- **Domain layer:** entities, value objects and business rules. Pure, easy to test.
- **Infrastructure layer (adapters):** database access, caches, external APIs, LLM clients, implementing interfaces the inner layers define.

```
src/app/
  api/              # HTTP handlers and request/response schemas
  services/         # use cases: AnswerQuestion, TriageTicket
  domain/           # entities, value objects, business rules (no I/O imports)
  ports/            # Protocols the core needs: LLMClient, DocumentIndex, Notifier
  adapters/         # postgres, redis, provider SDK wrappers implementing ports
  ai/
    prompts/        # versioned prompt files
    pipelines/      # retrieval, prompt assembly, parsing
    evals/          # datasets, scorers, runners
  config.py         # typed settings
  main.py           # composition root
tests/              # mirrors src/ layout
docs/               # adr/, runbooks/, design/
migrations/
```

Dependency direction can be **enforced mechanically** (for example with import-linter in Python or dependency rules in your build tool) so it does not erode one convenient shortcut at a time.

### 10.2 Dependency injection and the composition root

Pass collaborators in instead of constructing them inside. This lets tests substitute fakes and lets you change implementations without editing callers. Wire everything together in **one place** (the composition root) at startup, and avoid hidden globals and import-time side effects.

```python
class AnswerService:
    def __init__(self, retriever: Retriever, llm: LLMClient, cache: Cache) -> None:
        self._retriever = retriever
        self._llm = llm
        self._cache = cache


# main.py: the only place that knows the concrete classes
def build_app(settings: Settings) -> App:
    llm = ProviderClient(
        make_sdk(settings.llm_api_key.get_secret_value()),
        timeout_s=settings.llm_timeout_s,
        usage_log=UsageLog(db),
    )
    retriever = Retriever(PgVectorIndex(db))
    return App(AnswerService(retriever, llm, RedisCache(settings.redis_url)))
```

### 10.3 Configuration and secrets

- Follow the twelve-factor approach: configuration comes from the **environment**, not from the code.
- Use typed settings and **validate at startup**, failing immediately if something is missing or malformed. A service that crashes at boot with a clear message is better than one that fails on the first request.
- **Never commit secrets.** Use a secrets manager, rotate credentials, and scan for leaked keys in pre-commit and CI. Use a secret type that hides values when printed.
- Keep separate settings per environment but identical code. Do not give production secrets safe-looking defaults.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    llm_api_key: SecretStr
    llm_model: str
    llm_timeout_s: float = 30.0
```

### 10.4 Boundaries and contracts

- Validate **all** external input (HTTP bodies, queue messages, files, LLM output, tool results) at the edge with schemas.
- Keep module interfaces small and explicit. In Python, mark internals with a leading underscore and expose a deliberate public surface.
- Version APIs and event schemas. Make changes backward compatible, using expand and contract for databases (section 3.5).
- Document who owns each boundary.

### 10.5 Monolith first

A well-structured **modular monolith** is easier to build, test, deploy and debug than a set of services, and clean module boundaries make a later split possible. Split into separate services when you have a concrete reason, such as independent scaling, different reliability or security needs, or genuinely independent teams, and not as a default. Every network boundary adds latency, failure modes, versioning problems and operational cost.

## 11. Dependencies, releases and observability

### 11.1 Dependencies

Every dependency is code you now rely on and must keep secure and up to date.

- **Lock versions** with a lock file for reproducible builds, and install from the lock file in CI and production.
- **Automate updates** with Dependabot or Renovate, and merge them regularly in small batches. Large, rare upgrades are the painful ones.
- **Scan for known vulnerabilities** in CI, and generate an SBOM (software bill of materials) for important services.
- **Be deliberate about supply-chain risk.** Pin versions, verify integrity where your tooling supports it, and avoid adopting a brand-new release the moment it appears; a short waiting period lets the community catch problems.
- **Vet new dependencies.** Before adding one, check that it is actively maintained, its license is compatible, its security history is acceptable, and the problem is not solvable in a few lines of your own code.
- **Remove unused packages.** Tools such as deptry (Python) or knip (JavaScript) can find them.
- Pin and test upgrades of AI SDKs and framework libraries with the same care as model versions: they change quickly and sometimes change behavior.

### 11.2 Making change safe

- **Feature flags** separate deploying code from releasing behavior. Give every flag an owner and an expiry, and remove it once the feature is permanent, because flag debt is real. Distinguish release flags (temporary), operational flags (kill switches, long-lived) and experiment flags.
- **Progressive delivery** (canary, blue-green) with automatic rollback on error spikes limits the damage of a bad release.
- **Make rollback boring.** Know exactly how to revert code, configuration, a prompt version and a model choice, and practice it.
- **Database migrations** must be backward compatible and, where possible, reversible (section 3.5).
- **Semantic versioning** for libraries and APIs, plus a published deprecation policy with clear timelines.
- Treat configuration changes (flags, prompt versions, model settings) as deployments: reviewed, logged and reversible.

### 11.3 Observability as maintainability

Code you cannot observe is code you cannot maintain.

- **Structured logs** (JSON key-value pairs) with a correlation or request ID on every line, so one request can be followed across services. Pick log levels deliberately, and keep personal data and secrets out.
- **Metrics** for the golden signals: latency, traffic, errors and saturation. Avoid high-cardinality labels (such as raw user IDs) on metrics, which can overwhelm monitoring systems.
- **Distributed tracing** (for example with OpenTelemetry) to see where time goes across services, databases and model calls.
- **SLOs:** define what “working” means in user terms, for example “99.5% of search requests complete in under 2 seconds over 30 days”. The remainder (0.5%) is your error budget, which tells you when to slow feature work and invest in reliability.
- **Alert on symptoms users feel** (error rate, latency, failed jobs), not on every internal cause, and link each alert to a runbook. An alert nobody acts on should be fixed or deleted.

```python
logger.info(
    "payment_created",
    extra={
        "request_id": ctx.request_id,
        "payment_id": payment.id,
        "amount_cents": payment.amount_cents,
        "duration_ms": elapsed_ms,
    },
)
```

## 12. Measuring quality

Metrics should start conversations, not punish people. Use them at the team level, watch trends rather than single values, and pair measures so that improving one cannot hide damage to another (for example speed alongside stability).

| Metric | What it tells you | Caution |
| --- | --- | --- |
| Deployment frequency | How often you deliver working changes | Pair with stability metrics |
| Lead time for changes | How long a commit takes to reach production | Includes waiting and review time, not just coding |
| Change failure rate | Share of deployments that cause problems | Needs a clear shared definition of “failure” |
| Failed-deployment recovery time (formerly mean time to restore) | How quickly you recover from a bad release | Use the median alongside the mean |
| Test flakiness rate | Trust in the test suite | A rising rate predicts ignored red builds |
| PR size and review time | Health of the review process | Do not optimize by splitting PRs artificially |
| Cyclomatic complexity trend | Whether code is getting harder to change | Look at hotspots, not the global average |
| Diff coverage and escaped defects | Whether new code is tested and what slips through | Coverage alone does not measure test quality |
| Dependency age and known vulnerabilities | Maintenance hygiene | Triage by reachability and severity |
| Churn plus complexity hotspots | Where cleanup pays off most | A guide for attention, not a scoreboard |
| For AI features: eval scores, validation-failure rate, cost per request, p95 latency, user feedback | Whether the AI layer is good, reliable and affordable | Track per prompt and model version |

The first four are the DORA metrics, which research has linked to software delivery performance; two measure throughput and two measure stability. Recent DORA reports have refined the definitions (for example the recovery-time rename and an added rework measure), so check the current report before standardizing on exact wording. Avoid vanity measures such as lines of code, commit counts or a raw coverage percentage used as a target, and never use these metrics to rank individuals: people respond to measurement by optimizing the measure.

## 13. Adopting this on a real team

You cannot do everything at once, and a team that is told to change everything changes nothing. Three principles make adoption stick:

- **Start with pain.** Begin with the problems the team already complains about (flaky builds, slow reviews, recurring incidents), so each change visibly pays for itself.
- **Make the right thing the easy thing.** Automation and templates beat reminders and nagging.
- **Ratchet, do not big-bang.** Hold new code to the new standard, improve old code when you touch it, and track progress (section 4.8).

### 13.1 A sensible order

| When | Do this | Notes |
| --- | --- | --- |
| Week 1 | Add a formatter and linter, and run them in CI. | Largest payoff for the least effort. On a legacy repo: one dedicated reformat commit, listed in `.git-blame-ignore-revs`, and a baseline so only new violations fail. |
| Weeks 2 to 3 | Add type checking on new and changed code, pre-commit hooks and a Makefile so local and CI commands match. | Relax rules per legacy module rather than disabling globally. |
| Month 1 | PR template, small-PR norm, branch protection, conventional commits, a README a newcomer can follow. | Audit outbound calls for missing timeouts and unsafe retries (section 3). |
| Month 1 (AI, as soon as any LLM feature exists, even a prototype) | One client wrapper, schema validation of outputs, prompts in versioned files, usage logging, and a starter eval set of 20 to 50 cases. | Do not wait for month three: untracked prompts and unmeasured quality are hardest to retrofit. |
| Month 2 | Raise test quality around the riskiest modules; regression test for every bug; a real-database integration test; parallel CI; secret and dependency scanning. | On legacy code, start with characterization tests. |
| Month 3 | Start ADRs and runbooks for the top alerts, set up dependency automation, create a visible debt register, define a first SLO. | Write the runbook for the alert that last woke someone up. |
| Ongoing | Refactor hotspots gradually, review metrics monthly, grow the eval set from failures, rehearse model upgrades and rollbacks, hold blameless retrospectives. | Reserve steady capacity for debt (section 8.2). |

### 13.2 Adopting on an existing codebase

1. **Stabilize the pipeline first:** make the build reliable and fast. Nothing else sticks while CI is red or flaky.
2. **Freeze the baseline:** record current lint and type violations and fail only on new ones.
3. **Protect the dangerous areas:** add characterization and regression tests around the code that handles money, permissions and data loss.
4. **Fix on touch:** when someone changes a file, they bring it up to the new standard, proportionally.
5. **Pick two or three hotspots** (section 8.3) for deliberate refactoring each quarter, rather than spreading effort thinly.
6. **Retire, do not rewrite:** use the strangler fig approach for components too costly to repair.

## 14. Checklists

Use these as prompts for conversation, not paperwork. Each item points back to the section that explains it.

### 14.1 Pull request checklist

**Design and clarity**

- Does it do one thing, and is it small enough to review properly? (7.1)
- Are names clear, functions short, and surprises avoided? (2.1, 2.2)
- Are illegal states hard to represent, and is input validated at the edge? (2.8, 10.4)

**Correctness and reliability**

- Are edge cases and error paths handled, with specific exceptions and context? (2.7)
- Do all outbound calls have timeouts, and are retries safe and bounded? (3.1, 3.2)
- Are writes idempotent where duplicates are possible, and are transactions short? (3.3, 3.4)
- Are migrations backward compatible, and is there a rollback path? (3.5, 11.2)

**Tests and operations**

- Are there tests for the change and its failure cases, plus a regression test for any bug fix? (5)
- Are secrets kept out of code and logs, and personal data handled correctly? (6.10, 10.3)
- Is there logging, a metric or a trace for the new behavior, and do alerts have runbooks? (11.3)
- Are docs, README or ADRs updated where needed? (9)

**For AI changes**

- Is the prompt versioned and the change explained? (6.5)
- Is output validated, with bounded repair and defined failure behavior? (6.4)
- Were evals rerun and results attached, including adversarial cases? (6.7, 6.10)
- Are token limits, cost and latency considered, and are logs redacted? (6.11, 6.13)

### 14.2 New service setup checklist

1. Repository with README, license and `.gitignore`.
2. Formatter, linter and type checker configured, with a Makefile exposing the same commands locally and in CI.
3. Pre-commit hooks (format, lint, secret scan).
4. Test framework with a first passing test, and a real-database integration test.
5. CI with parallel jobs for static checks, unit tests, integration tests and security scans.
6. Dependency lock file and an automated update bot.
7. Branch protection, PR template and CODEOWNERS.
8. Dockerfile with a multi-stage build and a non-root user.
9. Typed configuration from the environment, validated at startup, secrets from a secrets manager.
10. Structured logging with request IDs, metrics, tracing, and liveness and readiness endpoints.
11. Graceful shutdown handling.
12. `docs/adr/` with a first ADR for the main stack choice, and a runbook stub for deployment and common alerts.

### 14.3 AI feature launch checklist

1. All model calls go through one client interface with timeouts, bounded retries, token accounting and a fallback.
2. Prompts live in versioned files, and prompt version and model are logged on every call.
3. Model identifiers are configuration, pinned to specific versions where stability matters, with deprecation dates tracked.
4. Every output consumed by code is schema-validated, with truncation and refusal handled.
5. A golden dataset exists and covers edge cases and adversarial inputs; a smoke eval runs in CI and a full eval runs before releases.
6. Retrieval quality (recall and precision) is measured separately from answer quality, and access control is enforced before content reaches the prompt.
7. Tools are least-privilege, validated and logged; risky actions need approval; agent loops have step, time and cost limits.
8. Prompt-injection and data-leak scenarios were tested; personal data is minimized, redacted in logs and retained only as long as needed.
9. Cost and latency budgets are defined, with alerts on anomalies and a per-tenant cap.
10. Dashboards show validation-failure rate, refusal rate, latency, cost and user feedback, and a production request can be replayed.
11. A rollback path exists for code, prompt, model and index version.
12. A runbook and documentation describe known failure modes and who to escalate to.

### 14.4 Weekly habits

- Delete dead code you came across.
- Rename one confusing thing.
- Add a missing test around code you touched.
- Update or remove one stale doc.
- Review one dependency update.
- Add one real failure from production to your eval set or regression tests.

## 15. Glossary

- **ADR:** architecture decision record; a short record of one significant decision.
- **Backpressure:** slowing, rejecting or shedding work when a system is overloaded instead of letting queues grow without bound.
- **Boy Scout rule:** leave the code a little cleaner than you found it.
- **Bulkhead:** isolating resources (pools, queues) so one failing workload cannot consume everything.
- **Canary release:** exposing a change to a small share of traffic first.
- **Characterization test:** a test that records current behavior of legacy code as a safety net for refactoring.
- **CI/CD:** continuous integration and delivery; automated build, test and deployment.
- **Circuit breaker:** a guard that stops calling a failing dependency for a cooling-off period.
- **Code smell:** a surface sign of a possible deeper design problem.
- **Composition root:** the single place where concrete objects are created and wired together.
- **Conventional commits:** a structured commit message format (`feat:`, `fix:` and so on).
- **Coverage (branch, diff):** the share of branches executed by tests; diff coverage restricts this to lines changed in a PR.
- **Cyclomatic complexity:** a count of independent paths through code.
- **Dead-letter queue:** where messages that repeatedly fail are parked for inspection.
- **DORA metrics:** research-backed delivery measures covering throughput and stability.
- **DRY:** do not repeat knowledge in several places.
- **Eval:** a repeatable measurement of AI output quality against a dataset and scoring method.
- **Expand and contract:** a migration pattern that adds the new structure, migrates, then removes the old, so old and new code can coexist.
- **Fake:** a small working substitute for a real component, used in tests.
- **Feature flag:** a switch that turns behavior on or off without deploying.
- **Golden dataset:** a curated, versioned set of inputs with expected results used for evals.
- **Golden signals:** latency, traffic, errors and saturation.
- **HNSW:** a graph-based index for approximate nearest-neighbor vector search.
- **Idempotency:** performing an operation twice has the same effect as once.
- **Keyset pagination:** paging by the last seen key rather than by offset.
- **KISS:** keep it simple.
- **LLM-as-judge:** using a model to score another model's output against a rubric.
- **Linter:** a tool that flags suspicious or non-standard code.
- **N+1 query:** one query to load a list plus one more per item.
- **Outbox pattern:** writing events to a table in the same transaction as the data, then publishing them separately.
- **Prompt injection:** malicious or accidental instructions in text a model reads.
- **Property-based testing:** testing general properties over many generated inputs.
- **RAG:** retrieval-augmented generation; supplying retrieved documents to a model as context.
- **Ratchet:** allowing no new violations of a standard while old ones are gradually removed.
- **Refactoring:** restructuring code without changing behavior.
- **RFC:** request for comments; a design proposal for discussion before work begins.
- **Runbook:** an operational guide for handling a specific situation.
- **SBOM:** software bill of materials; an inventory of components in a build.
- **SLO:** service level objective; a target for reliability in user terms.
- **SOLID:** five object-oriented design guidelines (section 2.4).
- **Strangler fig:** gradually replacing a legacy system piece by piece behind a seam.
- **Technical debt:** the future cost of present shortcuts.
- **Twelve-factor app:** a set of practices for portable, configurable, cloud-friendly services.
- **YAGNI:** you are not going to need it.

## Further reading

- *Refactoring* (Martin Fowler): the catalog of refactorings and the reasoning behind them.
- *Clean Code* (Robert C. Martin): influential on naming and function design; read critically, as some advice is debated.
- *A Philosophy of Software Design* (John Ousterhout): a counterweight emphasizing deep modules and managing complexity.
- *Working Effectively with Legacy Code* (Michael Feathers): characterization tests and safe change in untested systems.
- *Designing Data-Intensive Applications* (Martin Kleppmann): consistency, transactions, messaging and data systems.
- *Release It!* (Michael Nygard): timeouts, circuit breakers, bulkheads and other stability patterns.
- *Accelerate* (Forsgren, Humble, Kim) and the annual DORA reports: the research behind delivery metrics.
- *Software Engineering at Google* and the *Site Reliability Engineering* books: review, testing, SLOs and operations at scale.
- Google's public engineering practices documentation on code review.
- Michael Nygard's article “Documenting Architecture Decisions”: the origin of ADRs.
- The Twelve-Factor App (12factor.net) and the OWASP Top 10 for LLM Applications.

## Closing thought

Quality is a set of small, repeated habits backed by automation, not a one-time cleanup. Start with the tools that remove arguments, make failure handling and measurement explicit (especially around anything that calls a model), build the review and testing culture next, and write down decisions and procedures as you go. The goal is a codebase where change is cheap and safe.
