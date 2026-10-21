# 01. Clean Code Fundamentals

> **Module:** Core Engineering Principles  
> **Source:** Sections 1 & 2 of the Revised Code Quality Guide  
> **Related:** [02. Backend Reliability Patterns](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md) | [09. Project Structure](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/09_project_structure_and_design.md)

---

## 1. Why Code Quality Matters

Code is read far more often than it is written. A shortcut that saves an hour today is usually paid for later by whoever has to understand, debug, or extend it—and that person is often you in six months.

Quality is not perfection or aesthetic preference. It delivers three concrete operational outcomes:

- **Changeability:** Features and fixes are inexpensive because the code is easy to navigate and safe to modify.
- **Reliability:** Fewer defects reach production, and the ones that do are fast to diagnose and isolate.
- **Team Velocity:** New developers become productive quickly, and code reviews focus on architecture and correctness rather than style debates.

### The Stakes for AI & LLM Systems
For AI systems, the stakes are significantly higher. LLM-backed systems introduce non-determinism (unpredictable model output, prompt drift, retrieval quality variances, vendor model deprecations, latency spikes, and token billing). Therefore, the deterministic parts of the system must be as clean, typed, and testable as possible. 

> **Core Goal:** Build a thin, strictly fenced layer of non-determinism surrounded by boring, robust, and reliable code.

**A Useful Mindset:** Optimize for the reader. Ask *“could a new teammate understand this in five minutes?”* before asking *“is this clever?”*

---

## 2. Naming Conventions

Good names eliminate comments and make logic errors visible at a glance.

### Guidelines
- **Name by meaning, not type:** Use `retry_count`, not `n` or `int_value`.
- **Functions are verbs:** `fetch_user()`, `validate_token()`, `extract_paper_concepts()`.
- **Classes and variables are nouns:** `UserRepository`, `max_retries`, `PaperChunk`.
- **Booleans read as questions:** `is_active`, `has_permission`, `should_retry`.
- **Avoid vague filler words:** Eliminate `data`, `info`, `manager`, `helper`, `util`, `temp`. If you cannot name an object precisely, its design is likely unfocused.
- **Include units in names:** `timeout_seconds`, `size_bytes`, `price_cents`, `latency_ms`. Unit mismatch is one of the most common causes of production outages.
- **One term per concept:** Do not mix `fetch`, `get`, `retrieve`, and `load` for the same operational concept across different files.
- **Mirror domain vocabulary:** If product specifications refer to a "workspace", do not call it a `tenant` in one file and an `org` in another.

```python
# ❌ Before: The reader must reverse-engineer the author's intent
def proc(d, t):
    r = []
    for x in d:
        if x['ts'] > t:
            r.append(x)
    return r

# ✅ After: Signature and implementation are immediately self-explanatory
def events_after(events: list[Event], cutoff: datetime) -> list[Event]:
    return [event for event in events if event.timestamp > cutoff]
```

---

## 3. Small, Focused Functions

A function should perform **one task at one level of abstraction**.

### Warning Signs (Heuristics)
- You have to scroll vertically to read the function.
- It nests more than three levels deep (`if` within `for` within `if`).
- Its name contains conjunctions: `validate_and_save_and_notify()`.
- It takes more than 4 positional parameters.
- It mixes high-level orchestration with low-level string manipulation or SQL parsing.

### Use Guard Clauses
Each precondition becomes its own early return. This flattens the execution path and leaves the "happy path" unindented at the end of the function.

*(Note: Grouping conditions into a large `if (A or B or C)` statement is not a guard clause; it merely obscures individual reasons for failure).*

```python
# ❌ Deeply nested: the happy path is buried and hard to follow
def ship_order(order: Order) -> bool:
    if order.is_paid:
        if order.items:
            if order.address is not None:
                carrier.ship(order)
                return True
    return False

# ✅ Guard clauses: each precondition verified early, happy path at root level
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

> **Further Improvements:**  
> 1. If "cannot ship" is unexpected rather than routine, raise an explicit domain exception (`OrderNotPaidError`) so the caller receives the actual failure reason rather than a bare `False`.  
> 2. Reject `None` for the order itself at the system boundary; do not let invalid objects penetrate inner domain functions.

### Parameter Objects & Keyword-Only Arguments
Bundle related arguments into immutable objects and enforce keyword-only arguments for optional flags:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class SearchFilters:
    tenant_id: str
    created_after: datetime | None = None
    tags: tuple[str, ...] = ()

def search_documents(query: str, filters: SearchFilters, *, limit: int = 20) -> list[Document]:
    ...
```

