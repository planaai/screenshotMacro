import json
import os

coordinates = {
  "aspect_ratio": "16:9",
  "regions": {
    "student_name": {"x": 0.056, "y": 0.771, "w": 0.143, "h": 0.052},
    "bond_rank": {"x": 0.033, "y": 0.777, "w": 0.023, "h": 0.037},
    "student_level": {"x": 0.028, "y": 0.818, "w": 0.037, "h": 0.037},
    "student_stars": {"x": 0.203, "y": 0.786, "w": 0.063, "h": 0.036},
    "equip_1_box": {"x": 0.533, "y": 0.765, "w": 0.062, "h": 0.117},
    "equip_2_box": {"x": 0.605, "y": 0.767, "w": 0.069, "h": 0.123},
    "equip_3_box": {"x": 0.676, "y": 0.769, "w": 0.069, "h": 0.123},
    "equip_4_box": {"x": 0.749, "y": 0.767, "w": 0.069, "h": 0.123},
    "equip_1_tier_box": {"x": 0.53, "y": 0.836, "w": 0.036, "h": 0.063},
    "equip_2_tier_box": {"x": 0.601, "y": 0.83, "w": 0.036, "h": 0.063},
    "equip_3_tier_box": {"x": 0.674, "y": 0.834, "w": 0.036, "h": 0.063},
    "equip_4_tier_box": {"x": 0.748, "y": 0.831, "w": 0.036, "h": 0.063}
  }
}

equipment_ui = {
  "points": {
    "equipment_button": [0.88, 0.828],
    "slot_1": [0.097, 0.292],
    "slot_2": [0.097, 0.455],
    "slot_3": [0.097, 0.618],
    "main_slot_4": [0.783, 0.828],
    "equipment_menu_close": [0.936, 0.144],
    "favorite_popup_close": [0.852, 0.165]
  },
  "regions": {
    "equipment_button_search": [0.8, 0.757, 0.173, 0.133],
    "equipment_menu_title": [0.42, 0.107, 0.163, 0.073],
    "detail_panel": [0.16, 0.207, 0.383, 0.523],
    "detail_tier_badge": [0.262, 0.33, 0.063, 0.057],
    "detail_level": [0.318, 0.33, 0.078, 0.057],
    "favorite_tier_badge": [0.409, 0.545, 0.051, 0.066],
    "popup_detect_area": [0.121, 0.118, 0.763, 0.763]
  }
}

# 1920x1080 -> relative
def to_rel(roi):
    x, y, w, h = roi
    return [round(x/1920, 4), round(y/1080, 4), round(w/1920, 4), round(h/1080, 4)]

extractor_roi = {
    "skill_ex": to_rel((1000, 580, 120, 60)),
    "skill_basic": to_rel((1180, 580, 120, 60)),
    "skill_enh": to_rel((1340, 580, 120, 60)),
    "skill_sub": to_rel((1500, 580, 120, 60)),
    "weapon_level": to_rel((1200, 680, 80, 60)),
    "weapon_stars_area": to_rel((1500, 750, 160, 40)),
    "stat_hp": to_rel((1120, 350, 230, 40)),
    "stat_attack": to_rel((1410, 350, 240, 40)),
    "stat_defense": to_rel((1095, 400, 255, 40)),
    "stat_heal": to_rel((1410, 400, 240, 40)),
    "macro_name_compare": to_rel((120, 840, 300, 40)),
    "next_student_button": [0.98, 0.5]
}

items = {}
defaults = {}

# Student Info Scene
def add_item(key, typ, scene, group, label, val, is_advanced=False):
    items[key] = {
        "type": typ,
        "scene": scene,
        "group": group,
        "label": label,
        "guide": f"guides/{key}.md"
    }
    if is_advanced:
        items[key]["advanced"] = True
    defaults[key] = val

for k, v in coordinates["regions"].items():
    add_item(k, "region", "student_info", "기본 정보 ROI", k.replace("_", " ").title(), [v["x"], v["y"], v["w"], v["h"]])

add_item("equipment_button_search", "region", "student_info", "장비 버튼 찾기", "장비 버튼 범위", equipment_ui["regions"]["equipment_button_search"])
add_item("equipment_button", "point", "student_info", "장비 버튼", "장비 버튼 클릭", equipment_ui["points"]["equipment_button"])

# Advanced student info
for k, v in extractor_roi.items():
    typ = "point" if len(v) == 2 else "region"
    add_item(k, typ, "student_info", "고급 ROI (스킬/스탯/매크로)", k.replace("_", " ").title(), v, is_advanced=True)

# Equipment Modal Scene
eq_regs = ["equipment_menu_title", "detail_panel", "detail_tier_badge", "detail_level"]
for k in eq_regs:
    add_item(k, "region", "equipment_modal", "장비 상세 패널", k.replace("_", " ").title(), equipment_ui["regions"][k])
eq_pts = ["equipment_menu_close", "slot_1", "slot_2", "slot_3", "main_slot_4"]
for k in eq_pts:
    add_item(k, "point", "equipment_modal", "클릭 포인트", k.replace("_", " ").title(), equipment_ui["points"][k])

# Favorite Popup
fav_regs = ["favorite_tier_badge", "popup_detect_area"]
for k in fav_regs:
    add_item(k, "region", "favorite_popup", "애용품 팝업", k.replace("_", " ").title(), equipment_ui["regions"][k])
add_item("favorite_popup_close", "point", "favorite_popup", "애용품 팝업", "팝업 닫기", equipment_ui["points"]["favorite_popup_close"])

schema = {
    "version": 1,
    "base_resolution": [1920, 1080],
    "scenes": {
        "student_info": {"label": "학생 정보 화면", "reference_image": "guides/scenes/student_info.png"},
        "equipment_modal": {"label": "장비 성장 창", "reference_image": "guides/scenes/equipment_modal.png"},
        "favorite_popup": {"label": "애용품 정보 팝업", "reference_image": "guides/scenes/favorite_popup.png"}
    },
    "items": items
}

preset = {
    "schema_version": 1,
    "name": "default",
    "base": "default",
    "created_at": "2026-10-09T00:00:00+09:00",
    "updated_at": "2026-10-09T00:00:00+09:00",
    "note": "기본 좌표값 (16:9 1080p 기준)",
    "values": defaults
}

os.makedirs("config/presets", exist_ok=True)
with open("config/coord_schema.json", "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=2, ensure_ascii=False)
with open("config/presets/default.json", "w", encoding="utf-8") as f:
    json.dump(preset, f, indent=2, ensure_ascii=False)

print("Generated config/coord_schema.json and config/presets/default.json")
