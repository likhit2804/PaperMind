import sys
import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Enforce UTF-8 output encoding for Windows consoles
sys.stdout.reconfigure(encoding='utf-8')

# Ensure both workspace root and pipeline folder are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
pipeline_dir = os.path.dirname(current_dir)
workspace_root = os.path.dirname(pipeline_dir)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from pipeline.research_paper.extract_paper_concepts import parse_pdf_into_sections, clean_text
from pipeline.utils import parse_json_robust, call_gemini_with_retry

# Load environment variables
load_dotenv(override=True)

def get_term_contexts(sections, term, max_contexts=4):
    """
    Scans all sections, finds sentences matching the term, 
    and returns:
      - list of text snippets (matching sentence + surrounding context)
      - list of unique sources (e.g., "Page X (Section 'Y')")
    """
    term_lower = term.lower().strip()
    snippets = []
    sources = set()
    
    for sec in sections:
        sec_label = sec["label"]
        for page_num, page_text in sec["pages_data"]:
            # Normalize whitespace in page text
            page_clean = clean_text(page_text)
            # Find sentence boundaries
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', page_clean)
            
            for idx, sentence in enumerate(sentences):
                # Check if term matches as word/phrase boundary
                if re.search(r'\b' + re.escape(term_lower) + r'\b', sentence.lower()):
                    # Compile matching sentence with context before and after
                    before = sentences[idx - 1] if idx > 0 else ""
                    after = sentences[idx + 1] if idx < len(sentences) - 1 else ""
                    
                    snippet = ""
                    if before:
                        snippet += before + " "
                    snippet += sentence
                    if after:
                        snippet += " " + after
                    
                    snippets.append(snippet.strip())
                    sources.add((page_num, sec_label))
                    
                    if len(snippets) >= max_contexts:
                        break
            if len(snippets) >= max_contexts:
                break
        if len(snippets) >= max_contexts:
            break
            
    # Format unique sources cleanly
    source_strings = []
    # Sort sources by page number
    sorted_sources = sorted(list(sources), key=lambda x: x[0])
    for p_num, s_label in sorted_sources:
        source_strings.append(f"Page {p_num} (Section '{s_label}')")
        
    return snippets, source_strings

def get_topic_sentences(sections, keywords, max_sentences=20):
    """
    Offline helper to scan all sections and return sentences containing keywords for targeted Gemini queries.
    """
    hits = []
    for sec in sections:
        sec_label = sec["label"]
        for page_num, page_text in sec["pages_data"]:
            page_clean = clean_text(page_text)
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', page_clean)
            for idx, sent in enumerate(sentences):
                sent_lower = sent.lower()
                if any(re.search(r'\b' + re.escape(kw) + r'\b', sent_lower) for kw in keywords):
                    before = sentences[idx - 1] if idx > 0 else ""
                    after = sentences[idx + 1] if idx < len(sentences) - 1 else ""
                    full = " ".join(filter(None, [before, sent, after])).strip()
                    hits.append(f"(Page {page_num}, Section '{sec_label}'): {full}")
                    if len(hits) >= max_sentences:
                        return hits
    return hits

def generate_batch_definitions_via_ai(batch, title):
    """
    Sends a batch of terms and their corresponding contexts to Gemini in a single call.
    batch is a list of tuples: (term, list_of_contexts)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {term: "Definition not available (GEMINI_API_KEY not set)." for term, _ in batch}

    try:
        genai.configure(api_key=api_key)
        model_name = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        model = genai.GenerativeModel(model_name)
        
        # Build prompt listing each term and its contexts
        terms_context_prompt = []
        for idx, (term, contexts) in enumerate(batch):
            context_str = "\n".join([f"  - ... {c} ..." for c in contexts]) if contexts else "  - No direct occurrences found."
            terms_context_prompt.append(f"{idx+1}. Concept: \"{term}\"\nContexts:\n{context_str}")
            
        consolidated_prompt_list = "\n\n".join(terms_context_prompt)
        
        prompt = f"""You are an expert scientific dictionary editor and domain specialist.
