import json
import re
import time
import random
import google.generativeai as genai

def parse_json_robust(raw_text):
    """
    Cleans up a raw text string (which might be wrapped in markdown fences or contain
    trailing commas) and parses it as JSON. Returns the parsed dict/list.
    """
    text = raw_text.strip()
    
    # Strip markdown code blocks
    if text.startswith("```"):
        m = re.match(r'^```(?:json)?\s*(.*?)\s*```$', text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1).strip()
            
    # Try normal parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # Remove trailing commas inside lists/objects using regex
    # Matches a comma followed by closing brace or bracket with optional whitespace/newline
    repaired = re.sub(r',\s*([\]}])', r'\1', text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
        
    # Fallback: Extract the first balanced JSON object {...} or list [...] found in the text
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx:end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            try:
                candidate_repaired = re.sub(r',\s*([\]}])', r'\1', candidate)
                return json.loads(candidate_repaired)
            except json.JSONDecodeError:
                pass
                
    # If all fails, raise the original decode error
    return json.loads(raw_text)

def call_gemini_with_retry(model, prompt, generation_config=None, max_retries=5, initial_delay=2.0):
    """
    Calls Gemini model.generate_content with exponential backoff and jitter.
    Supports handling of rate limits (HTTP 429) and transient errors.
    """
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            if generation_config:
                return model.generate_content(prompt, generation_config=generation_config)
            else:
                return model.generate_content(prompt)
        except Exception as e:
            if attempt == max_retries:
                print(f"Error: Max retries ({max_retries}) reached. Raising exception.")
                raise e
            
            err_msg = str(e).lower()
            # If rate limited (429) or transient server error, sleep longer
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                sleep_time = delay * (1.5 + random.random())
                print(f"Warning: Rate limited by Gemini API. Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})")
            else:
                sleep_time = delay * (0.5 + random.random())
                print(f"Warning: Gemini API call failed: {e}. Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                
            time.sleep(sleep_time)
            delay *= 2.0
