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
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, 'students.json')

try:
    response = requests.get("https://api.planaai.kro.kr/api/students", timeout=5)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict):
            # If it's a dict like {"시로코": {...}}
            STUDENT_NAMES = list(data.keys())
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], dict):
                # If it's a list of objects
                k = 'name' if 'name' in data[0] else 'studentName' if 'studentName' in data[0] else 'id' if 'id' in data[0] else list(data[0].keys())[0]
                STUDENT_NAMES = [str(item.get(k, '')) for item in data if item.get(k)]
            else:
                # If it's a list of strings
                STUDENT_NAMES = [str(x) for x in data]
        
        if not STUDENT_NAMES:
            raise Exception("Server returned empty list or unparseable format")
            
        # Compare and update local json
        local_names = []
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    local_names = json.load(f)
            except:
                pass
                
        if local_names != STUDENT_NAMES:
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(STUDENT_NAMES, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print("Could not save updated students.json:", e)

    else:
        raise Exception(f"Server returned {response.status_code}")
except Exception as e:
    print("Could not load students from server, falling back to local:", e)
    try:
        # Fallback to local students.json
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
    clean_ex = re.sub(r'[^가-힣a-zA-Z0-9�]', '', extracted_name)
    if not clean_ex: 
        log_debug("Cleaned name is empty.")
        return ""
        
    # Apply manual OCR fallbacks for known difficult cases
    ocr_fallbacks = {
        "숲": "슌",
        "순": "슌",
        "숨": "슌",
        "슘": "슌",
        "춘": "슌",
        "": "슌",
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
        "웨이": "케이",
        "소": "슌",
        "춘": "슌"
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
    "studentName": (85, 810, 350, 70),
    "bondRank": (50, 835, 60, 40),
    "currentLevel": (20, 870, 120, 50),
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
    "stat_hp": (1120, 350, 230, 40),
    "stat_attack": (1410, 350, 240, 40),
    "stat_defense": (1095, 400, 255, 40),
    "stat_heal": (1410, 400, 240, 40)
}

import sys

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

_ocr_init_ok = True
try:
    reader_ko = RapidOCR(
        rec_model_path=get_resource_path("models/korean_PP-OCRv3_rec_infer.onnx"),
        rec_keys_path=get_resource_path("models/korean_dict.txt")
    )
    reader_en = RapidOCR()
except Exception as e:
    log_debug(f"[CRITICAL] RapidOCR initialization failed: {e}")
    _ocr_init_ok = False
    reader_ko = None
    reader_en = None

def count_stars(img_crop, is_weapon=False):
    hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
    if not is_weapon:
        # Yellow for student stars
        lower_color = np.array([15, 100, 100])
        upper_color = np.array([40, 255, 255])
        expected_w = 24.0
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
            if re.search(r'[가-힣�]', part):
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
        
    # An empty slot (e.g., unreleased bond gear or unequipped slot) consists only of 
    # bright background colors and faint outlines, resulting in very low contrast.
    # Real items have sharp outlines, shadows, and dark tier badges, giving higher variance.
    if np.std(gray) < 20:
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
    
    # 1. Use V-channel thresholding first, which is best for the bond rank heart
    scaled = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(scaled, cv2.COLOR_BGR2HSV)
    v = hsv[:,:,2]
    _, thresh = cv2.threshold(v, 100, 255, cv2.THRESH_BINARY_INV)
    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    
    try:
        res, _ = reader_en.text_recognizer([thresh_bgr])
        if res and len(res) > 0:
            text = "".join(res[0][0]).replace(" ", "")
            text = "".join(c for c in text if c in '0123456789LvlIOoSs')
            if parse_number(text): 
                return text
    except:
        pass
        
    # 2. If it fails, do a wider center crop to avoid heart borders, with a simple white padding
    ch, cw = thresh.shape
    center = thresh[int(ch*0.2):int(ch*0.8), int(cw*0.15):int(cw*0.85)]
    if center.size > 0:
        center_inv = cv2.bitwise_not(center)
        padded = np.full((center.shape[0] + 40, center.shape[1] + 40), 255, dtype=np.uint8)
        ch_c, cw_c = center_inv.shape
        padded[20:20+ch_c, 20:20+cw_c] = center_inv
        
        try:
            res, _ = reader_en.text_recognizer([cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)])
            if res and len(res) > 0:
                t = "".join(res[0][0]).replace(" ", "")
                t = "".join(c for c in t if c in '0123456789LvlIOoSs')
                if parse_number(t):
                    return t
        except:
            pass
            
    # 3. Ultimate fallback to raw image
    return extract_text(img, bbox, allowlist='0123456789LvlIOoSs', scale=2)

