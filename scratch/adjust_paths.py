import os
import re

# Folders to process
folders = ["pipeline/textbook", "pipeline/research_paper"]

# The new sys.path configuration block
new_path_setup = """# Ensure both workspace root and pipeline folder are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
pipeline_dir = os.path.dirname(current_dir)
workspace_root = os.path.dirname(pipeline_dir)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)"""

# Regex patterns to match old path setup block
old_path_patterns = [
    r'# Ensure both workspace root and pipeline folder are in sys\.path\s+current_dir = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s+workspace_root = os\.path\.dirname\(current_dir\)\s+sys\.path\.insert\(0, workspace_root\)\s+sys\.path\.insert\(0, current_dir\)',
    r'# Ensure pipeline folder is in sys\.path\s+current_dir = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s+workspace_root = os\.path\.dirname\(current_dir\)\s+if workspace_root not in sys\.path:\s+sys\.path\.insert\(0, workspace_root\)\s+if current_dir not in sys\.path:\s+sys\.path\.insert\(0, current_dir\)'
]

for folder in folders:
    if not os.path.exists(folder):
        continue
    for filename in os.listdir(folder):
        if not filename.endswith(".py"):
            continue
            
        filepath = os.path.join(folder, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        
        # Replace sys.path setup blocks
        for pat in old_path_patterns:
            if re.search(pat, content):
                content = re.sub(pat, new_path_setup, content)
                modified = True
                print(f"Replaced sys.path setup in {filepath}")
                break
                
        # Update imports of extract_paper_concepts in research_paper subfolder
        if folder == "pipeline/research_paper":
            old_import = "from pipeline.extract_paper_concepts"
            new_import = "from pipeline.research_paper.extract_paper_concepts"
            if old_import in content:
                content = content.replace(old_import, new_import)
                modified = True
                print(f"Updated imports in {filepath}: {old_import} -> {new_import}")
                
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Saved modified file: {filepath}")
        else:
            print(f"No changes needed for: {filepath}")
