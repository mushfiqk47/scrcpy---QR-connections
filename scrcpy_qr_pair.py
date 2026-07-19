import os
import subprocess
import time
import random
import string
import webbrowser
import base64
import io
import json
import threading
import re
import socket
import collections
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = Path(__file__).parent
ADB = str(SCRIPT_DIR / "adb.exe")
SCRCPY = str(SCRIPT_DIR / "scrcpy.exe")
CONFIG_PATH = str(SCRIPT_DIR / "scrcpy_qr_config.json")
LAST_CONN_PATH = str(SCRIPT_DIR / "scrcpy_last_connection.json")

DEFAULT_CONFIG = {
    "max_size": 1080,
    "bit_rate": "8M",
    "max_fps": 60,
    "audio": True,
    "turn_screen_off": False,
    "stay_awake": False,
    "record": False,
    "record_path": "",
    "crop": "",
    "lock_video_orientation": 0,
    "fullscreen": False,
    "always_on_top": False,
    "window_title": "",
    "no_control": False,
}

phone_ip = ""
pair_port = ""
pair_result = ""
connect_result = ""
status_msg = "waiting"
device_serial = ""
_pair_password = ""
app_config = dict(DEFAULT_CONFIG)
_was_reconnected = False
_qr_b64 = ""
_local_ip = ""
_service_name = ""

# Logging and dynamic reload globals
log_queue = collections.deque(maxlen=150)
log_lock = threading.Lock()
scrcpy_process = None
scrcpy_lock = threading.Lock()

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


def generate_id(length=14):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_password(length=21):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_qr_image(data):
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def img_to_base64(img):
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def run_adb(args, timeout=15):
    cmd = [ADB] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if args and args[0] not in ("mdns", "devices") and "ro.product.model" not in args:
            log_msg(f"adb {' '.join(args)} -> code {result.returncode}")
            if result.stderr.strip():
                log_msg(f"adb stderr: {result.stderr.strip()}")
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        log_msg(f"[X] adb {' '.join(args)} timed out")
        return "", "timeout", -1
    except FileNotFoundError:
        log_msg(f"[X] adb.exe not found at {ADB}")
        return "", "adb.exe not found", -1

def get_device_model(target):
    if not target:
        return "Android Device"
    out, err, code = run_adb(["-s", target, "shell", "getprop", "ro.product.model"])
    if not out.strip() or code != 0:
        out, err, code = run_adb(["shell", "getprop", "ro.product.model"])
    model = out.strip()
    return model if model else "Android Device"


def load_config():
    global app_config
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
                for k in DEFAULT_CONFIG:
                    if k in saved:
                        app_config[k] = saved[k]
    except:
        pass

def save_config(data):
    global app_config
    for k in DEFAULT_CONFIG:
        if k in data:
            app_config[k] = data[k]
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(app_config, f, indent=2)
    except:
        pass

LAST_CONN = None

