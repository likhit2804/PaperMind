import json
import os
import re
import time
import random
import threading
from dotenv import load_dotenv
import google.generativeai as genai
from pipeline.logger import log_info, log_warn, log_error, log_debug

import _bootstrap  # noqa: F401 - Initialize sys.path, env & encoding


class AdaptiveTokenBucketRateLimiter:
    """
    Advanced Thread-Safe Token Bucket Rate Limiter with Dynamic HTTP 429 Adaptive Backoff.

    Features:
    - Token Bucket with burst capacity (e.g. 15 RPM = 0.25 tokens/sec).
    - Dynamic Exponential Backoff: Automatically pauses and slows down when 429 quota errors occur.
    - Automatic Recovery: Successful requests gradually restore normal throughput.
    """

    def __init__(self, max_rate_per_min=15.0, burst_capacity=2):
        self.max_rate_per_min = max_rate_per_min
        self.capacity = float(burst_capacity)
        self.tokens = float(burst_capacity)
        self.fill_rate = max_rate_per_min / 60.0  # tokens per second
        self.last_update = time.time()
        self.lock = threading.Lock()

        # Adaptive backoff parameters
        self.backoff_until = 0.0
        self.backoff_factor = 1.0

    def _refill(self):
        now = time.time()
        delta = now - self.last_update
        self.tokens = min(
            self.capacity, self.tokens + delta * (self.fill_rate / self.backoff_factor)
        )
        self.last_update = now

    def acquire(self, tokens_needed=1.0):
        """Block until required tokens are available and backoff window has elapsed."""
        while True:
            with self.lock:
                now = time.time()
                # Check if currently in a forced 429 backoff pause
                if now < self.backoff_until:
                    sleep_needed = self.backoff_until - now
                else:
                    self._refill()
                    if self.tokens >= tokens_needed:
                        self.tokens -= tokens_needed
                        return
                    else:
                        needed = tokens_needed - self.tokens
                        sleep_needed = needed / (self.fill_rate / self.backoff_factor)

            log_debug(
                f"Rate Limiter: waiting {sleep_needed:.2f}s for tokens (backoff_factor={self.backoff_factor:.1f})"
            )
            time.sleep(max(0.1, sleep_needed))

    def wait(self):
        """Backwards compatible alias for acquire()."""
        self.acquire(1.0)

    def report_quota_error(self, pause_seconds=8.0):
        """Triggers adaptive backoff pause when HTTP 429 or quota limit is hit."""
        with self.lock:
            now = time.time()
            self.backoff_until = max(self.backoff_until, now + pause_seconds)
            self.backoff_factor = min(self.backoff_factor * 2.0, 8.0)
            self.tokens = 0.0
            log_warn(
                f"Rate Limiter: Quota 429 error triggered. Pausing {pause_seconds}s. Backoff factor updated to {self.backoff_factor}x."
            )

    def report_success(self):
        """Gradually recovers backoff factor upon successful API responses."""
        with self.lock:
            if self.backoff_factor > 1.0:
                self.backoff_factor = max(1.0, self.backoff_factor * 0.9)
                log_debug(
                    f"Rate Limiter: API success. Recovered backoff factor to {self.backoff_factor:.2f}x."
                )


# Global rate limiter instance to coordinate calls across threads (15 RPM max, 2 burst capacity)
gemini_rate_limiter = AdaptiveTokenBucketRateLimiter(max_rate_per_min=15.0, burst_capacity=2)


