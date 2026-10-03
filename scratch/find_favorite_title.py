import cv2
import sys
import os

sys.path.append(r"c:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\Plana_SE ver.1.4")
from equipment_scanner import centered_16_9_box
import extractor

img_path = r"C:\Program Files (x86)\Steam\userdata\1084165488\760\remote\3557620\screenshots\20261004000038_1.jpg"
frame = cv2.imread(img_path)

h, w = frame.shape[:2]
box = centered_16_9_box({"left": 0, "top": 0, "width": w, "height": h})
left, top, cw, ch = box["left"], box["top"], box["width"], box["height"]
frame_16_9 = frame[top:top+ch, left:left+cw]
frame_1080 = cv2.resize(frame_16_9, (1920, 1080), interpolation=cv2.INTER_AREA)

print("Running Korean OCR on the full 1920x1080 frame to find '애용품'...")
res, _ = extractor.reader_ko(frame_1080)
for box, text, conf in (res or []):
    if "용품" in text or "애용" in text or "정보" in text or "능력치" in text:
        print(f"FOUND: {text} at {box}")