### Avoid Boolean Flag Arguments
Passing `export_report(report, True, False)` is completely unreadable at the call site and usually indicates that the function has multiple responsibilities.

```python
# ❌ Unclear at call site; function does two distinct jobs
export_report(report, True)

# ✅ Clear: separate functions or an explicit enum
export_report_as_pdf(report)
export_report_as_csv(report)
```

### Separate Commands from Queries (CQS)
A function that modifies state should not return unexpected computed results, and a query function should never execute side-effects. Hidden mutations violate the principle of least surprise.

---

## 4. Core Principles & Common Misunderstandings

| Principle | True Meaning | Common Misuse |
| :--- | :--- | :--- |
| **DRY** | Do not duplicate *knowledge* across the codebase. | Merging code that merely looks similar, producing a premature abstraction tangled with conditional flags. |
| **KISS** | Prefer the simplest implementation that fulfills requirements. | Confusing "simple" with "compressed", "one-liners", or "clever". |
| **YAGNI** | Do not build speculative features until required. | Omitting basic extensibility and typing that current requirements already demand. |
| **Separation of Concerns** | Keep distinct responsibilities apart. | Over-fragmenting code into dozens of one-line files where no flow can be followed. |
| **Least Surprise** | Code behaves exactly as a typical reader expects. | Concealing database writes or network calls inside getter functions or properties. |

### Duplication vs. The Wrong Abstraction
- **Duplicated Knowledge:** A business rule, tax formula, or enum set. This *must* reside in one single place.
- **Duplicated Shape:** Two functions that format receipts and invoices might look identical today but evolve along completely different business paths tomorrow. Merging them prematurely forces every future change through brittle `if kind == 'invoice'` checks.
- **Heuristic:** Tolerate code duplication until you have observed the exact same requirement three times (Rule of Three), then extract the abstraction.

---

## 5. SOLID Principles in Plain Language

Treat SOLID as a shared vocabulary for architectural design reviews, not as an inflexible dogmatic checklist.

| Principle | Plain Meaning | What It Looks Like in Practice |
| :--- | :--- | :--- |
| **Single Responsibility (SRP)** | A module has only one reason to change. | Parsing LaTeX math is decoupled from database storage and HTTP handlers. |
| **Open / Closed (OCP)** | Add behavior by adding new code, not by modifying stable existing logic everywhere. | Supporting a new LLM provider requires creating a new client class implementing a protocol, not inserting 5 `if provider == ...` branches across the codebase. |
| **Liskov Substitution (LSP)** | Subclasses must honor the contract of their base class. | A `ReadOnlyRepository` subclass must not throw an unexpected exception on `.save()` if callers were promised a standard repository contract. |
| **Interface Segregation (ISP)** | Small, specific interfaces beat monolithic ones. | Consumers depend on `Notifier`, not on an enormous 50-method `CloudPlatformClient`. |
| **Dependency Inversion (DIP)** | High-level logic depends on abstractions; dependencies are injected. | Business services accept a `StorageService` protocol rather than directly instantiating an AWS S3 SDK. |

### Concrete Dependency Inversion Example (Python Protocol)

```python
from typing import Protocol, NewType

UserId = NewType('UserId', str)

class Notifier(Protocol):
    def send(self, user_id: UserId, message: str) -> None: ...

class SignupService:
    def __init__(self, users: UserRepository, notifier: Notifier) -> None:
        self._users = users
        self._notifier = notifier

    def register(self, email: str) -> User:
        user = self._users.add(email)
        self._notifier.send(user.id, "Welcome to the platform!")
        return user

# In production: wire in an SESNotifier or SendgridNotifier.
# In unit tests: wire in a FakeNotifier that records calls to an in-memory list.
# No mock monkeypatching required!
```

---

## 6. Code Smells & Typical Remedies

Smells are warning indicators, not automatic bugs. Investigate the underlying context before refactoring.

