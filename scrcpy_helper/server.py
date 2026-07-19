from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import json
import os
import time
from . import state
from . import config
from . import adb
from . import connection
from . import runner

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/status":
            self.send_json({
                "status": state.status_msg, 
                "phone_ip": state.phone_ip, 
                "result": f"{state.pair_result} | {state.connect_result}"
            })

        elif path == "/init":
            self.send_json({
                "qr_b64": state._qr_b64,
                "local_ip": state._local_ip,
                "service_name": state._service_name,
                "saved_device": config.LAST_CONN,
                "config": state.app_config,
                "status": state.status_msg,
            })

        elif path == "/settings":
            self.send_json(state.app_config)

        elif path == "/connect":
            qs = parse_qs(urlparse(self.path).query)
            target_serial = qs.get("serial", [""])[0]
            self.send_ok()
            threading.Thread(target=connection.do_pairing_flow, args=(state._pair_password, target_serial), daemon=True).start()

        elif path == "/reconnect":
            self.send_ok()
            threading.Thread(target=connection._do_reconnect_flow, daemon=True).start()

        elif path.startswith("/manual"):
            qs = parse_qs(urlparse(self.path).query)
            addr = qs.get("addr", [""])[0]
            code = qs.get("code", [""])[0]
            self.send_ok()
            threading.Thread(target=connection.manual_pair_flow, args=(addr, code), daemon=True).start()

        elif path == "/forget":
            try:
                if os.path.exists(state.LAST_CONN_PATH):
                    os.remove(state.LAST_CONN_PATH)
                config.load_last_connection()
                self.send_json({"ok": True})
            except Exception as e:
                self.send_json({"ok": False}, 400)

        elif path == "/logs":
            with state.log_lock:
                logs_list = list(state.log_queue)
            self.send_json({"logs": logs_list})

        elif path == "/devices":
            devices_list = []
            out, _, _ = adb.run_adb(["devices"], timeout=5)
            lines = out.split("\n")[1:]
            for line in lines:
                line = line.strip()
                if not line or "device" not in line or "offline" in line:
                    continue
                parts = line.split()
                if parts:
                    serial = parts[0]
                    model = adb.get_device_model(serial)
                    devices_list.append({
                        "serial": serial,
                        "model": model
                    })
            self.send_json({"devices": devices_list})

        elif path == "/reset_adb":
            state.log_msg("[*] Resetting ADB server...")
            adb.run_adb(["kill-server"])
            time.sleep(1)
            adb.run_adb(["start-server"])
            state.log_msg("[+] ADB server restarted successfully")
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
                config.save_config(config_data)
                self.send_json({"ok": True})
                
                is_running = False
                with state.scrcpy_lock:
                    if state.scrcpy_process and state.scrcpy_process.poll() is None:
                        is_running = True
                if is_running:
                    state.log_msg("[*] Setting changes received. Restarting scrcpy to apply settings...")
                    threading.Thread(target=runner.run_scrcpy, daemon=True).start()
            except Exception as e:
                state.log_msg(f"[X] Settings save failed: {e}")
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
        html_path = state.SCRIPT_DIR / "scrcpy_ui.html"
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = "<html><body><h1>scrcpy_ui.html not found</h1><p>Place it next to main.py</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def log_message(self, format, *args):
        pass
