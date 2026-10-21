# 04. Testing Strategy

> **Module:** Verification & Quality Assurance  
> **Source:** Section 5 of the Revised Code Quality Guide  
> **Related:** [03. Automated Enforcement](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/03_automated_enforcement.md) | [05. AI Engineering Practices](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md) | [07. Refactoring](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/07_refactoring_and_technical_debt.md)

---

## 1. The Test Pyramid & When to Bend It

- **Unit Tests (Many):** Ultra-fast (< 5ms each), run fully in-memory, zero network or disk I/O. Best for pure business logic, calculations, parsers, and data transformations.
- **Integration Tests (Some):** Verify real interaction with external resources (PostgreSQL, Redis, RabbitMQ, HTTP routes). In database-heavy or I/O-intensive services, integration tests often catch far more production bugs than unit tests.
- **End-to-End Tests (Few):** Drive end-to-end user journeys (e.g., uploading a PDF, extracting concepts, querying HexiBot). They are slow and brittle; keep them strictly focused on critical user workflows.

> **When to Bend the Pyramid:** The classic pyramid is a starting heuristic. A service that acts primarily as a high-throughput data ingestion router over Postgres may rightfully maintain a thicker integration layer than a pure mathematical calculation engine.

---

## 2. Anatomy of an Exceptional Test

An exceptional automated test exhibits five key qualities:

1. **Fast & Deterministic:** Zero flakiness. Never depends on the system clock, internet connectivity, or execution order.
2. **Readable (Arrange, Act, Assert):** A developer reading a failing test should understand within 15 seconds what behavior failed.
3. **Tests Behavior, Not Implementation:** Refactoring the internal implementation of a class without changing its contract must never break tests.
4. **Independent:** Each test creates its own fixtures and runs safely in parallel or in random order.
5. **Precise Assertions:** Assert on specific domain values and error types, never just "no exception was raised."

### Determinism via Injected Dependencies (Clock & Randomness)

```python
import pytest
from datetime import datetime, timezone, timedelta

# Inject fixed time to eliminate clock drift bugs
FROZEN_TIME = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

def test_expired_token_is_rejected():
    # Arrange: Explicitly inject expired timestamp
    token = make_token(expires_at=FROZEN_TIME - timedelta(minutes=1))
    
    # Act & Assert
    with pytest.raises(TokenExpiredError):
        validate_session(token, current_time=FROZEN_TIME)

@pytest.mark.parametrize("total_cents, discount_pct, expected_cents", [
    (10_000, 10, 9_000),
    (999, 10, 899),      # Explicit test for fractional rounding behavior
    (0, 50, 0),
])
def test_discount_calculation(total_cents, discount_pct, expected_cents):
    assert calculate_discount(total_cents, discount_pct) == expected_cents
```

---

## 3. Test Doubles: Prefer Fakes and Real Local Services

Over-mocking (`unittest.mock.patch` everywhere) couples test suites to internal implementation details. Tests pass when refactoring breaks production, and tests fail when harmless internal renamings occur.

### The Test Double Hierarchy (Prefer from Top to Bottom)

1. **Real Local Services:** Use containerized local dependencies (e.g., Postgres or Redis started via Testcontainers or Docker Compose).
2. **Fakes:** Working in-memory implementations of an interface (e.g., `InMemoryPaperRepository` using a Python dictionary, `FakeLLMClient`). They adhere to the real interface contract and make assertions straightforward.
3. **Stubs:** Provide hardcoded responses to specific inputs.
4. **Mocks:** Verify that a specific method was invoked. Use mocks sparingly—primarily when verifying side-effects that have no observable return value (e.g., asserting an email notification was triggered exactly once).

### Database Test Isolation
Run database integration tests inside an explicit transaction that rolls back at the end of each test, or utilize isolated temporary schemas. This keeps tests completely independent and avoids slow teardown routines.

---

## 4. Eradicating Flaky Tests

A flaky test is far worse than no test: it destroys the team's trust in CI, leading engineers to ignore red builds.

### Common Causes of Flakiness
- Reliance on real wall-clock time (`time.sleep()`).
- Unordered collection assertions (`assert [1, 2] == [2, 1]`).
- Concurrent access to shared test databases.
- Real external network calls.
- Race conditions in async task scheduling.

### Team Quarantine Policy
If a test fails intermittently without code changes:
1. **Quarantine Immediately:** Move the test to `@pytest.mark.flaky` or disable it from the blocking CI path.
2. **File a High-Priority Ticket:** Assign an owner and a 1-week SLA.
3. **Fix or Delete:** If the test cannot be stabilized within one week, delete it. Never leave broken tests in CI.

---

## 5. High-Value Testing Techniques

### 1. Regression Tests
Every reported production bug must be accompanied by an automated regression test that reproduces the defect and fails *before* the fix is applied.

### 2. Property-Based Testing (Hypothesis)
Instead of hand-picking three arbitrary test inputs, define invariant properties and let the testing engine generate thousands of edge cases (empty strings, huge integers, invalid Unicode, null bytes):

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_slugify_is_idempotent(text: str):
    # Property: slugifying an already slugified string has no further effect
    assert slugify(slugify(text)) == slugify(text)
```

### 3. Contract Testing (Pact)
Verify that client and server agree on API request and response schemas so that frontend and backend changes can be deployed independently without unexpected breaking contract mismatches.

### 4. Mutation Testing (Cosmic Ray / Mutmut)
Deliberately mutates operators (`+` to `-`, `>` to `>=`) in your production code and runs the test suite. If tests still pass, your assertions are inadequate. Reserve mutation testing for mission-critical core modules (e.g., authorization, billing, math parsing).

---

## 6. Code Coverage: Signal vs. Vanity Metric

Code coverage indicates what code has **not** been executed; high coverage alone does not prove that tests are asserting correctly.

- **Measure Branch Coverage:** Line coverage can be 100% while missing 50% of decision branches.
- **Diff Coverage on Pull Requests:** Mandate that PRs maintain high test coverage (e.g., 80%+) on **newly written or modified lines**, rather than demanding an impossible global percentage on legacy codebases.
- **Focus Where Risk Lives:** Concentrate deep testing on financial calculations, permission checks, state machines, regex parsing, and concurrency boundaries.

---

## 7. Testing Legacy Code Lacking Tests: Characterization Tests

When inheriting legacy code that has zero tests:

> ⚠️ **DO NOT start refactoring immediately.** You will inadvertently introduce regressions.

### The Characterization Test Workflow
1. Write a test calling the legacy function with various real-world inputs.
2. Record the actual return values produced *today*, even if they include odd quirks or historical bugs.
3. Assert against these existing outputs:
   ```python
   def test_legacy_equation_extractor_characterization():
       # Records current system behavior as an immutable safety harness
       result = legacy_extract_equation("$$ x = 1 $$")
       assert result == {"raw": "$$ x = 1 $$", "vars": ["x"], "valid": True}
   ```
4. With this safety net in place, perform incremental refactoring. If the test fails, you know immediately that you changed behavior.
