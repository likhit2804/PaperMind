"""
unified_paper_pipeline.py - Orchestrates the execution of all 7 individual scripts
in the research paper processing pipeline.

Usage:
  python unified_paper_pipeline.py <input_path> <output_dir>
"""
import sys
import os
import subprocess


import warnings
warnings.filterwarnings("ignore")

def run_script(script_name, args):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    cmd = [sys.executable, "-u", "-W", "ignore", script_path] + args
    print(f"\n---> Running: {' '.join(cmd)}", flush=True)
    
    env = dict(os.environ)
    env["PYTHONWARNINGS"] = "ignore"
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {script_name} failed with exit code {result.returncode}:")
        if result.stderr:
            print(result.stderr)
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

    # Steps 2-7 are independent (once concepts.json exists), but keep the
    # worker count bounded so a small deployment instance is not overwhelmed
    # by six Python processes and their concurrent LLM requests.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tasks = [
        ("generate_paper_notes.py", [input_path, concepts_json, notes_md]),
        ("generate_paper_summary.py", [input_path, summary_json]),
        ("generate_architecture_notes.py", [input_path, concepts_json, architecture_notes_md]),
        ("extract_paper_references.py", [input_path, references_json]),
        ("extract_notations_local.py", [input_path, notations_json]),
        ("extract_paper_equations.py", [input_path, equations_json]),
    ]

    max_workers = min(3, len(tasks))
    print(f"\n---> Running remaining {len(tasks)} pipeline steps with max {max_workers} concurrent workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_script = {
            executor.submit(run_script, script_name, args): script_name
            for script_name, args in tasks
        }
        for future in as_completed(future_to_script):
            script_name = future_to_script[future]
            try:
                success = future.result()
                if not success:
                    print(f"Warning: Step {script_name} encountered an issue.")
            except Exception as exc:
                print(f"Error: Step {script_name} generated an exception: {exc}")

    print(f"\n======================================================================")
    print(f"Unified Paper Processing Pipeline Completed Successfully!")
    print(f"======================================================================")


if __name__ == "__main__":
    main()
