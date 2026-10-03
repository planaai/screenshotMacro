import json
import re

transcript_path = r"C:\Users\also1\.gemini\antigravity-ide\brain\7bdbdb8b-3aac-4aca-8d77-af357ece712c\.system_generated\logs\transcript_full.jsonl"
out_path = "equipment_scanner_recovered.py"

content_to_save = None

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "CODE_ACTION" and "equipment_scanner.py" in data.get("content", ""):
                content = data["content"]
                if "The above content shows the entire, complete file contents" in content or "Total Lines:" in content:
                    if "Total Lines:" in content:
                        # Extract the lines from the view_file output
                        lines = []
                        capture = False
                        for c_line in content.split('\n'):
                            if c_line.startswith("The following code has been modified"):
                                capture = True
                                continue
                            if c_line.startswith("The above content"):
                                capture = False
                                continue
                            if capture:
                                # Remove the line number prefix (e.g. "123: ")
                                match = re.match(r'^\d+:\s(.*)$', c_line)
                                if match:
                                    lines.append(match.group(1))
                                else:
                                    # Might be empty line
                                    match = re.match(r'^\d+:$', c_line)
                                    if match:
                                        lines.append('')
                                    else:
                                        lines.append(c_line)
                        
                        if len(lines) > 500: # Make sure it's the full file
                            content_to_save = '\n'.join(lines)
                            break
        except Exception as e:
            pass

if content_to_save:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content_to_save)
    print("Recovered file saved to", out_path)
else:
    print("Could not find the full file in transcript")
