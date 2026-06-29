import cv2
import numpy as np

import warnings
import logging
warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger('easyocr').setLevel(logging.ERROR)

import easyocr
import json
import os
import re

# Load student names
STUDENT_NAMES = []
try:
    with open('students.json', 'r', encoding='utf-8') as f:
        STUDENT_NAMES = json.load(f)
except Exception as e:
    print("Could not load students.json:", e)

def levenshtein(a, b):
    if not a: return len(b)
    if not b: return len(a)
    matrix = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                matrix[i][j] = matrix[i - 1][j - 1]
            else:
                matrix[i][j] = min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1)
    return matrix[len(a)][len(b)]

def match_student_name(extracted_name):
    if not extracted_name or not STUDENT_NAMES:
        return extracted_name
    clean_ex = re.sub(r'[^가-힣a-zA-Z0-9]', '', extracted_name)
    if not clean_ex: return extracted_name
    
    for name in STUDENT_NAMES:
        if name == extracted_name: return name
        
    best_match = None
    best_dist = float('inf')
    for n in STUDENT_NAMES:
        clean_n = re.sub(r'[^가-힣a-zA-Z0-9]', '', n)
        d = levenshtein(clean_ex, clean_n)
        if d < best_dist:
            best_dist = d
            best_match = n
            
    if best_match and best_dist <= 2:
        return best_match
    return extracted_name

# Bounding Box: (x, y, w, h) based on 1920x1080 resolution
ROI_CONFIG = {
    "studentName": (120, 840, 300, 40),
    "bondRank": (50, 835, 60, 40),
    "currentLevel": (20, 880, 100, 40),
    "stars_area": (390, 840, 150, 40),
    "skill_ex": (1000, 580, 120, 60),
    "skill_basic": (1180, 580, 120, 60),
    "skill_enh": (1340, 580, 120, 60),
    "skill_sub": (1500, 580, 120, 60),
    "weapon_level": (1200, 680, 80, 60),
    "weapon_stars_area": (1550, 750, 100, 40),
    "equip_1": (1020, 800, 80, 80),
    "equip_2": (1160, 800, 80, 80),
    "equip_3": (1300, 800, 80, 80),
    "equip_4": (1440, 800, 80, 80),
    "stat_hp": (1130, 340, 180, 50),
    "stat_attack": (1400, 340, 180, 50),
    "stat_defense": (1110, 390, 90, 50),
    "stat_heal": (1400, 390, 180, 50)
}

reader = easyocr.Reader(['ko', 'en'], gpu=False)

def count_stars(img_crop, is_weapon=False):
    hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
    if not is_weapon:
        # Yellow for student stars
        lower_color = np.array([15, 100, 100])
        upper_color = np.array([40, 255, 255])
        expected_w = 21.0
    else:
        # Cyan/Blue for weapon stars
        lower_color = np.array([80, 100, 100])
        upper_color = np.array([110, 255, 255])
        expected_w = 26.0
        
    mask = cv2.inRange(hsv, lower_color, upper_color)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    star_count = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 20:  # Adjust threshold based on star size
            x, y, w, h = cv2.boundingRect(cnt)
            num = max(1, round(w / expected_w))
            star_count += num
            
    return star_count

def extract_text(img, bbox, allowlist=None, scale=1):
    x, y, w, h = bbox
    crop = img[y:y+h, x:x+w]
    
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if scale != 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    kwargs = {'detail': 0}
    if allowlist:
        kwargs['allowlist'] = allowlist
        
    # Using raw grayscale is usually best for EasyOCR, especially for text with outlines
    result = reader.readtext(gray, **kwargs)
    text = "".join(result).replace(" ", "")
    
    # If it failed to read, try inverted threshold
    if not text:
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        result = reader.readtext(thresh, **kwargs)
        text = "".join(result).replace(" ", "")
        
    return text

def parse_number(text):
    if not text:
        return None
    numbers = re.findall(r'\d+', text)
    if numbers:
        # Join in case of things like '43,784'
        num = "".join(numbers)
        return int(num)
    return None

def parse_stat_with_ability(text):
    stat = 0
    ability = 0
    if not text: return stat, ability
    match = re.search(r'[Ll][Vv]?\s*(\d+)', text)
    if match:
        ability = int(match.group(1))
        if ability > 25: ability = 25
        text = text[:match.start()]
    stat_val = parse_number(text)
    if stat_val: stat = stat_val
    return stat, ability

def parse_skill(text):
    if not text: return "MAX"
    num = parse_number(text)
    # If no number found, or it's misread text, it's likely "MAX"
    if num is None:
        return "MAX"
    return str(num)