We are compiling study notes for a research paper titled "{title}".
We need to extract precise, high-fidelity definitions and relational connections for the following technical concepts:

{consolidated_prompt_list}

Instructions:
1. Examine the provided contexts for each concept carefully. Differentiate between casual mentions and descriptions that explain the concept's function, structure, mathematical definition, or operational role in the paper.
2. For each concept, extract:
   - "definition": A concise 1-2 sentence definition/explanation.
   - "role": What specific role does this play in this paper (e.g. baseline benchmark, customized component, masking, etc.)?
   - "connections": A list of other technical terms (from the provided contexts) this concept directly interacts with or depends on.
3. Keep the tone academic, clear, and emoji-free.

Return your response strictly in JSON format as:
{{
  "definitions": {{
    "concept_name_1": {{
      "definition": "Synthesized grounded definition 1.",
      "role": "Grounded role explanation 1.",
      "connections": ["concept_a", "concept_b"]
    }}
  }}
}}
"""
        response = call_gemini_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = parse_json_robust(response.text)
        definitions = data.get("definitions", {})
        
        # Ensure lowercase keys for lookups
        result = {}
        for term, _ in batch:
            found = False
            term_clean = term.lower().strip()
            for k, v in definitions.items():
                if k.lower().strip() == term_clean:
                    if isinstance(v, dict):
                        # Format definitions with structured info for backwards compatibility
                        def_text = v.get("definition", "")
                        role_text = v.get("role", "")
                        conn_list = v.get("connections", [])
                        
                        full_def = def_text
                        if role_text:
                            full_def += f" [Role: {role_text}]"
                        if conn_list:
                            full_def += f" [Connections: {', '.join(conn_list)}]"
                        
                        result[term] = full_def
                    else:
                        result[term] = str(v)
                    found = True
                    break
            if not found:
                result[term] = "Definition not found in model response."
        return result
    except Exception as e:
        print(f"Warning: Failed to generate batch definitions: {e}")
        return {term: f"Failed to extract definition dynamically. (Error: {e})" for term, _ in batch}

def generate_novelty_vs_prior_art_via_ai(sections, title, unique_key_terms):
    """
    Calls Gemini to analyze targeted topic sentences and unique key terms, and classify what is 
    already present (prior art/baselines) versus what is newly introduced by this paper.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Prior Art vs Novelty not available (GEMINI_API_KEY not set)."

    try:
        genai.configure(api_key=api_key)
        model_name = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        model = genai.GenerativeModel(model_name)
        
        # Target prior art and novelty sentences
        prior_art_keywords = ["baseline", "comparison", "classical", "prior art", "existing", "previous work", "traditional"]
        novelty_keywords = ["proposed", "novel", "contribution", "our method", "we introduce", "we present", "in this paper"]
        
        prior_art_evidence = get_topic_sentences(sections, prior_art_keywords, max_sentences=20)
        novelty_evidence = get_topic_sentences(sections, novelty_keywords, max_sentences=20)
        
        prior_art_text = "\n".join([f"- {s}" for s in prior_art_evidence]) if prior_art_evidence else "- No specific prior-art statements extracted."
        novelty_text = "\n".join([f"- {s}" for s in novelty_evidence]) if novelty_evidence else "- No specific novelty statements extracted."
        terms_str = ", ".join(unique_key_terms)
        
        prompt = f"""You are an expert scientific editor and computer scientist.
We are compiling detailed technical notes for a research paper titled "{title}".
Here is the list of unique key concepts extracted from the paper: {terms_str}

We have pre-extracted sentences representing prior art and novelty evidence from the paper:

=== PRIOR ART EVIDENCE ===
{prior_art_text}

=== NOVELTY EVIDENCE ===
{novelty_text}

=== INSTRUCTIONS ===
Please generate a structured analysis in clean, premium GitHub-style markdown outlining:
1. **Prior Art (Already Present)**: What models, gates, math operators, representations, or principles are cited as existing foundations or baselines (e.g. what the authors build upon or compare against)?
2. **Proposed Novelty (Newly Introduced)**: What specific algorithms, customized circuit modules, masking designs, or complexity improvements are proposed as the paper's original contributions?

Categorize the relevant extracted key terms into these two groups and provide a concise, technical explanation of why they belong there based on the text.
Do NOT use emojis. Maintain a highly professional academic tone.

Return your response directly as markdown.
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating novelty analysis: {e}")
        return f"Failed to generate novelty analysis. (Error: {e})"

def main():
    if len(sys.argv) < 4:
        print("Usage: python generate_paper_notes.py <pdf_path> <concepts_json> <output_md>")
        sys.exit(1)
        
    pdf = sys.argv[1]
    concepts_json_path = sys.argv[2]
    output_md_path = sys.argv[3]
    
    if not os.path.exists(pdf):
        print(f"Error: PDF file not found at: {pdf}")
        sys.exit(1)
        
    if not os.path.exists(concepts_json_path):
        print(f"Error: Concepts JSON file not found at: {concepts_json_path}")
        sys.exit(1)
        
    print(f"Reading concept extractions from: {concepts_json_path}")
    with open(concepts_json_path, "r", encoding="utf-8") as f:
        concepts_data = json.load(f)
        
    title = concepts_data.get("paper_title", "Research Paper")
    section_terms_map = concepts_data.get("sections", {})
    unique_key_terms = concepts_data.get("unique_key_terms", [])
    
    sections = parse_pdf_into_sections(pdf, "")
    
    # 1. Search text contexts for each term and track sources
    print(f"Aggregating sentence contexts for {len(unique_key_terms)} key terms...")
    term_contexts = {}
    term_sources = {}
    for term in unique_key_terms:
        contexts, sources = get_term_contexts(sections, term)
        term_contexts[term] = contexts
        term_sources[term] = sources
        
    # 2. Batch definition generation
    print("Generating grounded definitions via Gemini (batch size: 10)...")
    batch_size = 10
    glossary = {}
    
    term_list = list(unique_key_terms)
    for i in range(0, len(term_list), batch_size):
        batch_terms = term_list[i:i+batch_size]
        batch_data = [(term, term_contexts[term]) for term in batch_terms]
        print(f"  Processing batch {i // batch_size + 1} ({len(batch_terms)} terms)...")
        
        batch_defs = generate_batch_definitions_via_ai(batch_data, title)
        glossary.update(batch_defs)
        
    # 3. Generate Prior Art vs. Novelty Analysis
    print("Analyzing Prior Art (Already Present) vs. Proposed Novelty (Newly Introduced)...")
    novelty_analysis = generate_novelty_vs_prior_art_via_ai(sections, title, unique_key_terms)
    
    # 4. Assemble the output markdown file (novelty analysis + definitions)
    print(f"Compiling final markdown glossary and analysis...")
    
    markdown_output = []
    markdown_output.append(f"# Technical Notes & Glossary: {title}\n")
    markdown_output.append(novelty_analysis)
    markdown_output.append("\n## Technical Glossary\n")
    markdown_output.append("The following glossary defines each verified concept as explained and utilized in this specific publication:\n")
    
    # Display the glossary in alphabetical order
    for term in sorted(glossary.keys()):
        definition = glossary[term]
        sources_str = ", ".join(term_sources[term]) if term_sources[term] else "Unknown source"
        # Highlight term and print source metadata
        markdown_output.append(f"* **{term}** *(Sources: {sources_str})*: {definition}")
        
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_output))
        
    print(f"\nSuccessfully wrote research glossary to: {output_md_path}")

if __name__ == "__main__":
    main()
