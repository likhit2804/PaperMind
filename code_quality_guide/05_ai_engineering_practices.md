# 05. AI Engineering Practices

> **Module:** LLM Systems, RAG & AI Architecture  
> **Source:** Section 6 of the Revised Code Quality Guide  
> **Related:** [01. Clean Code](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) | [02. Backend Reliability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md) | [04. Testing Strategy](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/04_testing_strategy.md)

---

## 1. Core Architectural Philosophy

LLM-backed features introduce components that are **non-deterministic, high-latency, billed per token, controlled by third parties, and subject to silent provider updates**.

> **The Central Design Goal:**  
> Confine non-determinism to a thin, strictly fenced layer and surround it with ordinary, strongly-typed, thoroughly-tested deterministic code.

### Foundational AI Principles
- **Treat Model Output as Untrusted User Input:** Validate output strictly against schemas before allowing any downstream code to consume it. Never pass raw model strings into `eval()`, shell executors, database queries, or URL fetchers.
- **Keep the Model Call at the Edge:** Prompt preparation, context retrieval, chunking, filtering, and post-processing are deterministic algorithms and should be written as pure functions that can be tested with zero live API calls.
- **Unified, Observable Client Interface:** Consolidate timeouts, retries, cost calculation, and logging into a single client wrapper your code controls.
- **Measure with Evals, Never "Eyeball":** A prompt modification is a production code deployment. You cannot know whether a prompt change improved or degraded performance until measured against an evaluation dataset.

---

## 2. A Pipeline of Small, Separable Steps

Decompose complex AI workflows into distinct, isolated stages. Each stage must have explicit inputs, outputs, and dedicated unit tests:

| Pipeline Stage | Nature | How to Test & Verify |
| :--- | :--- | :--- |
| **1. Input Sanitization** | Deterministic | Fast unit tests verifying boundary limits and bad characters. |
| **2. Context Retrieval (RAG)** | Deterministic (given an index) | Measure Recall@K, Precision@K, and MRR against labeled query sets. |
| **3. Prompt Assembly** | Deterministic | Unit and snapshot tests verifying template rendering and variable injection. |
| **4. Model Completion** | Non-Deterministic | Fake client in unit tests; automated evaluation suites for quality. |
| **5. Output Schema Validation** | Deterministic | Unit tests parsing valid, malformed, and adversarial JSON outputs. |
| **6. Business Rule Post-Processing** | Deterministic | Unit tests for domain logic and permission filtering. |
| **7. Persistence & Caching** | Deterministic | Integration tests verifying database and cache writes. |

> ⚠️ **Anti-Pattern:** Putting prompt building, the API call, regex extraction, and database persistence into one monolithic 300-line function. It prevents unit testing and makes prompt iteration dangerous.

---

## 3. One Client Interface for Every Provider

Wrap external provider SDKs (Google GenAI, OpenAI, Anthropic) behind an internal protocol that your application owns.

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
    prompt_version: str = ""  # Crucial for telemetry and evaluation tracking


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str  # Actual model that answered
    input_tokens: int
    output_tokens: int
    latency_ms: int
    finish_reason: str  # 'stop', 'length' (truncated), 'safety'


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

### Production Client Implementation
Cross-cutting operational concerns live exclusively inside the client implementation:

```python
import time


class ProviderClient:
    def __init__(self, sdk_client, *, timeout_s: float, usage_log: UsageLog) -> None:
        self._sdk = sdk_client
        self._timeout_s = timeout_s
        self._usage_log = usage_log

    def complete(self, request: LLMRequest) -> LLMResponse:
        start_time = time.monotonic()

        # Bounded retries on transient errors only (429, timeouts)
        raw_response = call_with_retry(
            lambda: self._sdk.generate_content(request),
            retry_on=(RateLimitError, TimeoutError, ServiceUnavailableError),
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        response = self._parse_response(raw_response, elapsed_ms)

        # Centralized observability: track tokens, latency, cost, and prompt version
        self._usage_log.record(request, response)
        return response
```

---

## 4. Structured Outputs with Bounded Repair Loops

Whenever code consumes model output, enforce a strict JSON schema and handle parsing failures with a **bounded repair loop** (maximum 1 attempt):

```python
from pydantic import BaseModel, Field, ValidationError


class ConceptExtractionResult(BaseModel):
    concept_name: str = Field(min_length=1, max_length=100)
    category: str
    definition: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)


MAX_REPAIR_ATTEMPTS = 1


def extract_concepts(llm: LLMClient, context_text: str) -> ConceptExtractionResult:
    request = build_concept_request(context_text)

    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        response = llm.complete(request)

        # 1. Truncation Check: A truncated response is an invalid response
        if response.finish_reason == "length":
            raise LLMOutputTruncatedError("Model output truncated by token limit")

        # 2. Schema Validation
        try:
            return ConceptExtractionResult.model_validate_json(extract_json(response.text))
        except ValidationError as exc:
            if attempt == MAX_REPAIR_ATTEMPTS:
                raise LLMOutputInvalidError(f"Validation failed after repair: {exc}")

            # One bounded repair attempt: show the model its own error
            request = with_repair_instruction(request, response.text, str(exc))
```

> **Rules for Repair Loops:**
> - Never run an unbounded `while True` repair loop. It leads to cost and latency spikes.
> - Check `finish_reason`. If the model was truncated, attempting to parse the broken JSON causes silent data corruption.
> - Define explicit fallback behavior when validation fails: default value, human review queue, or an explicit domain error.

---

## 5. Prompts are Code

