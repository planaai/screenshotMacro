import cv2
import sys
import os
import json

sys.path.append(r"c:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\Plana_SE ver.1.4")
from equipment_scanner import UiLayout, crop_region, OcrEngine, parse_tier_text, MAX_FAVORITE_TIER
import extractor

img_path = r"C:\Program Files (x86)\Steam\userdata\1084165488\760\remote\3557620\screenshots\20261004000038_1.jpg"
print(f"Loading image: {img_path}")
if not os.path.exists(img_path):
    print("File does not exist!")
    sys.exit(1)

frame = cv2.imread(img_path)
if frame is None:
    print("Failed to read image")
    sys.exit(1)

print(f"Image shape: {frame.shape}")

# Resize to 1920x1080 if necessary, but wait, GameScreen does:
# cv2.resize(frame, (1920, 1080)) after cutting 16:9
def centered_16_9_box(w, h):
    target_ratio = 16 / 9
    left, top = 0, 0
    if w / h > target_ratio:
        content_w = round(h * target_ratio)
        left = (w - content_w) // 2
        w = content_w
    elif w / h < target_ratio:
        content_h = round(w / target_ratio)
        top = (h - content_h) // 2
        h = content_h
    return left, top, w, h

h, w = frame.shape[:2]
left, top, cw, ch = centered_16_9_box(w, h)
print(f"Cropping to 16:9: {left}, {top}, {cw}, {ch}")
frame_16_9 = frame[top:top+ch, left:left+cw]
frame_1080 = cv2.resize(frame_16_9, (1920, 1080), interpolation=cv2.INTER_AREA)

layout = UiLayout.load(r"c:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\Plana_SE ver.1.4\config\equipment_ui.json")
region = layout.region("favorite_tier_badge")
print(f"Region favorite_tier_badge: {region}")

crop = crop_region(frame_1080, region)
cv2.imwrite("scratch/favorite_crop_debug.jpg", crop)
print("Saved crop to scratch/favorite_crop_debug.jpg")

ocr = OcrEngine(extractor.reader_ko, extractor.reader_en)
candidates = []
for text in ocr.iter_line_candidates(crop):
    candidates.append(text)
    print(f"OCR Candidate: {repr(text)}")
    tier = parse_tier_text(text, MAX_FAVORITE_TIER)
    print(f"Parsed tier: {tier}")

print("Checking favorite popup title...")
title_region = layout.region("favorite_popup_title")
print(f"favorite_popup_title region: {title_region}")
title_crop = crop_region(frame_1080, title_region)
cv2.imwrite("scratch/favorite_title_crop.jpg", title_crop)
title_text = ocr.read_korean_line(title_crop)
print(f"Popup Title Text OCR: {repr(title_text)}")

from equipment_scanner import EquipmentScreenReader
reader = EquipmentScreenReader(layout, ocr)
is_open = reader.is_favorite_popup_open(frame_1080)
print(f"is_favorite_popup_open: {is_open}")
