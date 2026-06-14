import os
import shutil

# 1. Create target directories
dirs_to_create = [
    "extracted_paper",
    "pipeline/textbook",
    "pipeline/research_paper"
]
for d in dirs_to_create:
    os.makedirs(d, exist_ok=True)
    print(f"Ensured directory exists: {d}")

# 2. Move generated output files from root to extracted_paper/
root_files_to_move = {
    "extracted_concepts_paper.json": "extracted_paper/extracted_concepts_paper.json",
    "paper_notes.md": "extracted_paper/paper_notes.md",
    "paper_equations.md": "extracted_paper/paper_equations.md",
    "paper_algorithms.md": "extracted_paper/paper_algorithms.md",
    "paper_figures.md": "extracted_paper/paper_figures.md",
    "paper_extraction_trace.log": "extracted_paper/paper_extraction_trace.log",
}

for src, dest in root_files_to_move.items():
    if os.path.exists(src):
        # Remove destination if it exists (overwrite)
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(src, dest)
        print(f"Moved output file: {src} -> {dest}")
    else:
        print(f"Source file not found (skipping): {src}")

# 3. Move extracted_figures directory to extracted_paper/extracted_figures
figures_src = "extracted_figures"
figures_dest = "extracted_paper/extracted_figures"
if os.path.exists(figures_src):
    if os.path.exists(figures_dest):
        shutil.rmtree(figures_dest)
    shutil.move(figures_src, figures_dest)
    print(f"Moved figures directory: {figures_src} -> {figures_dest}")
else:
    print(f"Figures directory not found (skipping): {figures_src}")

# 4. Move pipeline scripts to subfolders
textbook_scripts = [
    "extract_concepts.py",
    "extract_all_chapters.py",
    "tune_extraction.py",
    "analyze_results.py"
]

research_scripts = [
    "extract_paper_concepts.py",
    "extract_paper_equations.py",
    "extract_paper_algorithms.py",
    "extract_paper_images.py",
    "generate_paper_notes.py"
]

for script in textbook_scripts:
    src = os.path.join("pipeline", script)
    dest = os.path.join("pipeline", "textbook", script)
    if os.path.exists(src):
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(src, dest)
        print(f"Moved textbook script: {src} -> {dest}")

for script in research_scripts:
    src = os.path.join("pipeline", script)
    dest = os.path.join("pipeline", "research_paper", script)
    if os.path.exists(src):
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(src, dest)
        print(f"Moved research script: {src} -> {dest}")
