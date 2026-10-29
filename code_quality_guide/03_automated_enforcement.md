# 03. Automated Enforcement

> **Module:** Tooling, Automation & CI/CD  
> **Source:** Section 4 of the Revised Code Quality Guide  
> **Related:** [00. Project Adoption Plan](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/00_project_adoption_plan_and_commit_workflow.md) | [04. Testing Strategy](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/04_testing_strategy.md) | [06. Code Review](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/06_code_review_and_collaboration.md)

---

## 1. The Core Principle: Automated Guardrails

Rules that depend on human memory or peer reminders during code review inevitably fail. To build a maintainable engineering culture:

> **The Single Source of Truth:**  
> The exact same validation commands must run on a developer’s local laptop, in pre-commit git hooks, and in CI pull request pipelines.

Automating style, syntax, security, and type checks frees human engineers to focus code reviews exclusively on system architecture, algorithmic correctness, and business value.

---

## 2. Multi-Language Standard Toolchain

| Quality Layer | Python Ecosystem | JavaScript / TypeScript | Go Ecosystem |
| :--- | :--- | :--- | :--- |
| **Code Formatter** | `ruff format` (or Black) | Prettier / Biome | `gofmt` |
| **Linter** | `ruff` (replaces flake8, isort, etc.) | ESLint | `golangci-lint`, `go vet` |
| **Type Checker** | `mypy` or `pyright` | `tsc --strict` | Built-in compiler |
| **Test Runner** | `pytest` | Vitest / Jest | `go test` |
| **Dependency Audit** | `pip-audit` | `npm audit` / `pnpm audit` | `govulncheck` |
| **Security Linter** | Ruff `S` rules / Bandit | `eslint-plugin-security` | `gosec` (via golangci-lint) |
| **Secret Scanning** | Gitleaks / TruffleHog | Gitleaks / TruffleHog | Gitleaks / TruffleHog |
| **Lockfile Hygiene** | `uv.lock` or `poetry.lock` | `package-lock.json` / `pnpm-lock.yaml` | `go.sum` |

---

## 3. Code Formatter: Eliminating Style Debates

A code formatter ends subjective whitespace and styling arguments. Pick an opinionated formatter, integrate it into your editor on save, and run it in pre-commit hooks and CI. 

**Rule:** Nobody should ever comment on whitespace, indentation, or quotation marks during a pull request review.

---

## 4. Modern Linting with Ruff & ESLint

Linters catch unused variables, unreachable code paths, shadowed names, performance traps, and genuine runtime bugs before execution.

### Recommended Python Configuration (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
# E/F: pycodestyle & pyflakes, I: isort (import sorting), B: bugbear (likely bugs),
# UP: pyupgrade (modern syntax), S: flake8-bandit (security), 
# C90: mccabe complexity, SIM: flake8-simplify
select = ["E", "F", "I", "B", "UP", "S", "C90", "SIM"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.per-file-ignores]
# Asserts are legitimate in test suites
"tests/**" = ["S101"]
```

**Zero-Warning Policy:** Treat lint failures as hard errors in CI. Never allow warnings to accumulate. If a specific rule must be suppressed, require an inline `# noqa: <rule>` comment accompanied by a documented reason.

---

## 5. Type Checking: Catching Bugs Before Runtime

Type annotations turn entire categories of runtime errors (`TypeError: unsupported operand`, `AttributeError: NoneType has no attribute`) into instant IDE feedback, while serving as verified documentation.

### Recommended Mypy Configuration (`pyproject.toml`)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true
warn_return_any = true

# On legacy codebases: relax untyped definitions for legacy folders temporarily
[[tool.mypy.overrides]]
module = "pipeline.legacy.*"
disallow_untyped_defs = false
```

### Type Adoption Hierarchy
1. Type public API boundaries and service layer methods first.
2. Type data structures and domain models.
3. Type internal helper routines.
4. Enable `strict` flags across all new modules.
5. In TypeScript, mandate `strict: true` from day one. Avoid loose `any` casts without explicit justification comments.

---

## 6. Pre-Commit Hooks: Instant Local Feedback

Pre-commit hooks intercept commits on a developer's machine, executing fast formatting, linting, and secret scanning checks.

### Rules for Pre-Commit Hooks
- **Fast Execution (< 5 seconds):** If hooks take 30 seconds, developers will bypass them using `git commit --no-verify`. Run only fast formatters and linters locally; reserve full test suites for CI.
- **CI Remains the Final Gate:** Because local hooks can be skipped or disabled, CI is the ultimate authority.

### Recommended `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

---

## 7. Fast, Parallel Continuous Integration (CI)

A continuous integration pipeline must be **fast, parallel, and deterministic**. If a PR build takes 30 minutes, delivery grinds to a halt. Aim for builds under 8–10 minutes.

### GitHub Actions Pipeline Architecture (`.github/workflows/ci.yml`)

```yaml
name: CI Pipeline

on:
  pull_request:
    branches: [main]

jobs:
  static-checks:
    name: Lint & Typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy .

  unit-tests:
    name: Fast Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/unit -v --durations=10

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: app_test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/integration -v

  security-scan:
    name: Security & Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gitleaks/gitleaks-action@v2
      - run: pip install pip-audit && pip-audit
```

---

## 8. Cyclomatic Complexity & Static Analysis

Track **cyclomatic complexity** (the number of linearly independent paths through a function).

- **Heuristic:** Functions with complexity $> 10$ are difficult to understand and test exhaustively. Treat them as primary candidates for extraction.
- **Track Trends, Not Just Absolutes:** An isolated function with complexity 12 may be an acceptable parser table, but a steady upward trend across core modules signals accumulating technical debt.

---

## 9. The "Ratchet" Strategy for Existing Codebases

Turning on strict linters or strict type checking on an existing, multi-year codebase often generates thousands of violations. 

> 🚫 **DO NOT:**
> - Attempt a massive, multi-week refactor that blocks all feature delivery.
> - Disable the strict rules globally.

> ✅ **THE PROVEN RATCHET TECHNIQUE:**
> 1. **Establish a Baseline:** Many tools (including Mypy, ESLint, and SonarQube) support recording current violations into a baseline file. CI is configured to fail **only on new violations**.
> 2. **Apply Formatter in One Dedicated Commit:** Run `ruff format` or `prettier` on the entire repo once. List that commit's SHA in `.git-blame-ignore-revs` so historical blame remains clean.
> 3. **Diff Coverage Enforcement:** In PRs, enforce 80%+ test coverage and zero lint errors on **changed lines only**.
> 4. **Progressive Tightening:** As engineers touch legacy modules under the Boy Scout rule, legacy violations in that file are resolved, systematically ratcheting quality upward.
