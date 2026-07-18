import cv2
import numpy as np

import warnings
import logging
import logging
warnings.filterwarnings("ignore", category=UserWarning)

from rapidocr_onnxruntime import RapidOCR
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

import difflib

def name_similarity(ocr_text, candidate):
    ocr_k = re.sub(r'[^가-힣]', '', ocr_text)
    # Compare against the full name, since OCR often extracts the variant part like (수영복)
    name_k = re.sub(r'[^가-힣]', '', candidate)
    
    if not ocr_k or not name_k:
        return 0.0
        
    if name_k in ocr_k:
        # Give a slight penalty for extra noise characters
        return max(0.0, 1.0 - (len(ocr_k) - len(name_k)) * 0.1)
        
    # SequenceMatcher ratio to handle missing characters (deletions) naturally
    seq_ratio = difflib.SequenceMatcher(None, ocr_k, name_k).ratio()
    
    # Severe penalty for length mismatch to prevent short strings from matching long ones
    if len(name_k) > len(ocr_k) + 1:
        return max(0.3, seq_ratio - 0.2)
        
    best_score = 0.0
    window_size = len(name_k)
    
    # If ocr_k is shorter than name_k, we just compare what we have
    if len(ocr_k) < len(name_k):
        total = sum(char_similarity(ocr_k[i], name_k[i]) for i in range(len(ocr_k)))
        score = total / len(name_k)
        best_score = max(0.0, score - (len(name_k) - len(ocr_k)) * 0.1)
    else:
        for i in range(len(ocr_k) - window_size + 1):
            window = ocr_k[i:i+window_size]
            total = sum(char_similarity(window[j], name_k[j]) for j in range(window_size))
            score = total / len(name_k) - (len(ocr_k) - len(name_k)) * 0.1
            if score > best_score:
                best_score = score
            
    return max(0.0, best_score, seq_ratio)

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
    if best_match and best_ratio >= 0.60:
        log_debug(f"Accepted Match: '{best_match}'")
        return best_match
        
    log_debug("Match Rejected (Ratio < 0.60)")
    return ""

# Bounding Box: (x, y, w, h) based on 1920x1080 resolution
ROI_CONFIG = {
    "studentName": (85, 835, 350, 45),
    "bondRank": (50, 835, 60, 40),
    "currentLevel": (20, 880, 120, 40),
    "stars_area": (390, 840, 150, 40),
    "skill_ex": (1000, 580, 120, 60),
    "skill_basic": (1180, 580, 120, 60),
    "skill_enh": (1340, 580, 120, 60),
    "skill_sub": (1500, 580, 120, 60),
    "weapon_level": (1200, 680, 80, 60),
    "weapon_stars_area": (1500, 750, 160, 40),
    "equip_1": (1000, 820, 130, 130),
    "equip_2": (1140, 820, 130, 130),
    "equip_3": (1280, 820, 130, 130),
    "equip_4": (1420, 820, 130, 130),
    "stat_hp": (1050, 350, 300, 40),
    "stat_attack": (1350, 350, 300, 40),
    "stat_defense": (1050, 400, 300, 40),
    "stat_heal": (1350, 400, 300, 40)
}

import sys

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

reader_ko = RapidOCR(
    rec_model_path=get_resource_path("models/korean_PP-OCRv3_rec_infer.onnx"),
    rec_keys_path=get_resource_path("models/korean_dict.txt")
)
reader_en = RapidOCR()

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