def parse_json_robust(raw_text):
    """
    Cleans up a raw text string (which might be wrapped in markdown fences or contain
    trailing commas) and parses it as JSON. Returns the parsed dict/list.
    """
    text = raw_text.strip()

    # Strip markdown code blocks
    if text.startswith("```"):
        m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1).strip()

    # Try normal parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Remove trailing commas inside lists/objects using regex
    # Matches a comma followed by closing brace or bracket with optional whitespace/newline
    repaired = re.sub(r",\s*([\]}])", r"\1", text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Fallback: Extract the first balanced JSON object {...} or list [...] found in the text
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx : end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            try:
                candidate_repaired = re.sub(r",\s*([\]}])", r"\1", candidate)
                return json.loads(candidate_repaired)
            except json.JSONDecodeError:
                pass

    # If all fails, raise the original decode error
    return json.loads(raw_text)


def get_fallback_model_list(primary_model=None):
    """
    Builds the model rotation list strictly using environment variables:
    1. Primary: LLM_MODEL or AGENT_MODEL (or explicit primary_model parameter)
    2. Fallbacks: LLM_FALLBACK_MODELS (comma-separated list from .env)
    """
    raw_fallbacks = os.environ.get(
        "LLM_FALLBACK_MODELS",
        "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-1.5-flash-8b,gemini-1.5-pro",
    )
    models = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

    # Resolve primary model
    if primary_model:
        if isinstance(primary_model, str):
            primary_name = primary_model
        elif hasattr(primary_model, "model_name"):
            primary_name = primary_model.model_name.replace("models/", "")
        else:
            primary_name = (
                os.environ.get("LLM_MODEL")
                or os.environ.get("AGENT_MODEL")
                or "gemini-3.5-flash-lite"
            )
    else:
        primary_name = (
            os.environ.get("LLM_MODEL") or os.environ.get("AGENT_MODEL") or "gemini-3.5-flash-lite"
        )

    # Avoid duplication
    models = [m for m in models if m != primary_name]
    return [primary_name] + models


def call_gemini_with_retry(model, prompt, generation_config=None, max_retries=1, initial_delay=1.0):
    """
    Calls Gemini API with automatic model rotation across fallback candidates configured in .env.
    Integrates with AdaptiveTokenBucketRateLimiter for dynamic 429 backoff.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    candidates = get_fallback_model_list(primary_model=model)
    last_exception = None

    for candidate_name in candidates:
        # Wait for token from rate limiter before making API call
        gemini_rate_limiter.acquire(1.0)
        log_info(f"Gemini API: Requesting generation with model '{candidate_name}'")
        start_time = time.time()
        try:
            curr_model = genai.GenerativeModel(candidate_name)
            if generation_config:
                res = curr_model.generate_content(prompt, generation_config=generation_config)
            else:
                res = curr_model.generate_content(prompt)

            elapsed = time.time() - start_time
            log_info(f"Gemini API: Response received from '{candidate_name}' in {elapsed:.2f}s")
            gemini_rate_limiter.report_success()
            return res
        except Exception as e:
            last_exception = e
            err_msg = str(e).lower()
            if any(
                k in err_msg
                for k in [
                    "429",
                    "503",
                    "500",
                    "resource_exhausted",
                    "quota",
                    "unavailable",
                    "capacity",
                ]
            ):
                log_warn(
                    f"Gemini API: Model '{candidate_name}' returned capacity/quota error ({e}). Rotating to next fallback model..."
                )
                gemini_rate_limiter.report_quota_error(pause_seconds=2.0)
                continue
            else:
                # Non-quota error: retry once after short pause
                log_warn(
                    f"Gemini API: Model '{candidate_name}' encountered non-quota error: {e}. Retrying after {initial_delay}s..."
                )
                time.sleep(initial_delay)
                try:
                    curr_model = genai.GenerativeModel(candidate_name)
                    if generation_config:
                        res = curr_model.generate_content(
                            prompt, generation_config=generation_config
                        )
                    else:
                        res = curr_model.generate_content(prompt)
                    log_info(f"Gemini API: Retry succeeded for '{candidate_name}'")
                    gemini_rate_limiter.report_success()
                    return res
                except Exception as inner_e:
                    last_exception = inner_e
                    log_error(f"Gemini API: Model '{candidate_name}' failed on retry", inner_e)
                    continue

    log_error("Gemini API: All configured model candidates failed or hit quota limits.")
    if last_exception:
        raise last_exception
    raise RuntimeError("All configured Gemini models failed or hit quota limits.")


# ---------------------------------------------------------------------------
# Shared pipeline helpers — import these instead of duplicating per script
# ---------------------------------------------------------------------------


def clean_text(text):
    """Normalize whitespace and standard ligatures."""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    return text.strip()


def get_gemini_model(default_model=None, use_agent_model=False):
    """
    Read GEMINI_API_KEY, LLM_MODEL, and AGENT_MODEL from environment, configure genai,
    and return (model, api_key). Returns (None, None) when key is absent.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None, None
    genai.configure(api_key=api_key)

    env_var = "AGENT_MODEL" if use_agent_model else "LLM_MODEL"
    model_name = (
        os.environ.get(env_var)
        or os.environ.get("LLM_MODEL")
        or default_model
        or "gemini-1.5-flash"
    )

    model = genai.GenerativeModel(model_name)
    return model, api_key


def get_pdf_title(doc, fallback="Research Paper"):
    """Extract title from a PyMuPDF document's metadata with a safe fallback."""
    title = ""
    if hasattr(doc, "metadata") and doc.metadata:
        title = doc.metadata.get("title", "") or ""
    if not title.strip() or len(title.strip()) < 3:
        return fallback
    return title.strip()
