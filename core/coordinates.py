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
        self.active_preset_name = "QHD"
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
        
        # Load system presets (QHD baseline and FHD standard)
        system_presets_dir = os.path.join(get_bundle_dir(), "config", "presets")
        for sys_name in ["QHD", "FHD"]:
            sys_path = os.path.join(system_presets_dir, f"{sys_name}.json")
            if os.path.exists(sys_path):
                try:
                    with open(sys_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.presets[sys_name] = Preset(sys_name, data.get("values", {}))
                except Exception as e:
                    logger.error(f"Failed to load system preset {sys_name}.json: {e}")
                    self.presets[sys_name] = Preset(sys_name, {})
            else:
                self.presets[sys_name] = Preset(sys_name, {})

        # Load additional system presets if present (excluding legacy default.json)
        if os.path.exists(system_presets_dir):
            for fname in os.listdir(system_presets_dir):
                if fname.endswith(".json") and fname not in ("default.json", "QHD.json", "FHD.json"):
                    path = os.path.join(system_presets_dir, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            name = data.get("name", fname.replace(".json", ""))
                            base_name = data.get("base", "QHD")
                            if base_name == "default" or base_name not in self.presets:
                                base_name = "QHD"
                            merged_values = dict(self.presets.get(base_name, Preset(base_name, {})).values)
                            merged_values.update(data.get("values", {}))
                            self.presets[name] = Preset(name, merged_values)
                    except Exception as e:
                        logger.error(f"Failed to load system preset {fname}: {e}")

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
                        if name == "default":
                            continue
                        
                        base_name = data.get("base", "QHD")
                        if base_name == "default" or base_name not in self.presets:
                            base_name = "QHD"
                        
                        base_preset = self.presets.get(base_name, self.presets.get("QHD", Preset("QHD", {})))
                        merged_values = dict(base_preset.values)
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
                    name = data.get("active_preset", "QHD")
                    if name == "default":
                        name = "QHD"
                    if name in self.presets:
                        self.active_preset_name = name
                    else:
                        self.active_preset_name = "QHD"
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
        return self.presets.get(self.active_preset_name, self.presets.get("QHD", Preset("QHD", {})))

    def region(self, key: str) -> tuple[float, float, float, float]:
        val = self.active_preset().values.get(key, [0, 0, 0, 0])
        # If it's a dict (from old config), normalize to tuple
        if isinstance(val, dict):
            return (val.get('x',0), val.get('y',0), val.get('w',0), val.get('h',0))
        return tuple(val)

    def region_px(self, key: str, size=(2560, 1440)) -> tuple[int, int, int, int]:
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
                qhd_preset = self.presets.get("QHD", Preset("QHD", {}))
                for k, v in regions.items():
                    if isinstance(v, dict):
                        val = [v['x'], v['y'], v['w'], v['h']]
                    else:
                        val = v
                    
                    base_val = qhd_preset.values.get(k)
                    if base_val and val != base_val:
                        diff[k] = val
        except Exception as e:
            logger.error(f"Migration error: {e}")
            
        if diff:
            # Create a migrated preset
            preset_data = {
                "schema_version": 1,
                "name": "migrated",
                "base": "QHD",
                "note": "이전 버전에서 가져온 좌표 보정값",
                "values": diff
            }
            try:
                os.makedirs(user_presets_dir, exist_ok=True)
                with open(migrated_path, "w", encoding="utf-8") as f:
                    json.dump(preset_data, f, indent=2, ensure_ascii=False)
                # Load it
                merged = dict(self.presets.get("QHD", Preset("QHD", {})).values)
                merged.update(diff)
                self.presets["migrated"] = Preset("migrated", merged)
                self.active_preset_name = "migrated"
            except Exception as e:
                logger.error(f"Failed to save migrated preset: {e}")