def extract_text(img, bbox, allowlist=None, scale=1, is_name=False, min_length=0):
    x, y, w, h = bbox
    crop = img[y:y+h, x:x+w]
    
    if crop.size == 0:
        return ""

    if scale != 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    active_reader = reader_ko if is_name else reader_en

    try:
        ocr_res, _ = active_reader.text_recognizer([crop])
    except Exception as e:
        log_debug(f"text_recognizer error: {e}")
        ocr_res = None
    
    if ocr_res is None or len(ocr_res) == 0:
        parts = []
    else:
        parts = [ocr_res[0][0]]
    
    if is_name:
        korean_parts = []
        for part in parts:
            if re.search(r'[가-힣]', part):
                korean_parts.append(part)
        text = "".join(korean_parts).replace(" ", "")
        text = re.sub(r'^[0-9\+\-\}\{\[\]\(\)\!\@\#\$\%\^\&\*\'\"]+', '', text)
        log_debug(f"Name OCR raw parts: {parts} -> filtered: '{text}'")
        return text
    
    text = "".join(parts).replace(" ", "")
    
    if allowlist:
        text = "".join(c for c in text if c in allowlist)
    
    # If it failed to read or didn't find any numbers when it should have, try inverted threshold
    needs_retry = not text or len(text) < min_length
    
    def has_digit_or_alias(s):
        return any(c.isdigit() or c in 'lIOoSs' for c in s)

    if allowlist and any(c.isdigit() for c in allowlist) and not has_digit_or_alias(text):
        needs_retry = True
        
    if needs_retry:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        try:
            ocr_res, _ = active_reader.text_recognizer([thresh_bgr])
        except:
            ocr_res = None
            
        if ocr_res and len(ocr_res) > 0:
            retry_text = "".join(ocr_res[0][0]).replace(" ", "")
            if allowlist:
                retry_text = "".join(c for c in retry_text if c in allowlist)
            # If the retry text has digit aliases, prefer it
            if has_digit_or_alias(retry_text):
                text = retry_text
            elif not text:
                text = retry_text
        
    return text

def extract_equip_text(img, bbox):
    x, y, w, h = bbox
    crop = img[y:y+h, x:x+w]
    if crop.size == 0:
        return ""
        
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # A locked slot (padlock) has a dark gray background (mean ~120-136)
    # An equipped or unequipped slot has a brighter background/icon (mean > 170)
    if np.mean(gray) < 150:
        return "EMPTY"
        
    try:
        scaled = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        adjusted = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        res, _ = reader_en(adjusted)
        if res:
            texts = [r[1] for r in res]
            full_text = ' '.join(texts).upper()
            if "EMPTY" in full_text or "MPTY" in full_text or "PTY" in full_text:
                return "EMPTY"
            return full_text
    except Exception as e:
        log_debug(f"OCR Exception: {e}")
        
    return ""