def parse_equip(text):
    if not text:
        return {"tier": 0, "level": 0}
    
    tier = 1
    # Try to find T1~T9
    match_t = re.search(r'[Tt]\s*([1-9])', text)
    if match_t:
        tier = int(match_t.group(1))
        # Remove the T part from text so it doesn't merge with level
        text = text[:match_t.start()] + text[match_t.end():]
        
    num = parse_number(text)
    if not num:
        return {"tier": tier, "level": 1}
        
    # If level is found
    level = num
    # If we somehow missed the T but got a huge number (e.g. 860), fallback logic
    if num > 100 and tier == 1:
        tier_fallback = int(str(num)[0])
        level_fallback = int(str(num)[1:])
        if 1 <= tier_fallback <= 9 and 1 <= level_fallback <= 90:
            return {"tier": tier_fallback, "level": level_fallback}
            
    # Guess tier based on max level cap for that tier
    if level <= 40:
        tier = max(tier, max(1, (level - 1) // 10 + 1))
    else:
        tier = max(tier, min(9, 4 + (level - 36) // 5))
            
    return {"tier": tier, "level": level}

def extract_screenshot_data(img_path):
    print(f"Processing image: {img_path}")
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if img is None:
        print("Failed to load image.")
        return None
        
    # Resize to 1920x1080 for consistent ROI
    img = cv2.resize(img, (1920, 1080))
    
    data = {}
    
    # 1. OCR Extraction
    data["studentName"] = match_student_name(extract_text(img, ROI_CONFIG["studentName"]))
    data["bondRank"] = parse_number(extract_text(img, ROI_CONFIG["bondRank"], allowlist='0123456789', scale=2))
    data["currentLevel"] = parse_number(extract_text(img, ROI_CONFIG["currentLevel"], allowlist='0123456789Lv'))
    
    data["skills"] = {
        "ex": parse_skill(extract_text(img, ROI_CONFIG["skill_ex"])),
        "basic": parse_skill(extract_text(img, ROI_CONFIG["skill_basic"])),
        "enh": parse_skill(extract_text(img, ROI_CONFIG["skill_enh"])),
        "sub": parse_skill(extract_text(img, ROI_CONFIG["skill_sub"]))
    }
    
    data["weapon"] = {
        "level": parse_number(extract_text(img, ROI_CONFIG["weapon_level"], allowlist='0123456789Lv')),
    }
    
    data["equipment"] = {
        "slot1": parse_equip(extract_text(img, ROI_CONFIG["equip_1"], allowlist='T0123456789Lv')),
        "slot2": parse_equip(extract_text(img, ROI_CONFIG["equip_2"], allowlist='T0123456789Lv')),
        "slot3": parse_equip(extract_text(img, ROI_CONFIG["equip_3"], allowlist='T0123456789Lv'))
    }
    
    # 3-1. Bond Gear (Slot 4) Extraction using Edge Detection and Color
    x, y, w, h = ROI_CONFIG["equip_4"]
    crop = img[y:y+h, x:x+w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Check edges to differentiate EMPTY from FILLED
    edges = cv2.Canny(gray[20:60, 10:50], 100, 200)
    if np.count_nonzero(edges) >= 130:
        # It's filled. Check for pink/red background pixels for T2.
        # The background circle is on the left side of the slot.
        hsv = cv2.cvtColor(crop[:, 0:40], cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 30, 150]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([160, 30, 150]), np.array([180, 255, 255]))
        pink_mask = cv2.bitwise_or(mask1, mask2)
        
        tier = 2 if cv2.countNonZero(pink_mask) > 500 else 1
        data["equipment"]["slot4"] = {"tier": tier}
    
    # 2. Detailed Stats OCR
    hp_stat, hp_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_hp"], allowlist='0123456789Lv'))
    atk_stat, atk_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_attack"], allowlist='0123456789Lv'))
    heal_stat, heal_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_heal"], allowlist='0123456789Lv'))

    data["stats"] = {
        "maxHP": hp_stat,
        "hpAbility": hp_ability,
        "attackPower": atk_stat,
        "atkAbility": atk_ability,
        "defensePower": parse_number(extract_text(img, ROI_CONFIG["stat_defense"], allowlist='0123456789')),
        "healPower": heal_stat,
        "healAbility": heal_ability
    }
    
    # 3. Star Counting (OpenCV)
    stars_x, stars_y, stars_w, stars_h = ROI_CONFIG["stars_area"]
    stars_crop = img[stars_y:stars_y+stars_h, stars_x:stars_x+stars_w]
    data["currentStar"] = count_stars(stars_crop, is_weapon=False)
    
    w_stars_x, w_stars_y, w_stars_w, w_stars_h = ROI_CONFIG["weapon_stars_area"]
    w_stars_crop = img[w_stars_y:w_stars_y+w_stars_h, w_stars_x:w_stars_x+w_stars_w]
    data["weapon"]["star"] = count_stars(w_stars_crop, is_weapon=True)
    
    return data

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <image_path>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    result = extract_screenshot_data(img_path)
    
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
