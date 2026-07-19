import os
import json
import time
from . import state

def load_config():
    try:
        if os.path.exists(state.CONFIG_PATH):
            with open(state.CONFIG_PATH, "r") as f:
                saved = json.load(f)
                for k in state.DEFAULT_CONFIG:
                    if k in saved:
                        state.app_config[k] = saved[k]
    except Exception as e:
        state.log_msg(f"[X] Failed to load config: {e}")

def save_config(data):
    for k in state.DEFAULT_CONFIG:
        if k in data:
            state.app_config[k] = data[k]
    try:
        with open(state.CONFIG_PATH, "w") as f:
            json.dump(state.app_config, f, indent=2)
    except Exception as e:
        state.log_msg(f"[X] Failed to save config: {e}")

LAST_CONN = None

def save_last_connection(ip, port, serial, password=""):
    global LAST_CONN
    target = f"{ip}:{port}" if port else ip
    
    # Delayed import of adb to prevent circular dependency
    from . import adb
    model_name = adb.get_device_model(serial if serial else target)
    LAST_CONN = {
        "ip": ip,
        "port": port,
        "serial": serial,
        "device_name": model_name,
        "password": password,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(state.LAST_CONN_PATH, "w") as f:
            json.dump(LAST_CONN, f, indent=2)
        state.log_msg(f"[*] Connection metadata saved for: {model_name} ({target})")
    except Exception as e:
        state.log_msg(f"[X] Failed to save connection cache: {e}")

def load_last_connection():
    global LAST_CONN
    try:
        if os.path.exists(state.LAST_CONN_PATH):
            with open(state.LAST_CONN_PATH, "r") as f:
                LAST_CONN = json.load(f)
                return LAST_CONN
    except Exception as e:
        pass
    LAST_CONN = None
    return None