Prompts dictate system behavior just as functions do. Manage them with identical engineering discipline:

1. **Versioned Files, Not Strings:** Store prompts in dedicated files (`prompts/concepts/v2.user.jinja`), never as raw strings concatenated inside Python files.
2. **Strict Template Rendering:** Use template engines like Jinja2 with `StrictUndefined` so that a missing variable causes an immediate error rather than rendering a blank space.
3. **Prompt Changelog:** Maintain `prompts/CHANGELOG.md` detailing the rationale for each version bump.
4. **Delimiters for Untrusted Content:** Clearly separate system instructions from untrusted user documents using delimiters (e.g., `"""` or `<paper_context>`).

```
prompts/
  concept_extraction/
    v1.system.md
    v1.user.jinja
    v2.user.jinja
    CHANGELOG.md   # "v2: Added negative constraints to stop over-extracting math variables"
```

---

## 6. Deterministic Testing with Fake LLMs

Write comprehensive unit tests for your pipelines using a deterministic fake client:

```python
class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.recorded_requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.recorded_requests.append(request)
        return LLMResponse(
            text=self._responses.pop(0),
            model=request.model,
            input_tokens=10,
            output_tokens=20,
            latency_ms=50,
            finish_reason="stop",
        )


def test_repair_loop_recovers_from_single_malformed_json():
    fake_llm = FakeLLM(
        [
            "Malformed JSON output: { name: 'Transformer' }",  # Attempt 1 fails
            '{"concept_name": "Transformer", "category": "Model", "definition": "Attention-based architecture.", "confidence": 0.95}',  # Attempt 2 succeeds
        ]
    )

    result = extract_concepts(fake_llm, "Paper excerpt...")
    assert result.concept_name == "Transformer"
    assert len(fake_llm.recorded_requests) == 2  # Proves exactly one repair attempt occurred
```

---

## 7. Evals: Measuring Model Output Quality

Unit tests verify that your plumbing works. **Evals** determine whether your AI model outputs are accurate and whether a prompt change improved or degraded performance.

### 1. Build a Golden Dataset
- Curate 20–50 real-world, anonymized inputs with human-verified expected outputs.
- Include edge cases: empty papers, corrupted formatting, extreme lengths, and prompt injection attempts.
- Version the dataset in Git (`tests/evals/golden_dataset.jsonl`). Keep a held-out evaluation slice to avoid overfitting prompts.

### 2. Score in Layers (Cheapest to Most Expensive)
1. **Deterministic Checks (Free & Instant):** Schema adherence, JSON validity, exact category matches, regex constraints, and checking that cited page numbers actually exist.
2. **Reference-Based Metrics (Fast):** Semantic embedding similarity or ROUGE/BLEU scores against ground truth.
3. **LLM-as-Judge (Selective):** Use a larger model (e.g., Gemini 1.5 Pro) with a strict rubric for qualitative metrics (e.g., hallucination rate, clarity).

### 3. Mitigating LLM-as-Judge Pitfalls
- **Narrow, Binary Rubrics:** Ask *"Does the definition contradict the source excerpt? [Yes/No]"* rather than asking for a subjective 1–10 rating.
- **Randomize Pairwise Order:** LLM judges exhibit position bias (favoring the first option presented). Swap orders and verify consensus.
- **Calibrate with Humans:** Regularly test agreement between LLM judges and human engineer ratings.

---

## 8. Retrieval-Augmented Generation (RAG) Best Practices

Most complaints that "the model hallucinated" are actually retrieval bugs where the relevant context was never fetched.

- **Version the Index:** The embedding model, chunking algorithm, and chunk size define an index version. Changing any parameter requires re-indexing.
- **Enforce Access Control Before Retrieval:** Filter by user and tenant permissions *before* injecting context into the prompt. Never rely on the model to enforce permissions.
- **Measure Retrieval Quality Independently:**
  - **Recall@K:** Is the ground-truth document chunk contained in the top $K$ results?
  - **Precision@K:** What percentage of retrieved chunks are genuinely relevant?
  - **MRR (Mean Reciprocal Rank):** How high up in the ranking does the first relevant chunk appear?
- **Verify Citations in Code:** If the model outputs citations `[Page 4, Equation 2]`, programmatically verify that Page 4 was in the retrieved set.

---

## 9. Agent Safety & Tool Security

When models can execute tools (e.g., calling APIs, querying databases):
- **Tools are Strongly-Typed Functions:** Validate arguments through schemas before execution.
- **Never Pass Raw Output to Interpreters:** Never let an LLM generate raw SQL or shell commands without parameterization and validation.
- **Least Privilege:** Tool permissions must be scoped to the authenticated user's credentials, not the backend service's admin credentials.
- **Require Confirmation for Risky Side-Effects:** High-consequence actions (deleting data, executing financial transfers) require human approval.
- **Hard Bounds on Agent Loops:** Always set maximum step counts, token budgets, and execution timeouts.

---

## 10. AI Security: Prompt Injection & Privacy

- **Prompt Injection Defense is Architectural:** System prompts and delimiters reduce, but do *not* prevent, prompt injection. Protect systems by:
  - Validating all tool arguments in code.
  - Ensuring the model has zero access to secrets or private environment variables.
  - Disallowing self-authorization by the model.
- **Data Minimization:** Strip unnecessary PII before sending context to external providers.
- **Sanitize Telemetry:** Never log raw API keys, passwords, or sensitive customer data in prompt trace logs.
- **Tenant Isolation:** Cache keys and retrieval indexes must partition strictly on tenant ID.
