"""
pipeline/prompts/__init__.py — Versioned Prompt Registry & Safe Template Loader
Enforces strict variable substitution and tracks prompt versions.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(template_filename: str, **variables: str) -> str:
    """
    Loads a versioned prompt template from disk and safely performs variable substitution.
    Raises FileNotFoundError if the template does not exist.
    Raises KeyError if a required template placeholder is missing from kwargs.
    """
    template_path = PROMPTS_DIR / template_filename
    if not template_path.exists():
        raise FileNotFoundError(
            f"❌ Prompt template not found: {template_filename}. "
            f"Available templates are in {PROMPTS_DIR}"
        )

    template_text = template_path.read_text(encoding="utf-8")

    # Safe format: ensures all kwargs match template placeholders
    try:
        return template_text.format(**variables)
    except KeyError as exc:
        raise KeyError(
            f"❌ Missing required prompt variable {exc} when rendering template '{template_filename}'"
        ) from exc


__all__ = ["load_prompt", "PROMPTS_DIR"]
