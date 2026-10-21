"""
pipeline/tests/test_fakes.py — Deterministic Test Doubles & Fake Gemini Client.
Enables unit testing the extraction pipeline in CI without API keys or token costs.
"""
from dataclasses import dataclass, field
from pipeline.schemas import ConceptMetadataOutput, BatchedEquationsOutput


@dataclass
class FakeLLMResponse:
    text: str


class FakeGeminiModel:
    """A deterministic in-memory fake Gemini client for unit tests."""
    def __init__(self, canned_responses: list[str] | None = None):
        self.canned_responses = list(canned_responses or [])
        self.calls: list[str] = []

    def generate_content(self, prompt: str, **kwargs) -> FakeLLMResponse:
        self.calls.append(prompt)
        if self.canned_responses:
            return FakeLLMResponse(text=self.canned_responses.pop(0))
        return FakeLLMResponse(text='{"title": "Test Paper", "canonical_seeds": ["test"]}')


def test_concept_metadata_schema_valid():
    """Verify schema parses valid JSON correctly."""
    raw = '{"title": "Attention Is All You Need", "canonical_seeds": ["transformer", "self-attention"]}'
    parsed = ConceptMetadataOutput.model_validate_json(raw)
    assert parsed.title == "Attention Is All You Need"
    assert "transformer" in parsed.canonical_seeds


def test_equation_schema_valid():
    """Verify equation output schema parses valid LaTeX outputs."""
    raw = '''{
        "equations": [
            {
                "label": "Equation (1)",
                "latex_equation": "$$\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$",
                "explanation": "Defines Scaled Dot-Product Attention.",
                "notations": [
                    {"symbol": "Q", "definition": "Queries matrix"},
                    {"symbol": "d_k", "definition": "Dimension of keys"}
                ]
            }
        ]
    }'''
    parsed = BatchedEquationsOutput.model_validate_json(raw)
    assert len(parsed.equations) == 1
    assert parsed.equations[0].label == "Equation (1)"
    assert parsed.equations[0].notations[0].symbol == "Q"


def test_fake_gemini_client():
    """Verify FakeGeminiModel replays canned responses deterministically."""
    fake = FakeGeminiModel([
        '{"title": "Paper A", "canonical_seeds": ["seed_a"]}',
        '{"title": "Paper B", "canonical_seeds": ["seed_b"]}',
    ])
    
    res1 = fake.generate_content("prompt 1")
    res2 = fake.generate_content("prompt 2")
    
    assert "Paper A" in res1.text
    assert "Paper B" in res2.text
    assert len(fake.calls) == 2


def test_golden_benchmark_suite():
    """Verify that golden benchmark suite loads, validates schemas, and achieves target recall."""
    from pipeline.evals.run_eval import run_benchmark_suite
    results = run_benchmark_suite(verbose=False)
    assert results["total_cases"] >= 6
    assert results["schema_conformity_rate"] == 1.0
    assert results["equation_pass_rate"] == 1.0
    assert results["average_recall"] >= 0.9