def parse_number(text):
    if not text:
        return None
        
    # Replace common OCR misreads for numbers
    text = text.replace('l', '1').replace('I', '1').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5').replace('z', '2').replace('Z', '2')
    
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
    text = text.replace('S', '5').replace('s', '5').replace('O', '0').replace('o', '0').replace('z', '2').replace('Z', '2')
    
    match = re.search(r'(?:[LlI][VvYy]*|1[VvYy]+|[Vv])[:.]?\s*(\d+)', text)
    if match:
        ability = int(match.group(1))
        if ability > 25: ability = 25
        text = text[:match.start()]
    stat_val = parse_number(text)
    if stat_val: 
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
        if len(val_str) > 1 and val_str[0] in ('1', '7'):
            val_str = val_str[1:]
        else:
            val_str = val_str[:-1]
    return int(val_str) if val_str else 0

def parse_equip(text, is_bond_gear=False):
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
    match_lv = re.search(r'(?:[LlI][VvYy]*|1[VvYy]+|[Vv])[:.]?\s*(\d+)', text)
    if match_lv:
        level = int(match_lv.group(1))
        
    if tier == 0 and level == 0:
        return {"tier": 0, "level": 0}
        
    if not is_bond_gear:
        # If a low tier item has no T badge (e.g. T1 Lv.15), it only says Lv.15
        if tier == 0 and level > 0:
            tier = 1
            
        if level > 90:
            level = int(str(level)[:2])
    else:
        # Bond Gears only have Tier, no Level.
        # If there's no T badge but a level, it's likely reading locked requirement text
        if tier == 0 and level > 0:
            return {"tier": 0, "level": 0}
        level = 0

    return {"tier": tier, "level": level}

def get_calibrated_rois(img):
    h, w = img.shape[:2]
    # Ensure height is 1080 for ROI calculations
    if h != 1080:
        w = int(w * 1080 / h)
        
    if w <= 1930:
        return ROI_CONFIG
        
    extra_w = w - 1920
    
    # 4 UI Blocks based on exact Flex-box layout ratios:
    # 1. Left Panel (Name, Level, Stars, Bond)
    dx_left = int(extra_w * 0.234)
    # 2. Stats Left Column (HP, DEF)
    dx_stats_left = int(extra_w * 0.370)
    # 3. Stats Right Column (ATK, HEAL)
    dx_stats_right = int(extra_w * 0.476)
    # 4. Right Panel (Skills, Weapon, Equip)
    dx_right_panel = int(extra_w * 0.640)
    
    # Vertical shift: Y-axis also slightly shifts up in wide aspect ratios
    dy_stats = int(-25 * extra_w / 640)
    dy_equip = int(80 * extra_w / 640)
    dy_weapon = int(30 * extra_w / 640)
    
    calibrated = {}
    for key, (x, y, bw, bh) in ROI_CONFIG.items():
        if x < 960:
            calibrated[key] = (x + dx_left, y + dy_stats, bw, bh)
        elif key in ["stat_hp", "stat_defense"]:
            calibrated[key] = (x + dx_stats_left, y + dy_stats, bw, bh)
        elif key in ["stat_attack", "stat_heal"]:
            calibrated[key] = (x + dx_stats_right, y + dy_stats, bw, bh)
        elif key == "weapon_level":
            calibrated[key] = (x + int(290 * extra_w / 640), y + dy_weapon, 120, bh)
        elif key == "weapon_stars_area":
            calibrated[key] = (x + int(460 * extra_w / 640), y + dy_weapon, 120, bh)
        elif key == "equip_1":
            calibrated[key] = (x + int(340 * extra_w / 640), y + dy_equip - 10, bw, 145)
        elif key == "equip_2":
            calibrated[key] = (x + int(356 * extra_w / 640), y + dy_equip - 10, bw, 145)
        elif key == "equip_3":
            calibrated[key] = (x + int(384 * extra_w / 640), y + dy_equip - 10, bw, 145)
        elif key == "equip_4":
            calibrated[key] = (x + int(420 * extra_w / 640), y + dy_equip - 10, bw, 145)
        else:
            calibrated[key] = (x + dx_right_panel, y, bw, bh)
            
    return calibrated

_cached_align_offsets = None

