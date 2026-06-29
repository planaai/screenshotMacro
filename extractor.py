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
import requests
import urllib3
import difflib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load student names
STUDENT_NAMES = []
try:
    response = requests.get("https://localhost:3443/api/students/names", verify=False, timeout=5)
    if response.status_code == 200:
        STUDENT_NAMES = response.json()
    else:
        raise Exception(f"Server returned {response.status_code}")
except Exception as e:
    print("Could not load students from server, falling back to local:", e)
    try:
        # Fallback to local students.json based on current directory or script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, 'students.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            STUDENT_NAMES = json.load(f)
    except Exception as e2:
        print("Could not load local students.json:", e2)

import datetime

def log_debug(msg):
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        with open(os.path.join(log_dir, "extractor_debug.log"), "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

def split_jamo(text):
    CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
    JUNGSUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
    JONGSUNG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
    
    result = []
    for char in text:
        if '가' <= char <= '힣':
            char_code = ord(char) - 44032
            cho1 = char_code // 588
            jung1 = (char_code - (588 * cho1)) // 28
            jong1 = (char_code - (588 * cho1) - (28 * jung1))
            result.append(CHOSUNG[cho1])
            result.append(JUNGSUNG[jung1])
            if jong1 > 0:
                result.append(JONGSUNG[jong1])
        else:
            result.append(char)
    return "".join(result)

def split_jamo_char(char):
    if '가' <= char <= '힣':
        code = ord(char) - 44032
        cho = code // 588
        jung = (code - 588*cho) // 28
        jong = code - 588*cho - 28*jung
        return (cho, jung, jong)
    return None

def char_similarity(c1, c2):
    j1 = split_jamo_char(c1)
    j2 = split_jamo_char(c2)
    if j1 is None or j2 is None:
        return 1.0 if c1 == c2 else 0.0
    score = 0
    # Chosung match (out of 1)
    score += 1.0 if j1[0] == j2[0] else 0.0
    # Jungsung match (out of 1) 
    score += 1.0 if j1[1] == j2[1] else 0.0
    # Jongsung match (out of 1)
    score += 1.0 if j1[2] == j2[2] else 0.0
    return score / 3.0

def name_similarity(ocr_text, candidate):
    ocr_k = re.sub(r'[^가-힣]', '', ocr_text)
    # Compare against the full name, since OCR often extracts the variant part like (수영복)
    name_k = re.sub(r'[^가-힣]', '', candidate)
    if not ocr_k or not name_k:
        return 0.0
    
    # Severe penalty for length mismatch to prevent short strings from matching long ones
    if abs(len(ocr_k) - len(name_k)) > 1:
        return 0.3
    
    min_len = min(len(ocr_k), len(name_k))
    max_len = max(len(ocr_k), len(name_k))
    
    total = sum(char_similarity(ocr_k[i], name_k[i]) for i in range(min_len))
    
    # If there's an exact base name match, boost it slightly
    if ocr_k == name_k:
        return 1.0
        
    return total / max_len

def match_student_name(extracted_name):
    if not extracted_name or not STUDENT_NAMES:
        log_debug("Empty extracted_name or STUDENT_NAMES list.")
        return ""
    
    log_debug(f"--- Name Matching Start ---")
    log_debug(f"Raw OCR Output: '{extracted_name}'")
    
    # Remove all non-alphanumeric/Korean characters
    clean_ex = re.sub(r'[^가-힣a-zA-Z0-9]', '', extracted_name)
    if not clean_ex: 
        log_debug("Cleaned name is empty.")
        return ""
        
    # Apply manual OCR fallbacks for known difficult cases
    ocr_fallbacks = {
        "숲": "슌",
        "순": "슌",
        "숨": "슌",
        "슘": "슌",
        "스프미": "스즈미",
        "치하로": "치히로",
        "소구호미사키": "쇼쿠호미사키",
        "사례루이코": "사텐루이코",
    }
    for bad, good in ocr_fallbacks.items():
        if clean_ex.startswith(bad):
            clean_ex = good + clean_ex[len(bad):]
            break
            
    # Exact match fallbacks for single characters to avoid breaking longer names (e.g., 레이사)
    exact_fallbacks = {
        "레이": "케이",
        "켜이": "케이",
        "웨이": "케이"
    }
    if clean_ex in exact_fallbacks:
        clean_ex = exact_fallbacks[clean_ex]
            
    log_debug(f"Cleaned String: '{clean_ex}'")
    
    cleaned_names = {re.sub(r'[^가-힣a-zA-Z0-9]', '', n): n for n in STUDENT_NAMES}
    
    # 1. Exact match
    if clean_ex in cleaned_names:
        log_debug(f"Exact match found: '{cleaned_names[clean_ex]}'")
        return cleaned_names[clean_ex]
        
    # 2. Similarity match using character-by-character Jamo matching
    best_match = None
    best_ratio = 0.0
    
    # We want to match against base names first, but if there's a variant, 
    # we need to be careful. The OCR only sees the base name since it's 
    # extracted from the UI name field which doesn't contain the variant suffix like "(수영복)".
    # Therefore, matching should be primarily against the base name.
    
    for orig_n in STUDENT_NAMES:
        ratio = name_similarity(clean_ex, orig_n)
        
        # In case of ties, prefer the base character over the variant (e.g. '히나타' over '히나타(수영복)')
        # If the ratio is strictly greater, it becomes the new best match.
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = orig_n
        elif ratio == best_ratio and ratio > 0:
            # Tie breaker: if orig_n is shorter (i.e. it doesn't have parenthesis), prefer it
            if orig_n == orig_n.split('(')[0] and best_match != best_match.split('(')[0]:
                best_match = orig_n
            
    # Require a high confidence ratio to prevent matching completely wrong names
    # Per-character Jamo matching ratios: 1 wrong vowel out of 3 chars = 8/9 = 0.88
    # 1 wrong consonant = 8/9 = 0.88
    log_debug(f"Best Match Candidate: '{best_match}' with ratio: {best_ratio:.3f}")
    if best_match and best_ratio >= 0.65:
        log_debug(f"Accepted Match: '{best_match}'")
        return best_match
        
    log_debug("Match Rejected (Ratio < 0.7)")
    return ""

# Bounding Box: (x, y, w, h) based on 1920x1080 resolution
ROI_CONFIG = {
    "studentName": (85, 835, 350, 45),
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

def extract_text(img, bbox, allowlist=None, scale=1, is_name=False):
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
    
    if is_name:
        # The name ROI may include the bond rank number (e.g. "16") before the name.
        # EasyOCR often splits these into separate results like ["16", "나기사"].
        # We want only the Korean text part, so filter out pure number/symbol results.
        korean_parts = []
        for part in result:
            # Keep parts that contain at least one Korean character
            if re.search(r'[가-힣]', part):
                korean_parts.append(part)
        text = "".join(korean_parts).replace(" ", "")
        # Also strip any leading digits/symbols that might be stuck to the name
        text = re.sub(r'^[0-9\+\-\}\{\[\]\(\)\!\@\#\$\%\^\&\*\'\"]+', '', text)
        log_debug(f"Name OCR raw parts: {result} -> filtered: '{text}'")
        return text
    
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
    data["studentName"] = match_student_name(extract_text(img, ROI_CONFIG["studentName"], scale=3, is_name=True))
    
    # Disambiguate '케이' vs '레이' using Attack Type color (Mystic=Blue vs Sonic=Purple)
    if data["studentName"] == "케이":
        atk_type_crop = img[940:990, 300:400]
        hsv_crop = cv2.cvtColor(atk_type_crop, cv2.COLOR_BGR2HSV)
        purple_mask = cv2.inRange(hsv_crop, np.array([125, 50, 50]), np.array([165, 255, 255]))
        if cv2.countNonZero(purple_mask) > 500:
            data["studentName"] = "레이"
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
    else:
        data["equipment"]["slot4"] = {"tier": 0}
    
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
