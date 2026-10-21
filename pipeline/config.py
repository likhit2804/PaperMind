"""
pipeline/config.py — Strongly-typed 12-factor configuration for PaperMind Python Pipeline.
Validates environment variables at boot and masks API keys with SecretStr.
"""
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Workspace root is one level up from pipeline/
PIPELINE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = PIPELINE_DIR.parent
ENV_FILE = WORKSPACE_ROOT / ".env"


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base Paths
    workspace_root: Path = WORKSPACE_ROOT
    pipeline_dir: Path = PIPELINE_DIR

    # Gemini & AI Model Configuration
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
        description="Google Gemini API key for pipeline AI extractions",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="Optional OpenAI API key for fallback extractions",
    )
    llm_model: str = Field(
        default="gemini-1.5-flash",
        validation_alias="LLM_MODEL",
        description="Target model identifier",
    )

    # Reliability & Timeout Controls
    llm_timeout_s: float = Field(
        default=30.0,
        ge=5.0,
        le=180.0,
        validation_alias="LLM_TIMEOUT_SECONDS",
        description="Timeout cap for external LLM API calls in seconds",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        le=5,
        validation_alias="LLM_MAX_RETRIES",
        description="Maximum retry attempts on transient network/429 errors",
    )

    def require_gemini_key(self) -> str:
        """Returns the raw Gemini API key string, or raises a clear domain error."""
        if not self.gemini_api_key:
            raise RuntimeError(
                "❌ GEMINI_API_KEY is not configured in .env. "
                "Please configure a valid Gemini API key to execute AI extraction stages."
            )
        return self.gemini_api_key.get_secret_value()


# Centralized singleton instance
settings = PipelineSettings()
