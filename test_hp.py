import cv2
import numpy as np
import extractor
from extractor import extract_text, ROI_CONFIG, parse_stat_with_ability

img_path = r"C:\Users\also1\Documents\ba_archive\ba_archive\screenshot_extracter\test_release_working\extracted_data\images\capture_20260704115328_15.jpg"
img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
img = cv2.resize(img, (1920, 1080))

num_allowlist = '0123456789LvlIOoSs'

# Let's test extract_text directly on HP ROI
bbox = (1050, 350, 300, 40)
x, y, w, h = bbox
crop = img[y:y+h, x:x+w]

# Try standard extraction
res_standard = extract_text(img, bbox, allowlist=num_allowlist, scale=2, min_length=3)
print("Standard extraction result:", res_standard)

# Let's debug what OCR sees
from rapidocr_onnxruntime import RapidOCR
reader_en = RapidOCR()
crop_scaled = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
raw_res, _ = reader_en.text_recognizer([crop_scaled])
print("Raw OCR (scale=2):", raw_res)

gray = cv2.cvtColor(crop_scaled, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
inv_res, _ = reader_en.text_recognizer([thresh_bgr])
print("Inverted OCR (scale=2, thresh=150):", inv_res)

_, thresh2 = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
thresh_bgr2 = cv2.cvtColor(thresh2, cv2.COLOR_GRAY2BGR)
inv_res2, _ = reader_en.text_recognizer([thresh_bgr2])
print("Inverted OCR (scale=2, thresh=200):", inv_res2)

_, thresh_normal = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
thresh_normal_bgr = cv2.cvtColor(thresh_normal, cv2.COLOR_GRAY2BGR)
norm_res, _ = reader_en.text_recognizer([thresh_normal_bgr])
print("Binary OCR (scale=2, thresh=150):", norm_res)

cv2.imwrite("debug_hp_crop.jpg", crop_scaled)
cv2.imwrite("debug_hp_inv.jpg", thresh_bgr)
