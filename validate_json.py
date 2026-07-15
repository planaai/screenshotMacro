import json
import os

data_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\extracted_data\extracted_data.json"
out_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\validation_results.txt"

with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

anomalies = []
for idx, student in enumerate(data):
    name = student.get('studentName', 'UNKNOWN')
    
    # Check levels
    lvl = student.get('currentLevel')
    if lvl is None or not (1 <= lvl <= 95):
        anomalies.append(f"{name}: Invalid currentLevel {lvl}")
        
    bond = student.get('bondRank')
    if bond is None or not (1 <= bond <= 100):
        anomalies.append(f"{name}: Invalid bondRank {bond}")
        
    # Check skills
    skills = student.get('skills', {})
    for sk, val in skills.items():
        if val not in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "M", "MAX", None, ""]:
            anomalies.append(f"{name}: Invalid skill {sk} = {val}")
            
    # Check stats
    stats = student.get('stats', {})
    hp = stats.get('maxHP')
    atk = stats.get('attackPower')
    # Let's consider HP below 500 as an error unless level is 1? No, level 1 HP is usually >500. Let's flag < 1000 for sure.
    if hp is not None and hp < 1000:
        if hp < 500:
            anomalies.append(f"{name}: Unreasonably low HP {hp} (Level: {lvl})")
    
    if atk is not None and atk < 100:
        anomalies.append(f"{name}: Unreasonably low ATK {atk} (Level: {lvl})")
        
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f"Total students processed: {len(data)}\n")
    f.write(f"Total anomalies found: {len(anomalies)}\n")
    for a in anomalies:
        f.write(a + "\n")