| Code Smell | Why It Degrades Maintainability | Proven Remedy |
| :--- | :--- | :--- |
| **Long Method / Class** | Does too much; difficult to test exhaustively. | Extract focused helper functions or collaborator classes. |
| **Magic Numbers / Strings** | `if status == 3:` hides business domain rules. | Extract named constants or enums (`OrderStatus.PAID`). |
| **Deep Nesting** | High cognitive load; hides edge-case returns. | Use guard clauses and early exits. |
| **Long Parameter List** | Indicates an unexpressed domain concept. | Group parameters into a frozen dataclass or Pydantic model. |
| **Boolean Flags** | Function is doing two distinct tasks. | Split into two named functions or use an explicit enum. |
| **God Object** | One class controls all logic; every PR touches it. | Decompose by domain responsibility. |
| **Primitive Obsession** | Raw strings/ints invite accidental parameter swaps. | Use Value Objects (`UserId`, `EmailAddress`, `Money`). |
| **Feature Envy** | A method queries another object's fields continuously. | Move the method onto the data-owning object. |
| **Dead / Commented Code** | Clutters reviews and misleads debugging sessions. | Delete immediately; Git history preserves it permanently. |
| **Swallowed Exceptions** | `except: pass` hides critical production bugs. | Catch specific exceptions, log context, or re-raise. |
| **Shotgun Surgery** | A single conceptual change touches 15 files. | Consolidate the scattered responsibility into one module. |
| **Mutable Shared State** | Race conditions and unpredictable concurrency bugs. | Use immutable models and explicit ownership. |

---

## 7. Comments & Docstrings

Comments explain **WHY**, not **WHAT**. The code itself already documents what is happening.

```python
# ❌ Bad: Restates the obvious syntax
# loop over users and send email
for user in users:
    send_email(user)

# ✅ Good: Explains a non-obvious business constraint or external quirk
# The upstream API silently drops payloads exceeding 50 items (INC-8812),
# so we partition into batches of 50.
BATCH_SIZE = 50
```

- **`TODO` Comments:** Must include an issue ticket number or owner name (e.g., `# TODO(CORE-204): Migrate to batch endpoint`). Unassigned TODOs become permanent codebase noise.
- **Docstrings:** Document behavior, preconditions, thrown exceptions, units of measurement, and an example for non-obvious algorithms. Do not redundantly restate type hints that are already in the signature.

---

## 8. Robust Error Handling

Classify every failure before writing handling logic:

| Failure Category | Examples | Correct Response |
| :--- | :--- | :--- |
| **Programmer Error** | Passing `None` where a string is mandatory, index out of range. | Fail fast and loudly; fix the bug in code. |
| **Expected Domain Failure** | Insufficient funds, invalid password, duplicate username. | Raise specific domain exception or return a typed error result. |
| **Infrastructure Failure** | Upstream timeout, connection reset, HTTP 503. | Retry if idempotent (with jittered backoff), or fail gracefully. |

### Practical Error Handling Rules
1. **Catch Specific Exceptions:** Never write `except Exception:` unless logging with full context and re-raising.
2. **Preserve Root Cause:** When re-raising or wrapping exceptions, use exception chaining: `raise ServiceUnavailable(...) from exc`.
3. **Log Once at the Boundary:** Do not catch, log, and re-raise at every layer of the architecture. This produces duplicate log spam that drowns out the real root cause.
4. **Use Custom Domain Exceptions:**

```python
class DomainError(Exception):
    """Base class for all business domain errors."""

class InsufficientCredits(DomainError):
    def __init__(self, account_id: str, shortfall: int) -> None:
        super().__init__(f"Account {account_id} requires {shortfall} more credits")
        self.account_id = account_id
        self.shortfall = shortfall
```

---

## 9. Making Illegal States Unrepresentable

Design domain structures using the type system so that invalid data cannot physically exist:

```python
from dataclasses import dataclass
from enum import Enum
from typing import NewType

UserId = NewType('UserId', str)

class ExtractionStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

@dataclass(frozen=True)
class Money:
    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValueError("amount_cents cannot be negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be a 3-letter ISO code")
```

### Validate at Boundaries, Trust on the Inside
Validate external payloads (HTTP request bodies, queue messages, raw file uploads, and LLM output strings) strictly at the outer boundary using schemas. Once validated, pass strongly-typed objects into inner domain functions so inner code does not need defensive validation checks.

```python
from pydantic import BaseModel, Field

class CreatePaperRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    page_count: int = Field(gt=0, le=200)
    tags: list[str] = Field(default_factory=list)
```
