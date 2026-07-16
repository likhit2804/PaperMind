"""
unified_paper_pipeline.py - Orchestrates the execution of all 7 individual scripts
in the research paper processing pipeline.

Usage:
  python unified_paper_pipeline.py <input_path> <output_dir>
"""
import sys
import os
import subprocess


def run_script(script_name, args):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    cmd = [sys.executable, script_path] + args
    print(f"\n---> Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"Error: {script_name} failed with exit code {result.returncode}")
        return False
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python unified_paper_pipeline.py <input_path> <output_dir>")
        sys.exit(1)

    input_path = os.path.abspath(sys.argv[1])
    output_dir = os.path.abspath(sys.argv[2])

    if not os.path.exists(input_path):
        print(f"Error: Input file not found at: {input_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    concepts_json = os.path.join(output_dir, "concepts.json")
    notes_md = os.path.join(output_dir, "notes.md")
    summary_json = os.path.join(output_dir, "summary.json")
    architecture_notes_md = os.path.join(output_dir, "architecture_notes.md")
    references_json = os.path.join(output_dir, "references.json")
    notations_json = os.path.join(output_dir, "notations.json")
    equations_json = os.path.join(output_dir, "equations.json")

    print(f"======================================================================")
    print(f"Starting Unified Paper Processing Pipeline")
    print(f"Input: {input_path}")
    print(f"Output Directory: {output_dir}")
    print(f"======================================================================")

    # 1. Concepts extraction (must run first, as notes/architecture depend on it)
    if not run_script("extract_paper_concepts.py", [input_path, concepts_json]):
        print("Fatal: Concept extraction failed. Aborting pipeline.")
        sys.exit(1)

    # 2. Paper notes and glossary (depends on concepts.json)
    run_script("generate_paper_notes.py", [input_path, concepts_json, notes_md])

    # 3. Paper summary
    run_script("generate_paper_summary.py", [input_path, summary_json])

    # 4. Architecture notes (depends on concepts.json)
    run_script("generate_architecture_notes.py", [input_path, concepts_json, architecture_notes_md])

    # 5. References and citations
    run_script("extract_paper_references.py", [input_path, references_json])

    # 6. Notations and Nomenclature table
    run_script("extract_notations_local.py", [input_path, notations_json])

    # 7. Equations and math
    run_script("extract_paper_equations.py", [input_path, equations_json])

    print(f"\n======================================================================")
    print(f"Unified Paper Processing Pipeline Completed Successfully!")
    print(f"======================================================================")


if __name__ == "__main__":
    main()