def extract_bond_text(img, bbox):
    x, y, w, h = bbox
    crop = img[y:y+h, x:x+w]
    if crop.size == 0: return ""
    
    text = extract_text(img, bbox, allowlist='0123456789LvlIOoSs', scale=2)
    if parse_number(text): return text
        
    scaled = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(scaled, cv2.COLOR_BGR2HSV)
    v = hsv[:,:,2]
    _, thresh = cv2.threshold(v, 100, 255, cv2.THRESH_BINARY_INV)
    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    
    try:
        res, _ = reader_en.text_recognizer([thresh_bgr])
        if res and len(res) > 0 and parse_number(res[0][0]):
            return res[0][0]
    except:
        pass
        
    ch, cw = thresh.shape
    center = thresh[int(ch*0.2):int(ch*0.8), int(cw*0.30):int(cw*0.70)]
    if center.size > 0:
        center_inv = cv2.bitwise_not(center)
        combined = np.full((center.shape[0] + 40, center.shape[1] * 3 + 80), 255, dtype=np.uint8)
        ch_c, cw_c = center_inv.shape
        combined[20:20+ch_c, 20:20+cw_c] = center_inv
        combined[20:20+ch_c, 40+cw_c:40+cw_c*2] = center_inv
        combined[20:20+ch_c, 60+cw_c*2:60+cw_c*3] = center_inv
        
        try:
            res, _ = reader_en.text_recognizer([cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)])
            if res and len(res) > 0:
                t = res[0][0]
                if len(t) % 3 == 0: return t[:len(t)//3]
                elif len(t) > 0: return t[:max(1, len(t)//3)]
        except:
            pass
            
    return text

def parse_number(text):
    if not text:
        return None
        
    # Replace common OCR misreads for numbers
    text = text.replace('l', '1').replace('I', '1').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
    
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
    
    # Pre-process S/s to 5 before regex since OCR often reads '25' as '2S'
    text = text.replace('S', '5').replace('s', '5').replace('O', '0').replace('o', '0')
    
    match = re.search(r'[Ll][Vv]?\s*(\d+)', text)
    if match:
        ability = int(match.group(1))
        if ability > 25: ability = 25
        text = text[:match.start()]
    stat_val = parse_number(text)
    if stat_val: 
        # Fix for OCR mistakenly reading the left text '력' as '7' or '1'
        if stat_val > 100000 and str(stat_val).startswith('7'):
            stat_val = int(str(stat_val)[1:])
        elif stat_val > 100000 and str(stat_val).startswith('1'):
            stat_val = int(str(stat_val)[1:])
        stat = stat_val
    return stat, ability

def parse_skill(text, is_ex=False):
    if not text: return "1"
    
    text_upper = text.upper()
    if "M" in text_upper or "X" in text_upper or "MAX" in text_upper:
        return "MAX"
    
    # Strip common 'Lv' misreads before parsing to avoid 'Lo' -> '0'
    text_clean = re.sub(r'[Ll][VvOo0]?', '', text)
    
    num = parse_number(text_clean)
    # If no number found, or it's misread text, default to 1 instead of MAX
    if num is None or num == 0:
        return "1"
        
    max_val = 5 if is_ex else 10
    
    # If it is read as 31, 71, etc.
    while num > max_val:
        num_str = str(num)
        if len(num_str) >= 2 and (num_str[-1] == '1' or num_str[-1] == '7'):
            num = int(num_str[:-1])
        else:
            num = max_val
            break
            
    if num > max_val:
        num = max_val
            
    return str(max(1, num))

def clamp_stat(val, max_val):
    if val is None: return None
    val_str = str(val)
    while len(val_str) > 0 and int(val_str) > max_val:
        val_str = val_str[:-1]
    return int(val_str) if val_str else 0

def parse_equip(text):
    if not text or "EMPTY" in text.upper() or "MPTY" in text.upper() or "PTY" in text.upper():
        return {"tier": 0, "level": 0}
        
    tier = 0
    level = 0
    
    # Try to find T1~T10
    match_t = re.search(r'[Tt]\s*(10|[1-9])', text)
    if match_t:
        tier = int(match_t.group(1))
        
    # Strictly read the level next to Lv. 
    # Match variations of L.v, Lv, LV, lV, L2, LY (common OCR misreads for Lv)
    match_lv = re.search(r'(?:[Ll1I][VvYy2oO]*[:.]?)\s*(\d+)', text)
    if match_lv:
        level = int(match_lv.group(1))
        
    if tier == 0 and level == 0:
        return {"tier": 0, "level": 0}
        
    # If a low tier item has no T badge (e.g. T1 Lv.15), it only says Lv.15
    if tier == 0 and level > 0:
        tier = 1
        
    if level > 90:
        level = int(str(level)[:2])

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
            
    num_allowlist = '0123456789LvlIOoSs'
    
    data["bondRank"] = parse_number(extract_bond_text(img, ROI_CONFIG["bondRank"]))
    data["currentLevel"] = parse_number(extract_text(img, ROI_CONFIG["currentLevel"], allowlist=num_allowlist, scale=2))
    
    data["skills"] = {
        "ex": parse_skill(extract_text(img, ROI_CONFIG["skill_ex"]), is_ex=True),
        "basic": parse_skill(extract_text(img, ROI_CONFIG["skill_basic"]), is_ex=False),
        "enh": parse_skill(extract_text(img, ROI_CONFIG["skill_enh"]), is_ex=False),
        "sub": parse_skill(extract_text(img, ROI_CONFIG["skill_sub"]), is_ex=False)
    }
    
    data["weapon"] = {
        "level": parse_number(extract_text(img, ROI_CONFIG["weapon_level"], allowlist=num_allowlist, scale=2)),
    }
    
    t1_text = extract_equip_text(img, ROI_CONFIG["equip_1"])
    t2_text = extract_equip_text(img, ROI_CONFIG["equip_2"])
    t3_text = extract_equip_text(img, ROI_CONFIG["equip_3"])
    t4_text = extract_equip_text(img, ROI_CONFIG["equip_4"])
    
    # 3-1. Bond Gear (Slot 4) Extraction using Color
    # The 4th slot is slightly pinkish if the student has a favorite item.
    ex, ey, ew, eh = ROI_CONFIG["equip_4"]
    slot4_crop = img[ey:ey+eh, ex:ex+ew]
    cb, cg, cr = cv2.split(slot4_crop)
    has_favorite_item = np.mean(cr) > np.mean(cb) and np.mean(cr) > np.mean(cg)
    
    data["equipment"] = {
        "slot1": parse_equip(t1_text),
        "slot2": parse_equip(t2_text),
        "slot3": parse_equip(t3_text),
        "slot4": parse_equip(t4_text) if has_favorite_item else {"tier": 0, "level": 0}
    }
    
    # 2. Detailed Stats OCR
    hp_stat, hp_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_hp"], allowlist=num_allowlist, scale=2, min_length=3))
    atk_stat, atk_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_attack"], allowlist=num_allowlist, scale=2, min_length=3))
    heal_stat, heal_ability = parse_stat_with_ability(extract_text(img, ROI_CONFIG["stat_heal"], allowlist=num_allowlist, scale=2, min_length=3))

    data["stats"] = {
        "maxHP": clamp_stat(hp_stat, 200000),
        "hpAbility": hp_ability,
        "attackPower": clamp_stat(atk_stat, 25000),
        "atkAbility": atk_ability,
        "defensePower": clamp_stat(parse_number(extract_text(img, ROI_CONFIG["stat_defense"], allowlist=num_allowlist, scale=2)), 10000),
        "healPower": clamp_stat(heal_stat, 35000),
        "healAbility": heal_ability
    }
    
    # 3. Star Counting (OpenCV)
    stars_x, stars_y, stars_w, stars_h = ROI_CONFIG["stars_area"]
    stars_crop = img[stars_y:stars_y+stars_h, stars_x:stars_x+stars_w]
    data["currentStar"] = count_stars(stars_crop, is_weapon=False)
    
    w_stars_x, w_stars_y, w_stars_w, w_stars_h = ROI_CONFIG["weapon_stars_area"]
    w_stars_crop = img[w_stars_y:w_stars_y+w_stars_h, w_stars_x:w_stars_x+w_stars_w]
    data["weapon"]["star"] = count_stars(w_stars_crop, is_weapon=True)
    
    # 4. Post-processing validation
    validate_extracted_data(data)
    
    return data

# Weapon max level per star grade: 3성=50, 4성=60
WEAPON_MAX_LEVEL_BY_STAR = {0: 0, 1: 30, 2: 40, 3: 50, 4: 60}

def validate_extracted_data(data):
    """Post-processing to fix common OCR misreads based on game logic constraints."""
    
    # 0. Fix Level > 90 trailing 1
    if data.get("currentLevel", 0) > 90:
        lvl_str = str(data["currentLevel"])
        if lvl_str.endswith("1"):
            log_debug(f"[Validation] currentLevel {lvl_str} -> {lvl_str[:-1]} 보정 (name={data.get('studentName')})")
            data["currentLevel"] = int(lvl_str[:-1])
            
        if data["currentLevel"] > 90:
            log_debug(f"[Validation] currentLevel {data['currentLevel']} -> 90 클램핑 (name={data.get('studentName')})")
            data["currentLevel"] = 90
    
    # 1. currentLevel: 9 → 90 보정
    # Lv.9에서 스킬 MAX, 높은 인연 랭크, 5성, 무기 보유는 불가능
    if data.get("currentLevel") == 9:
        skills = data.get("skills", {})
        has_max_skill = any(v == "MAX" for v in skills.values())
        has_high_bond = (data.get("bondRank") or 0) >= 15
        has_high_star = (data.get("currentStar") or 0) >= 4
        has_weapon = (data.get("weapon", {}).get("star") or 0) >= 2
        
        if has_max_skill or has_high_bond or has_high_star or has_weapon:
            log_debug(f"[Validation] currentLevel 9 → 90 보정 (name={data.get('studentName')}, bond={data.get('bondRank')}, star={data.get('currentStar')}, has_max_skill={has_max_skill})")
            data["currentLevel"] = 90
    
    # 2. weapon level 클램핑 (성급별 최대 레벨)
    weapon = data.get("weapon", {})
    w_star = weapon.get("star") or 0
    w_level = weapon.get("level")
    
    max_weapon_level = WEAPON_MAX_LEVEL_BY_STAR.get(w_star, 50)
    
    if w_level is not None and w_level > max_weapon_level:
        log_debug(f"[Validation] weapon level {w_level} → {max_weapon_level} 클램핑 (star={w_star}, name={data.get('studentName')})")
        weapon["level"] = max_weapon_level
    
    # 3. weapon star > 0 인데 level = None → level = 1
    if w_star > 0 and w_level is None:
        log_debug(f"[Validation] weapon level None → 1 (star={w_star}, name={data.get('studentName')})")
        weapon["level"] = 1
        
    # 4. Strict validation check
    needs_review = False
    lvl = data.get("currentLevel") or 1
    hp = data.get("stats", {}).get("maxHP") or 0
    if lvl > 90:
        needs_review = True
    if hp < 1000:
        needs_review = True
    data["needs_review"] = needs_review

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <image_path>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    result = extract_screenshot_data(img_path)
    
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
