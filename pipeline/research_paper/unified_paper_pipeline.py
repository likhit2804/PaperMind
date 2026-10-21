"""
unified_paper_pipeline.py - Orchestrates the execution of all research paper processing pipeline scripts.

Architecture & Pairing:
  - Phase 1: Sequential Base Anchor (extract_paper_concepts.py) - Must run first for concept grounding.
  - Phase 2: Parallel Zero-Interference Extraction Group (max_workers = 3):
      1. extract_paper_equations.py (1 Batched API Call for complex math, local typesetting for simple math)
      2. extract_paper_references.py (0 API Calls - 100% Offline Dual Format Regex Engine)
      3. extract_notations_local.py  (0 API Calls - 100% Offline Regex Engine)

Usage:
  python unified_paper_pipeline.py <input_path> <output_dir>
"""
from _bootstrap import *
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import warnings
warnings.filterwarnings("ignore")

import threading

def _stream_pipe(pipe, script_name):
    """Safely stream subprocess stdout line-by-line in a background thread."""
    try:
        for line in iter(pipe.readline, ""):
            if line:
                print(f"[{script_name}] {line.rstrip()}", flush=True)
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass

def run_script(script_name, args, timeout_seconds=300):
    """
    Executes an individual pipeline script with streaming logs and strict timeout protection.
    Default timeout: 300 seconds (5 minutes) per extraction stage.
    """
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    cmd = [sys.executable, "-u", "-W", "ignore", script_path] + args
    print(f"\n---> [Pipeline Step] Launching {script_name} (timeout={timeout_seconds}s)...", flush=True)
    
    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONWARNINGS"] = "ignore"
    env["PYTHONUNBUFFERED"] = "1"
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1
    )
    
    # Stream logs asynchronously so a hung process cannot block the timeout monitor
    reader = threading.Thread(target=_stream_pipe, args=(proc.stdout, script_name), daemon=True)
    reader.start()

    try:
        return_code = proc.wait(timeout=timeout_seconds)
        reader.join(timeout=2.0)
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"❌ Error: {script_name} timed out after {elapsed:.1f}s (limit={timeout_seconds}s). Terminating process...", flush=True)
        try:
            proc.kill()
        except Exception as kill_err:
            print(f"Warning: Failed to kill process {proc.pid}: {kill_err}", flush=True)
        return False
    except Exception as exc:
        print(f"❌ Error: Unexpected failure in {script_name}: {exc}", flush=True)
        try:
            proc.kill()
        except Exception:
            pass
        return False

    elapsed = time.time() - t0
    if return_code != 0:
        print(f"❌ Error: {script_name} failed with exit code {return_code} ({elapsed:.2f}s)", flush=True)
        return False
        
    print(f"✅ [Pipeline Step Completed] {script_name} finished in {elapsed:.2f}s", flush=True)
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
    pipeline_t0 = time.time()

    concepts_json = os.path.join(output_dir, "concepts.json")
    references_json = os.path.join(output_dir, "references.json")
    notations_json = os.path.join(output_dir, "notations.json")
    equations_json = os.path.join(output_dir, "equations.json")

    print(f"======================================================================")
    print(f"Starting PaperMind Unified Research Paper Processing Pipeline")
    print(f"Input Document:   {input_path}")
    print(f"Output Directory: {output_dir}")
    print(f"======================================================================")

    # Phase 1: Sequential Base Anchor (Concept extraction runs first for terminology grounding)
    print("\n--- Phase 1: Sequential Base Anchor ---")
    if not run_script("extract_paper_concepts.py", [input_path, concepts_json]):
        print("Fatal: Concept extraction failed. Aborting pipeline.")
        sys.exit(1)

    # Phase 2: Parallel Extraction Group (Zero-Interference Concurrent Pairing)
    # Pairs 1 Batched API call task (equations) with 2 Offline Zero-API tasks (references, notations)
    print("\n--- Phase 2: Zero-Interference Parallel Extraction Group ---")
    tasks = [
        # Paused tasks (replaced by native UI Work in Progress pages):
        # generate_paper_notes.py, generate_paper_summary.py, generate_architecture_notes.py
        ("extract_paper_equations.py", [input_path, equations_json]),
        ("extract_paper_references.py", [input_path, references_json]),
        ("extract_notations_local.py", [input_path, notations_json]),
    ]

    try:
        env_workers = int(os.environ.get("MAX_WORKERS") or os.environ.get("PIPELINE_WORKERS") or os.environ.get("NUM_WORKERS") or 3)
    except (ValueError, TypeError):
        env_workers = 3

    max_workers = max(1, min(env_workers, len(tasks)))
    print(f"---> Dispatching {len(tasks)} concurrent tasks (Max Workers = {max_workers})...")

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

    # Generate fallback placeholder files for paused generation scripts to ensure backend compatibility
    notes_md = os.path.join(output_dir, "notes.md")
    summary_json = os.path.join(output_dir, "summary.json")
    arch_notes_md = os.path.join(output_dir, "architecture_notes.md")

    if not os.path.exists(notes_md):
        with open(notes_md, "w", encoding="utf-8") as f:
            f.write("# Paper Notes\n\nThis feature is under active upgrade for PaperMind.")

    if not os.path.exists(summary_json):
        with open(summary_json, "w", encoding="utf-8") as f:
            json.dump({"overview": "Summary feature is under active upgrade.", "key_takeaways": []}, f, indent=2)

    if not os.path.exists(arch_notes_md):
        with open(arch_notes_md, "w", encoding="utf-8") as f:
            f.write("# Architecture Notes\n\nArchitecture notes are under active upgrade.")

    total_pipeline_time = time.time() - pipeline_t0
    print(f"\n======================================================================")
    print(f"🎉 PaperMind Unified Processing Pipeline Completed in {total_pipeline_time:.2f}s!")
    print(f"======================================================================")


if __name__ == "__main__":
    main()
