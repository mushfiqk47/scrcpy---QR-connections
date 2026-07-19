import subprocess
import time
import re
from . import state

def run_adb(args, timeout=15):
    cmd = [state.ADB] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if args and args[0] not in ("mdns", "devices") and "ro.product.model" not in args:
            state.log_msg(f"adb {' '.join(args)} -> code {result.returncode}")
            if result.stderr.strip():
                state.log_msg(f"adb stderr: {result.stderr.strip()}")
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        state.log_msg(f"[X] adb {' '.join(args)} timed out")
        return "", "timeout", -1
    except FileNotFoundError:
        state.log_msg(f"[X] adb.exe not found at {state.ADB}")
        return "", "adb.exe not found", -1

def is_device_online(serial, retries=4):
    for _ in range(retries):
        out, _, _ = run_adb(["devices"], timeout=5)
        for line in out.split("\n")[1:]:
            if serial in line and "device" in line and "offline" not in line and "unauthorized" not in line:
                return True
        time.sleep(0.5)
    return False

def get_device_model(target):
    if not target:
        return "Android Device"
    # Check cache first
    now = time.time()
    if target in state._model_cache:
        cached_model, cached_time = state._model_cache[target]
        if now - cached_time < state._MODEL_CACHE_TTL:
            return cached_model
    out, err, code = run_adb(["-s", target, "shell", "getprop", "ro.product.model"], timeout=5)
    if not out.strip() or code != 0:
        out, err, code = run_adb(["shell", "getprop", "ro.product.model"], timeout=5)
    model = out.strip()
    result = model if model else "Android Device"
    state._model_cache[target] = (result, now)
    return result

def scan_mdns(service_type, target_ip=None, timeout=15):
    service = "_adb-tls-pairing._tcp" if service_type == "pairing" else "_adb-tls-connect._tcp"
    for attempt in range(timeout):
        out, _, _ = run_adb(["mdns", "services"])
        for line in out.split("\n"):
            if service in line and (not target_ip or target_ip in line):
                for p in line.strip().split():
                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                        return p
        if attempt % 5 == 4:
            print(f"  [*] Scanning {service_type}... ({attempt+1}s)")
        time.sleep(1)
    return None

def ensure_single_device(device_ip):
    out, _, _ = run_adb(["devices"])
    lines = [l for l in out.split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) <= 1:
        return
    for line in lines:
        serial = line.split()[0]
        if "._tcp" in serial:
            run_adb(["disconnect", serial])
            print(f"  [-] Removed duplicate: {serial}")

def get_connected_serial(device_ip):
    out, _, _ = run_adb(["devices"])
    for line in out.split("\n")[1:]:
        line = line.strip()
        if device_ip in line and "device" in line:
            parts = line.split()
            if parts:
                return parts[0]
    return device_ip
