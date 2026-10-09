import os
import json
import logging
from typing import Callable, Any
from dataclasses import dataclass
from core.paths import get_bundle_dir, get_user_data_dir

logger = logging.getLogger("coordinates")

@dataclass
class Preset:
    name: str
    values: dict[str, Any]

class CoordinateService:
    _instance = None

    @classmethod
    def instance(cls) -> "CoordinateService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.schema = {}
        self.presets: dict[str, Preset] = {}
        self.active_preset_name = "default"
        self._listeners: list[Callable[[], None]] = []
        
        self.load_schema()
        self.load_all_presets()
        self.migrate_old_configs()
        self.load_settings()

    def load_schema(self):
        path = os.path.join(get_bundle_dir(), "config", "coord_schema.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load coord_schema.json: {e}")
            self.schema = {"items": {}}

    def load_all_presets(self):
        self.presets.clear()
        
        # Load default
        default_path = os.path.join(get_bundle_dir(), "config", "presets", "default.json")
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.presets["default"] = Preset("default", data.get("values", {}))
        except Exception as e:
            logger.error(f"Failed to load default.json: {e}")
            self.presets["default"] = Preset("default", {})

        # Load user presets
        user_presets_dir = os.path.join(get_user_data_dir(), "presets")
        os.makedirs(user_presets_dir, exist_ok=True)
        for fname in os.listdir(user_presets_dir):
            if fname.endswith(".json"):
                path = os.path.join(user_presets_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        name = data.get("name", fname.replace(".json", ""))
                        
                        # Merge with base (default)
                        merged_values = dict(self.presets["default"].values)
                        merged_values.update(data.get("values", {}))
                        
                        self.presets[name] = Preset(name, merged_values)
                except Exception as e:
                    logger.error(f"Failed to load preset {fname}: {e}")

    def load_settings(self):
        settings_path = os.path.join(get_user_data_dir(), "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = data.get("active_preset", "default")
                    if name in self.presets:
                        self.active_preset_name = name
        except Exception as e:
            logger.error(f"Failed to load settings.json: {e}")

    def save_settings(self):
        settings_path = os.path.join(get_user_data_dir(), "settings.json")
        try:
            data = {"active_preset": self.active_preset_name}
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save settings.json: {e}")

    def set_active_preset(self, name: str):
        if name in self.presets:
            self.active_preset_name = name
            self.save_settings()
            self._notify_listeners()

    def active_preset(self) -> Preset:
        return self.presets.get(self.active_preset_name, self.presets["default"])

    def region(self, key: str) -> tuple[float, float, float, float]:
        val = self.active_preset().values.get(key, [0, 0, 0, 0])
        # If it's a dict (from old config), normalize to tuple
        if isinstance(val, dict):
            return (val.get('x',0), val.get('y',0), val.get('w',0), val.get('h',0))
        return tuple(val)

    def region_px(self, key: str, size=(1920, 1080)) -> tuple[int, int, int, int]:
        r = self.region(key)
        return (int(r[0]*size[0]), int(r[1]*size[1]), int(r[2]*size[0]), int(r[3]*size[1]))

    def point(self, key: str) -> tuple[float, float]:
        val = self.active_preset().values.get(key, [0, 0])
        return tuple(val)

    def on_changed(self, callback: Callable[[], None]):
        self._listeners.append(callback)

    def _notify_listeners(self):
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in coordinate listener: {e}")

    def migrate_old_configs(self):
        user_presets_dir = os.path.join(get_user_data_dir(), "presets")
        migrated_path = os.path.join(user_presets_dir, "migrated.json")
        if os.path.exists(migrated_path):
            return  # Already migrated
            
        old_coord_path = os.path.join(get_bundle_dir(), "config", "coordinates.json")
        
        diff = {}
        try:
            if os.path.exists(old_coord_path):
                with open(old_coord_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    
                regions = old_data.get("regions", {})
                for k, v in regions.items():
                    if isinstance(v, dict):
                        val = [v['x'], v['y'], v['w'], v['h']]
                    else:
                        val = v
                    
                    default_val = self.presets["default"].values.get(k)
                    if default_val and val != default_val:
                        diff[k] = val
        except Exception as e:
            logger.error(f"Migration error: {e}")
            
        if diff:
            # Create a migrated preset
            preset_data = {
                "schema_version": 1,
                "name": "migrated",
                "base": "default",
                "note": "이전 버전에서 가져온 좌표 보정값",
                "values": diff
            }
            try:
                os.makedirs(user_presets_dir, exist_ok=True)
                with open(migrated_path, "w", encoding="utf-8") as f:
                    json.dump(preset_data, f, indent=2, ensure_ascii=False)
                # Load it
                merged = dict(self.presets["default"].values)
                merged.update(diff)
                self.presets["migrated"] = Preset("migrated", merged)
                self.active_preset_name = "migrated"
            except Exception as e:
                logger.error(f"Failed to save migrated preset: {e}")