def preprocess_image(img):
    """
    와이드 모니터 또는 창 모드(해상도 변경 등)로 인해 UI 위치가 어긋난 경우,
    OCR을 통해 기준점(Anchor)을 동적으로 찾아 완벽한 1920x1080 캔버스에 재조립합니다.
    """
    global _cached_align_offsets
    h, w = img.shape[:2]
    
    if w == 1920 and h == 1080:
        return img
        
    if _cached_align_offsets is not None:
        dx_left, dx_right, dy = _cached_align_offsets
    else:
        dx_left, dx_right, dy = 0, 0, 0
        
        # 1. Find Left Anchor (STRIKER, SPECIAL, FRONT 등)
        left_crop = img[700:1080, :w//2]
        res, _ = reader_ko(left_crop)
        if res:
            for line in res:
                bbox, text, conf = line
                if 'STRIKER' in text or 'SPECIAL' in text:
                    abs_x = bbox[0][0]
                    abs_y = bbox[0][1] + 700
                    dx_left = int(abs_x - 558)
                    dy = int(abs_y - 840)
                    break
                elif 'FRONT' in text or 'MIDDLE' in text or 'BACK' in text:
                    abs_x = bbox[0][0]
                    abs_y = bbox[0][1] + 700
                    dx_left = int(abs_x - 75)
                    dy = int(abs_y - 1014)
                    break
                    
        # 2. Find Right Anchor (치유력, 방어력 등 고정 스탯 텍스트)
        right_crop = img[200:600, w//2:]
        res, _ = reader_ko(right_crop)
        if res:
            for line in res:
                bbox, text, conf = line
                if '치유력' in text:
                    abs_x = bbox[0][0] + w//2
                    dx_right = int(abs_x - 1410)
                    break
                elif '방어력' in text:
                    abs_x = bbox[0][0] + w//2
                    dx_right = int(abs_x - 1095)
                    break
                    
        # Fallback for known 2560x1080 21:9 shifted layout
        if dx_left == 0 and dx_right == 0 and w > 1920:
            dx_left, dx_right, dy = 150, 305, -21
            
        _cached_align_offsets = (dx_left, dx_right, dy)
        print(f"[Auto-Align] Computed offsets: dx_left={dx_left}, dx_right={dx_right}, dy={dy}")
        
    canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    y_c_start = max(0, -dy)
    y_c_end = min(1080, h - dy)
    y_i_start = y_c_start + dy
    y_i_end = y_c_end + dy
    
    x_c_left_start = max(0, -dx_left)
    x_c_left_end = min(960, w - dx_left)
    x_i_left_start = x_c_left_start + dx_left
    x_i_left_end = x_c_left_end + dx_left
    
    if y_c_end > y_c_start and x_c_left_end > x_c_left_start:
        canvas[y_c_start:y_c_end, x_c_left_start:x_c_left_end] = img[y_i_start:y_i_end, x_i_left_start:x_i_left_end]
        
    x_c_right_start = max(960, -dx_right)
    x_c_right_end = min(1920, w - dx_right)
    x_i_right_start = x_c_right_start + dx_right
    x_i_right_end = x_c_right_end + dx_right
    
    if y_c_end > y_c_start and x_c_right_end > x_c_right_start:
        canvas[y_c_start:y_c_end, x_c_right_start:x_c_right_end] = img[y_i_start:y_i_end, x_i_right_start:x_i_right_end]
        
    return canvas

def extract_screenshot_data(img_path):
    print(f"Processing image: {img_path}")
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if img is None:
        print("Failed to load image.")
        return None
        
    h, w = img.shape[:2]
    if h != 1080:
        new_w = int(w * 1080 / h)
        img = cv2.resize(img, (new_w, 1080), interpolation=cv2.INTER_CUBIC)
        
    rois = get_calibrated_rois(img)
    
    data = {}
    
    # 1. OCR Extraction
    data["studentName"] = match_student_name(extract_text(img, rois["studentName"], scale=3, is_name=True))
    
    # Disambiguate '케이' vs '레이' using Attack Type color (Mystic=Blue vs Sonic=Purple)
    if data["studentName"] == "케이":
        atk_type_crop = img[rois["studentName"][1]+60:rois["studentName"][1]+110, rois["studentName"][0]+215:rois["studentName"][0]+315]
        if atk_type_crop.shape[0] > 0 and atk_type_crop.shape[1] > 0:
            hsv_crop = cv2.cvtColor(atk_type_crop, cv2.COLOR_BGR2HSV)
            purple_mask = cv2.inRange(hsv_crop, np.array([125, 50, 50]), np.array([165, 255, 255]))
            if cv2.countNonZero(purple_mask) > 500:
                data["studentName"] = "레이"
            
    num_allowlist = '0123456789LvlIOoSszZ'
    
    data["bondRank"] = parse_number(extract_bond_text(img, rois["bondRank"]))
    if data["bondRank"] is None:
        data["bondRank"] = 0
        
    data["currentLevel"] = parse_number(extract_text(img, rois["currentLevel"], allowlist=num_allowlist, scale=2))
    if data["currentLevel"] is None:
        data["currentLevel"] = 0
        log_debug("[Warning] currentLevel OCR failed, defaulting to 0")
    
    data["skills"] = {
        "ex": parse_skill(extract_text(img, rois["skill_ex"]), is_ex=True),
        "basic": parse_skill(extract_text(img, rois["skill_basic"]), is_ex=False),
        "enh": parse_skill(extract_text(img, rois["skill_enh"]), is_ex=False),
        "sub": parse_skill(extract_text(img, rois["skill_sub"]), is_ex=False)
    }
    
    data["weapon"] = {
        "level": parse_number(extract_text(img, rois["weapon_level"], allowlist=num_allowlist, scale=2)),
    }
    if data["weapon"]["level"] is None:
        data["weapon"]["level"] = 0
    
    t1_text = extract_equip_text(img, rois["equip_1"])
    t2_text = extract_equip_text(img, rois["equip_2"])
    t3_text = extract_equip_text(img, rois["equip_3"])
    t4_text = extract_equip_text(img, rois["equip_4"])
    
    data["equipment"] = {
        "slot1": parse_equip(t1_text),
        "slot2": parse_equip(t2_text),
        "slot3": parse_equip(t3_text),
        "slot4": parse_equip(t4_text, is_bond_gear=True)
    }
    
    # 2. Detailed Stats OCR
    hp_stat, hp_ability = parse_stat_with_ability(extract_text(img, rois["stat_hp"], allowlist=num_allowlist, scale=2, min_length=3))
    atk_stat, atk_ability = parse_stat_with_ability(extract_text(img, rois["stat_attack"], allowlist=num_allowlist, scale=2, min_length=3))
    heal_stat, heal_ability = parse_stat_with_ability(extract_text(img, rois["stat_heal"], allowlist=num_allowlist, scale=2, min_length=3))

    data["stats"] = {
        "maxHP": clamp_stat(hp_stat, 200000),
        "hpAbility": hp_ability,
        "attackPower": clamp_stat(atk_stat, 25000),
        "atkAbility": atk_ability,
        "defensePower": clamp_stat(parse_number(extract_text(img, rois["stat_defense"], allowlist=num_allowlist, scale=2)), 10000),
        "healPower": clamp_stat(heal_stat, 35000),
        "healAbility": heal_ability
    }
    
    # 3. Star Counting (OpenCV)
    stars_x, stars_y, stars_w, stars_h = rois["stars_area"]
    stars_crop = img[stars_y:stars_y+stars_h, stars_x:stars_x+stars_w]
    data["currentStar"] = count_stars(stars_crop, is_weapon=False)
    
    w_stars_x, w_stars_y, w_stars_w, w_stars_h = rois["weapon_stars_area"]
    w_stars_crop = img[w_stars_y:w_stars_y+w_stars_h, w_stars_x:w_stars_x+w_stars_w]
    data["weapon"]["star"] = count_stars(w_stars_crop, is_weapon=True)
    
    # 4. Post-processing validation
    validate_extracted_data(data)
    
    return data

# Weapon max level per star grade: 3성=50, 4성=60
WEAPON_MAX_LEVEL_BY_STAR = {0: 0, 1: 30, 2: 40, 3: 50, 4: 60}

def validate_extracted_data(data):
    """Post-processing to fix common OCR misreads based on game logic constraints."""
    
    # 0-1. Lock skills based on star grade
    # 1-star: enh and sub are locked (level 1)
    # 2-star: sub is locked (level 1)
    current_star = data.get("currentStar") or 0
    if current_star == 1:
        if "skills" in data:
            data["skills"]["enh"] = 1
            data["skills"]["sub"] = 1
            log_debug(f"[Validation] 1성 강제 스킬 레벨 조정 (enh=1, sub=1)")
    elif current_star == 2:
        if "skills" in data:
            data["skills"]["sub"] = 1
            log_debug(f"[Validation] 2성 강제 스킬 레벨 조정 (sub=1)")
            
    # 0-2. Fix Level > 90 trailing 1
    current_level = data.get("currentLevel") or 0
    if current_level > 90:
        lvl_str = str(data["currentLevel"])
        if lvl_str.endswith("1"):
            log_debug(f"[Validation] currentLevel {lvl_str} -> {lvl_str[:-1]} 보정 (name={data.get('studentName')})")
            data["currentLevel"] = int(lvl_str[:-1])
            
        if (data.get("currentLevel") or 0) > 90:
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
