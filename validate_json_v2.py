import json
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python validate_json_v2.py <path_to_json>")
    sys.exit(1)

data_path = sys.argv[1]

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
    
    if hp is not None and hp < 1000:
        if hp < 500:
            anomalies.append(f"{name}: Unreasonably low HP {hp} (Level: {lvl})")
    
    if atk is not None and atk < 100:
        anomalies.append(f"{name}: Unreasonably low ATK {atk} (Level: {lvl})")
        
with open('validation_results_2.txt', 'w', encoding='utf-8') as out_f:
    out_f.write(f"Total students processed: {len(data)}\n")
    out_f.write(f"Total anomalies found: {len(anomalies)}\n")
    for a in anomalies:
        out_f.write(a + "\n")
