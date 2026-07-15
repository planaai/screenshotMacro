import json

data_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\extracted_data\extracted_data.json"
out_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\anomaly_details.txt"

with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

details = []
for student in data:
    name = student.get('studentName', 'UNKNOWN')
    lvl = student.get('currentLevel')
    stats = student.get('stats', {})
    hp = stats.get('maxHP')
    
    is_anomaly = False
    reason = ""
    
    if lvl is not None and lvl > 95:
        is_anomaly = True
        reason += f"Invalid Level ({lvl}). "
    
    if hp is not None:
        if (lvl is not None and lvl > 1 and hp < 100) or (hp < 100):
            is_anomaly = True
            reason += f"Invalid HP ({hp}). "
            
    if is_anomaly:
        details.append(f"Name: {name} | Reason: {reason}\nData: {json.dumps(student, ensure_ascii=False)}\n")

with open(out_path, 'w', encoding='utf-8') as f:
    for d in details:
        f.write(d + "\n")
