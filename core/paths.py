import os
import sys

def get_bundle_dir() -> str:
    """Return the base directory for bundled read-only files (or source root in dev)."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_user_data_dir() -> str:
    """Return the user data directory for writable files like user presets and settings."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    path = os.path.join(base, "user_data")
    os.makedirs(path, exist_ok=True)
    return path
