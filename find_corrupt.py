import sys

def find_corrupted(filepath):
    print(f"=== {filepath} ===")
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if '' in line:
                print(f"{i}: {line.strip()}")

find_corrupted('equipment_scanner.py')
find_corrupted('gui_app.py')
