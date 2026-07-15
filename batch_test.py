import os
import glob
import json
import sys
from extractor import extract_screenshot_data

img_dir = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\extracted_data\images"
images = glob.glob(os.path.join(img_dir, "*.jpg"))
images.sort()

print(f"Found {len(images)} images to process.")

anomalies = []
processed_data = []

for i, img_path in enumerate(images):
    print(f"[{i+1}/{len(images)}] Processing {os.path.basename(img_path)}...")
    data = extract_screenshot_data(img_path)
    if data:
        processed_data.append(data)
        
        # Check strict rules again just to report
        name = data.get('studentName', 'UNKNOWN')
        lvl = data.get('currentLevel') or 1
        hp = data.get('stats', {}).get('maxHP') or 0
        
        reasons = []
        if lvl > 90:
            reasons.append(f"Level {lvl} > 90")
        if hp < 1000:
            reasons.append(f"HP {hp} < 1000")
        if data.get("needs_review"):
            reasons.append("needs_review flag is True")
            
        if reasons:
            anomalies.append(f"{name} ({os.path.basename(img_path)}): {', '.join(reasons)}")

print(f"\n--- Batch Test Completed ---")
print(f"Total processed: {len(processed_data)}")
print(f"Total anomalies: {len(anomalies)}")
for a in anomalies:
    print(a)
    
if len(anomalies) == 0:
    print("ALL TESTS PASSED!")
    
    # Save the updated data
    out_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\extracted_data\extracted_data.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)
    print("Updated extracted_data.json saved.")
else:
    print("TEST FAILED.")
    sys.exit(1)
