import json

transcript_path = r"C:\Users\likhi\.gemini\antigravity-ide\brain\1747dec6-4644-4996-9af0-962d9d0e021d\.system_generated\logs\transcript.jsonl"

with open(transcript_path, 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        if "console" in line.lower() or "error" in line.lower():
            try:
                data = json.loads(line)
                print(f"=== Line {idx} Step {data.get('step_index')} Source: {data.get('source')} Type: {data.get('type')} ===")
                # If content exists, print first 200 chars
                content = data.get("content", "")
                if content:
                    print(content[:300])
            except Exception as e:
                pass
