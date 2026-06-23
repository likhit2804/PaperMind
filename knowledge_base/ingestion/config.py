import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Ensure environment variables are loaded from the root .env
load_dotenv()

class IngestionSettings(BaseSettings):
    app_name: str = "CogniWeave Ingestion"
    # parents[2] from knowledge_base/ingestion/config.py -> knowledge_base/ingestion -> knowledge_base -> ml (root)
    base_dir: Path = Path(__file__).resolve().parents[2]
    knowledge_base_dir: Path = base_dir / "knowledge_base"

    # LLM Settings
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = IngestionSettings()

def get_llm(temperature: float = 0.2):
    """Returns a Gemini chat model via LangChain with retry policies."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=temperature,
        google_api_key=settings.gemini_api_key,
        max_retries=3,
    )
