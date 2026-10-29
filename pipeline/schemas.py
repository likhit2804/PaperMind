"""
pipeline/schemas.py — Pydantic output schemas for PaperMind AI extraction stages.
Enforces strict boundary validation and handles missing/malformed model fields.
"""

from pydantic import BaseModel, Field


class ConceptMetadataOutput(BaseModel):
    """Schema for paper title and canonical domain seeds extraction."""

    title: str = Field(
        default="Research Paper",
        description="The extracted canonical title of the research paper",
    )
    canonical_seeds: list[str] = Field(
        default_factory=list,
        description="List of 25-35 core domain terms and theoretical concepts",
    )


class NotationItem(BaseModel):
    """Schema for a single mathematical variable/symbol definition."""

    symbol: str = Field(min_length=1, description="Mathematical symbol (e.g. L_H, \\alpha)")
    definition: str = Field(min_length=1, description="Contextual definition of the symbol")


class EquationItem(BaseModel):
    """Schema for an individual extracted LaTeX display equation."""

    label: str = Field(description="Equation label or anchor (e.g. Equation (1))")
    latex_equation: str = Field(description="Clean, display-math LaTeX equation enclosed in $$")
    explanation: str = Field(default="", description="1-sentence contextual description")
    notations: list[NotationItem] = Field(
        default_factory=list,
        description="List of symbols defined in this equation",
    )


class BatchedEquationsOutput(BaseModel):
    """Schema for batched equation extraction responses."""

    equations: list[EquationItem] = Field(
        default_factory=list,
        description="List of structured equations extracted by AI",
    )
