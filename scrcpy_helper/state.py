import os
import collections
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent

# Config and path files
CONFIG_PATH = str(SCRIPT_DIR / "scrcpy_qr_config.json")
LAST_CONN_PATH = str(SCRIPT_DIR / "scrcpy_last_connection.json")

def _find_exe(name):
    local = SCRIPT_DIR / name
    if local.exists():
        return str(local)
    import shutil
    return shutil.which(name) or str(local)

ADB = _find_exe("adb.exe")
SCRCPY = _find_exe("scrcpy.exe")

DEFAULT_CONFIG = {
    "max_size": 1080,
    "bit_rate": "8M",
    "max_fps": 60,
    "audio": True,
    "turn_screen_off": False,
    "stay_awake": False,
    "keep_active": False,
    "record": False,
    "record_path": "",
    "record_format": "",
    "record_orientation": "0",
    "crop": "",
    "display_orientation": "0",
    "capture_orientation": "0",
    "capture_orientation_lock": False,
    "fullscreen": False,
    "always_on_top": False,
    "window_title": "",
    "no_control": False,
    "video_source": "display",
    "video_codec": "h264",
    "video_buffer": "",
    "camera_id": "",
    "camera_facing": "front",
    "camera_size": "",
    "camera_fps": "",
    "camera_torch": False,
    "camera_high_speed": False,
    "camera_zoom": "",
    "camera_ar": "",
    "audio_source": "output",
    "audio_dup": False,
    "audio_codec": "opus",
    "audio_bit_rate": "",
    "audio_buffer": "",
    "window_borderless": False,
    "show_touches": False,
    "time_limit": "",
    "screen_off_timeout": "",
}

# Shared variables across modules
phone_ip = ""
pair_result = ""
connect_result = ""
status_msg = "waiting"
device_serial = ""
_pair_password = ""
app_config = dict(DEFAULT_CONFIG)
_qr_b64 = ""
_local_ip = ""
_service_name = ""

# Logging
log_queue = collections.deque(maxlen=150)
log_lock = threading.Lock()

# scrcpy process
scrcpy_process = None
scrcpy_lock = threading.Lock()

# Cache for device models
_model_cache = {}
_MODEL_CACHE_TTL = 300

def log_msg(msg):
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    with log_lock:
        log_queue.append(formatted)

def _read_stream(stream, prefix):
    try:
        for line in stream:
            cleaned = line.strip()
            if cleaned:
                log_msg(f"[{prefix}] {cleaned}")
    except Exception:
        pass
