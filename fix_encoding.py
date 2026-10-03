import sys
with open('equipment_scanner.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[378] = '    MENU_TITLE_KEYWORDS = ("장비", "성장")\n'
lines[379] = '    EQUIPMENT_BUTTON_KEYWORD = "성장"\n'

with open('equipment_scanner.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("done")