def save_last_connection(ip, port, serial, password=""):
    global LAST_CONN
    target = f"{ip}:{port}" if port else ip
    model_name = get_device_model(serial if serial else target)
    LAST_CONN = {
        "ip": ip,
        "port": port,
        "serial": serial,
        "device_name": model_name,
        "password": password,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(LAST_CONN_PATH, "w") as f:
            json.dump(LAST_CONN, f, indent=2)
        log_msg(f"[*] Connection metadata saved for: {model_name} ({target})")
    except Exception as e:
        log_msg(f"[X] Failed to save connection cache: {e}")


def load_last_connection():
    global LAST_CONN
    try:
        if os.path.exists(LAST_CONN_PATH):
            with open(LAST_CONN_PATH, "r") as f:
                LAST_CONN = json.load(f)
                return LAST_CONN
    except:
        pass
    LAST_CONN = None
    return None

def try_auto_reconnect():
    global phone_ip, connect_result, status_msg, _was_reconnected

    saved = load_last_connection()
    if not saved:
        return False

    ip = saved.get("ip", "")
    port = saved.get("port", "")
    password = saved.get("password", "")

    if not ip:
        return False

    print(f"[*] Saved device found: {ip}:{port}")
    print(f"[*] Saved: {saved.get('timestamp', 'unknown')}")
    print("[*] Trying auto-reconnect...")
    status_msg = "reconnecting"

    if ip and port:
        run_adb(["disconnect"])
        time.sleep(1)
        out, err, code = run_adb(["connect", f"{ip}:{port}"])
        if "connected" in out.lower() or "already" in out.lower():
            print(f"[+] Auto-reconnect OK: {ip}:{port}")
            connect_result = out
            phone_ip = f"{ip}:{port}"
            status_msg = "connected"
            ensure_single_device(ip)
            _was_reconnected = True
            return True

    device_ip = ip.split(":")[0] if ":" in ip else ip
    print("[*] Direct reconnect failed. Scanning mDNS...")

    for attempt in range(15):
        mdns_out, _, _ = run_adb(["mdns", "services"])
        for line in mdns_out.split("\n"):
            if "_adb-tls-connect._tcp" in line and device_ip in line:
                for p in line.strip().split():
                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                        new_ip = p.split(":")[0]
                        new_port = p.split(":")[-1]
                        print(f"[+] mDNS found device at {new_ip}:{new_port}")
                        run_adb(["disconnect"])
                        time.sleep(1)
                        out2, _, _ = run_adb(["connect", f"{new_ip}:{new_port}"])
                        if "connected" in out2.lower() or "already" in out2.lower():
                            connect_result = out2
                            phone_ip = f"{new_ip}:{new_port}"
                            status_msg = "connected"
                            ensure_single_device(new_ip)
                            save_last_connection(new_ip, new_port, saved.get("serial",""), password)
                            _was_reconnected = True
                            return True
        if attempt % 5 == 4:
            print(f"  [*] Scanning mDNS... ({attempt+1}s)")
        time.sleep(1)

    if password:
        print("[*] mDNS connect failed. Trying QR re-pair...")
        for attempt in range(15):
            mdns_out, _, _ = run_adb(["mdns", "services"])
            for line in mdns_out.split("\n"):
                if "_adb-tls-pairing._tcp" in line and device_ip in line:
                    for p in line.strip().split():
                        if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                            pair_addr = p
                            pair_ip = p.split(":")[0]
                            print(f"[+] Found pairing service at {pair_addr}")
                            out3, _, _ = run_adb(["pair", pair_addr, password])
                            if "success" in out3.lower():
                                time.sleep(2)
                                for p2 in line.strip().split():
                                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p2):
                                        connect_port = p2.split(":")[-1]
                                        run_adb(["disconnect"])
                                        time.sleep(1)
                                        out4, _, _ = run_adb(["connect", f"{pair_ip}:{connect_port}"])
                                        if "connected" in out4.lower() or "already" in out4.lower():
                                            connect_result = out4
                                            phone_ip = f"{pair_ip}:{connect_port}"
                                            status_msg = "connected"
                                            ensure_single_device(pair_ip)
                                            save_last_connection(pair_ip, connect_port, saved.get("serial",""), password)
                                            _was_reconnected = True
                                            return True
            if attempt % 5 == 4:
                print(f"  [*] Re-pairing attempt... ({attempt+1}s)")
            time.sleep(1)

    print("[!] Auto-reconnect failed. Will show QR code.")
    status_msg = "waiting"
    return False

