import os
import sys
import json
import re
from dotenv import load_dotenv

# Enforce UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Automatically load environment variables from root .env
_current_dir = os.path.dirname(os.path.abspath(__file__))
_workspace_root = os.path.dirname(_current_dir)

env_path = os.path.join(_workspace_root, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# Ensure workspace root and pipeline dir are in sys.path
for _path in (_workspace_root, _current_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)