def get_scrcpy_cmd():
    cmd = [SCRCPY]
    if phone_ip:
        cmd += ["-s", phone_ip]
    elif device_serial:
        cmd += ["-s", device_serial]
        
    cfg = app_config
    if cfg["max_size"]:
        cmd += ["--max-size", str(cfg["max_size"])]
    if cfg["bit_rate"]:
        cmd += ["--video-bit-rate", cfg["bit_rate"]]
    if cfg["max_fps"]:
        cmd += ["--max-fps", str(cfg["max_fps"])]
    if not cfg["audio"]:
        cmd += ["--no-audio"]
    if cfg["turn_screen_off"]:
        cmd += ["--turn-screen-off"]
    if cfg["stay_awake"]:
        cmd += ["--stay-awake"]
    if cfg["record"] and cfg["record_path"]:
        cmd += ["--record", cfg["record_path"]]
    elif cfg["record"]:
        ts = time.strftime("%Y%m%d_%H%M%S")
        cmd += ["--record", f"scrcpy_recording_{ts}.mp4"]
    if cfg["crop"]:
        cmd += ["--crop", cfg["crop"]]
    if cfg["lock_video_orientation"]:
        cmd += ["--display-orientation", str(cfg["lock_video_orientation"])]
    if cfg["fullscreen"]:
        cmd += ["--fullscreen"]
    if cfg["always_on_top"]:
        cmd += ["--always-on-top"]
    if cfg["window_title"]:
        cmd += ["--window-title", cfg["window_title"]]
    if cfg["no_control"]:
        cmd += ["--no-control"]
    return cmd

def run_scrcpy():
    global scrcpy_process
    with scrcpy_lock:
        if scrcpy_process and scrcpy_process.poll() is None:
            log_msg("[*] Stopping running scrcpy instance for configuration update...")
            scrcpy_process.terminate()
            try:
                scrcpy_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                scrcpy_process.kill()
        
        cmd = get_scrcpy_cmd()
        log_msg(f"[*] Starting scrcpy: {' '.join(cmd[1:])}")
        try:
            scrcpy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            threading.Thread(target=_read_stream, args=(scrcpy_process.stdout, "scrcpy"), daemon=True).start()
            threading.Thread(target=_read_stream, args=(scrcpy_process.stderr, "scrcpy"), daemon=True).start()
        except Exception as e:
            log_msg(f"[X] Failed to launch scrcpy: {e}")


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/status":
            self.send_json({"status": status_msg, "phone_ip": phone_ip, "result": f"{pair_result} | {connect_result}"})

        elif path == "/init":
            self.send_json({
                "qr_b64": _qr_b64,
                "local_ip": _local_ip,
                "service_name": _service_name,
                "saved_device": LAST_CONN,
                "config": app_config,
                "status": status_msg,
            })

        elif path == "/settings":
            self.send_json(app_config)

        elif path == "/connect":
            qs = parse_qs(urlparse(self.path).query)
            target_serial = qs.get("serial", [""])[0]
            self.send_ok()
            threading.Thread(target=do_pairing_flow, args=(_pair_password, target_serial), daemon=True).start()

        elif path == "/reconnect":
            self.send_ok()
            threading.Thread(target=_do_reconnect_flow, daemon=True).start()

        elif path.startswith("/manual"):
            qs = parse_qs(urlparse(self.path).query)
            addr = qs.get("addr", [""])[0]
            code = qs.get("code", [""])[0]
            self.send_ok()
            threading.Thread(target=manual_pair_flow, args=(addr, code), daemon=True).start()

        elif path == "/forget":
            try:
                if os.path.exists(LAST_CONN_PATH):
                    os.remove(LAST_CONN_PATH)
                load_last_connection()
                self.send_json({"ok": True})
            except:
                self.send_json({"ok": False}, 400)

        elif path == "/logs":
            with log_lock:
                logs_list = list(log_queue)
            self.send_json({"logs": logs_list})

        elif path == "/devices":
            devices_list = []
            out, _, _ = run_adb(["devices"])
            lines = out.split("\n")[1:]
            for line in lines:
                line = line.strip()
                if not line or "device" not in line or "offline" in line:
                    continue
                parts = line.split()
                if parts:
                    serial = parts[0]
                    model = get_device_model(serial)
                    devices_list.append({
                        "serial": serial,
                        "model": model
                    })
            self.send_json({"devices": devices_list})

        elif path == "/reset_adb":
            log_msg("[*] Resetting ADB server...")
            run_adb(["kill-server"])
            time.sleep(1)
            run_adb(["start-server"])
            log_msg("[+] ADB server restarted successfully")
            self.send_json({"ok": True})

        else:
            self.send_html()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else "{}"
        if path == "/settings":
            try:
                config_data = json.loads(body)
                save_config(config_data)
                self.send_json({"ok": True})
                
                global scrcpy_process
                is_running = False
                with scrcpy_lock:
                    if scrcpy_process and scrcpy_process.poll() is None:
                        is_running = True
                if is_running:
                    log_msg("[*] Setting changes received. Restarting scrcpy to apply settings...")
                    threading.Thread(target=run_scrcpy, daemon=True).start()
            except Exception as e:
                log_msg(f"[X] Settings save failed: {e}")
                self.send_json({"ok": False}, 400)
        else:
            self.send_json({"ok": False}, 404)


    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_ok(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def send_html(self):
        html_path = SCRIPT_DIR / "scrcpy_ui.html"
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = "<html><body><h1>scrcpy_ui.html not found</h1><p>Place it next to scrcpy_qr_pair.py</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def log_message(self, format, *args):
        pass

def _do_reconnect_flow():
    """Reconnect to saved device from UI button."""
    global status_msg
    status_msg = "reconnecting"
    reconnected = try_auto_reconnect()
    if reconnected:
        print("[+] Reconnect to saved device successful!")
        time.sleep(1)
        run_scrcpy()
    else:
        status_msg = "error"
        print("[!] Reconnect to saved device failed.")



def do_pair_via_qr(password):
    global phone_ip, pair_port, status_msg, pair_result
    status_msg = "waiting"
    for attempt in range(90):
        out, err, code = run_adb(["mdns", "services"])
        for line in out.split("\n"):
            if "_adb-tls-pairing._tcp" in line:
                parts = line.strip().split()
                for p in parts:
                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                        phone_ip = p
                        pair_port = p.split(":")[-1]
                        status_msg = "pairing"
                        print(f"\n[+] Phone found at {phone_ip}")
                        return True
        if attempt % 10 == 9:
            print(f"  [*] Waiting for phone... ({attempt+1}s)")
            status_msg = f"waiting ({attempt+1}s)"
        time.sleep(1)
    return False

def do_adb_pair(password):
    global phone_ip, pair_result
    if not phone_ip:
        return False
    print(f"[*] Running: adb pair {phone_ip} [password]")
    out, err, code = run_adb(["pair", phone_ip, password])
    pair_result = out or err
    print(f"[*] Pair result: {pair_result}")
    if "error" in err.lower() and code != 0:
        return False
    if "success" in out.lower() or "pair" in out.lower():
        return True
    return code == 0

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


def save_connection_from_state(password):
    global phone_ip
    if not phone_ip:
        return
    device_ip = phone_ip.split(":")[0] if ":" in phone_ip else phone_ip
    port = phone_ip.split(":")[1] if ":" in phone_ip else "5555"
    serial = get_connected_serial(device_ip)
    save_last_connection(device_ip, port, serial, password)

def do_adb_connect():
    global phone_ip, connect_result, status_msg
    device_ip = phone_ip.split(":")[0] if ":" in phone_ip else phone_ip
    time.sleep(2)

    connect_port = ""
    for attempt in range(8):
        out, err, code = run_adb(["mdns", "services"])
        for line in out.split("\n"):
            if "_adb-tls-connect._tcp" in line and device_ip in line:
                for p in line.strip().split():
                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                        connect_port = p.split(":")[-1]
                        break
        if connect_port:
            break
        time.sleep(1)

    run_adb(["disconnect"])
    time.sleep(1)

    attempts = []
    if connect_port:
        attempts.append(f"{device_ip}:{connect_port}")
    attempts.append(f"{device_ip}:5555")
    attempts.append(device_ip)

    for target in attempts:
        out, err, code = run_adb(["connect", target])
        connect_result = out or err
        print(f"[*] adb connect {target} -> {connect_result}")
        if "connected" in out.lower() or "already" in out.lower():
            status_msg = "connected"
            phone_ip = target
            ensure_single_device(device_ip)
            return True
    status_msg = "error"
    return False

def do_pairing_flow(password="", target_serial=""):
    global device_serial, status_msg, _pair_password, phone_ip, connect_result
    status_msg = "scanning"
    log_msg("[*] Starting connection flow...")

    if target_serial:
        device_serial = target_serial
        log_msg(f"[*] Target device specified: {device_serial}")
        if "." in device_serial:
            log_msg(f"[+] Device {device_serial} selected. Starting scrcpy...")
            phone_ip = device_serial
            status_msg = "connected"
            save_connection_from_state(password)
            time.sleep(1)
            run_scrcpy()
            return
    else:
        out, err, code = run_adb(["devices"])
        for line in out.split("\n")[1:]:
            line = line.strip()
            if line and "device" in line and "offline" not in line:
                serial = line.split("\t")[0]
                if "." not in serial:
                    device_serial = serial
                    log_msg(f"[+] USB device detected: {device_serial}")
                    break

    if device_serial and "." not in device_serial:
        log_msg("[*] USB device found. Using USB-assisted wireless mode...")
        status_msg = "pairing"

        out, err, code = run_adb(["-s", device_serial, "shell", "ip", "route"])
        ip_match = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", out)
        if not ip_match:
            out2, _, _ = run_adb(["-s", device_serial, "shell", "ifconfig", "wlan0"])
            ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out2)
        if not ip_match:
            out3, _, _ = run_adb(["-s", device_serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"])
            ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out3)

        if ip_match:
            phone_ip = ip_match.group(1)
            log_msg(f"[*] Phone WiFi IP: {phone_ip}")
        else:
            status_msg = "error"
            connect_result = "Could not detect phone IP"
            log_msg("[X] Could not detect phone IP over USB.")
            return

        out, err, code = run_adb(["-s", device_serial, "tcpip", "5555"])
        log_msg(f"[*] tcpip 5555: {out}")
        time.sleep(3)

        run_adb(["disconnect"])
        time.sleep(1)

        out, err, code = run_adb(["connect", f"{phone_ip}:5555"])
        connect_result = out or err
        log_msg(f"[*] adb connect {phone_ip}:5555 -> {connect_result}")

        if "connected" in out.lower() or "already" in out.lower():
            log_msg("[+] Wireless connection established!")
            status_msg = "connected"
            phone_ip = f"{phone_ip}:5555"
            ensure_single_device(phone_ip)
            save_connection_from_state(password)
            time.sleep(1)
            run_scrcpy()
            return

        status_msg = "error"
        return

    if password:
        log_msg("[*] Disconnecting stale devices...")
        run_adb(["disconnect"])
        time.sleep(1)

        log_msg("[*] Waiting for phone via QR pairing...")
        if not do_pair_via_qr(password):
            status_msg = "error"
            connect_result = "Phone not found via mDNS. Try manual pairing."
            log_msg("[X] QR pairing timeout (90s).")
            return

        if not do_adb_pair(password):
            status_msg = "error"
            log_msg("[X] adb pair failed.")
            return

        do_adb_connect()

        if status_msg == "connected":
            log_msg("[+] Wireless connection established!")
            save_connection_from_state(password)
            time.sleep(1)
            run_scrcpy()


def manual_pair_flow(addr, code):
    global phone_ip, pair_result, connect_result, status_msg
    status_msg = "pairing"
    print(f"[*] Manual pairing: {addr} code={code}")

    run_adb(["disconnect"])
    time.sleep(1)

    phone_ip = addr.split(":")[0] if ":" in addr else addr

    out, err, _ = run_adb(["pair", addr, code])
    pair_result = out or err
    print(f"[*] Pair: {pair_result}")
    time.sleep(2)

    out, err, _ = run_adb(["connect", f"{phone_ip}:5555"])
    connect_result = out or err
    print(f"[*] Connect 5555: {connect_result}")

    if "connected" in out.lower() or "already" in out.lower():
        status_msg = "connected"
        phone_ip = f"{phone_ip}:5555"
        ensure_single_device(phone_ip)
        save_connection_from_state(code)
        time.sleep(1)
        run_scrcpy()
        return

    connect_port = ""
    for attempt in range(8):
        mdns_out, _, _ = run_adb(["mdns", "services"])
        for line in mdns_out.split("\n"):
            if "_adb-tls-connect._tcp" in line and phone_ip in line:
                for p in line.strip().split():
                    if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", p):
                        connect_port = p.split(":")[-1]
                        break
        if connect_port:
            break
        time.sleep(1)

    if connect_port:
        out, err, _ = run_adb(["connect", f"{phone_ip}:{connect_port}"])
        connect_result = out or err
        if "connected" in out.lower() or "already" in out.lower():
            status_msg = "connected"
            phone_ip = f"{phone_ip}:{connect_port}"
            ensure_single_device(phone_ip)
            save_connection_from_state(code)
            time.sleep(1)
            run_scrcpy()
            return

    status_msg = "error"

def main():
    global _pair_password, _was_reconnected, _qr_b64, _local_ip, _service_name

    print("=" * 55)
    print("  scrcpy Wireless Phone Mirror")
    print("=" * 55)

    if not os.path.exists(ADB):
        print(f"\n[!] adb.exe not found at: {ADB}")
        print("[!] Make sure this script is in your scrcpy folder.")
        input("\nPress Enter to exit...")
        return

    html_path = SCRIPT_DIR / "scrcpy_ui.html"
    if not html_path.exists():
        print(f"\n[!] scrcpy_ui.html not found at: {html_path}")
        print("[!] Place it next to this script.")
        input("\nPress Enter to exit...")
        return

    try:
        import qrcode
    except ImportError:
        print("\n[!] Required: pip install qrcode[pil] pillow")
        input("\nPress Enter to exit...")
        return

    load_config()
    print("[*] Settings loaded from config.json")

    saved = load_last_connection()
    if saved:
        print(f"[*] Saved device: {saved.get('ip', '')}:{saved.get('port', '')}")
        print(f"[*] Last connected: {saved.get('timestamp', 'unknown')}")

    _service_name = f"scrcpy_{generate_id()}"
    password = generate_password()
    _pair_password = password
    qr_data = f"WIFI:T:ADB;S:{_service_name};P:{password};;"
    _local_ip = get_local_ip()

    img = generate_qr_image(qr_data)
    _qr_b64 = img_to_base64(img)

    port = random.randint(8800, 9900)
    server = HTTPServer(("0.0.0.0", port), StatusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    webbrowser.open(f"http://localhost:{port}")

    print(f"\n[*] Browser: http://localhost:{port}")
    print(f"[*] UI served from: {html_path}")

    if saved:
        print(f"\n[*] Saved device: {saved.get('ip', '')}:{saved.get('port', '')}")
        print(f"[*] Choose in browser: connect to saved or pair new device")
    else:
        print(f"\n  On your phone:")
        print(f"  1. Settings -> Developer Options -> Wireless debugging -> ON")
        print(f"  2. Tap Pair device with QR code -> scan QR in browser")
        print(f"  OR: connect USB cable for auto-assisted mode")

    # Start scanning for QR pairing in background
    time.sleep(2)
    threading.Thread(target=lambda: do_pairing_flow(password), daemon=True).start()

    while True:
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
