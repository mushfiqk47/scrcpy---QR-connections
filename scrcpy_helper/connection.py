import time
import threading
import re
from . import state
from . import config
from . import adb
from . import runner

def try_auto_reconnect():
    saved = config.load_last_connection()
    if not saved or not saved.get("ip"):
        return False

    ip = saved["ip"]
    port = saved.get("port", "")
    password = saved.get("password", "")
    device_ip = ip.split(":")[0] if ":" in ip else ip

    print(f"[*] Saved device: {ip}:{port} ({saved.get('timestamp', 'unknown')})")
    print("[*] Trying auto-reconnect...")
    state.status_msg = "reconnecting"

    # Stage 1: direct connect
    if port:
        adb.run_adb(["disconnect"])
        time.sleep(1)
        out, _, _ = adb.run_adb(["connect", f"{ip}:{port}"])
        if ("connected" in out.lower() or "already" in out.lower()) and adb.is_device_online(f"{ip}:{port}"):
            return _apply_reconnect(out, ip, port, device_ip, password, saved)

    # Stage 2: scan mDNS for connect service
    print("[*] Direct connect failed. Scanning mDNS for connect...")
    addr = adb.scan_mdns("connect", target_ip=device_ip, timeout=10)
    if not addr:
        addr = adb.scan_mdns("connect", target_ip=None, timeout=5)
    if addr:
        new_ip, new_port = addr.split(":")[0], addr.split(":")[-1]
        adb.run_adb(["disconnect"])
        time.sleep(1)
        out, _, _ = adb.run_adb(["connect", addr])
        if ("connected" in out.lower() or "already" in out.lower()) and adb.is_device_online(addr):
            return _apply_reconnect(out, new_ip, new_port, device_ip, password, saved)

    # Stage 3: re-pair via saved password
    if password:
        print("[*] mDNS connect failed. Trying re-pair...")
        pair_addr = adb.scan_mdns("pairing", target_ip=device_ip, timeout=10)
        if not pair_addr:
            pair_addr = adb.scan_mdns("pairing", target_ip=None, timeout=5)
        if pair_addr:
            pair_ip = pair_addr.split(":")[0]
            out, _, _ = adb.run_adb(["pair", pair_addr, password])
            if "success" in out.lower():
                time.sleep(2)
                connect_addr = adb.scan_mdns("connect", target_ip=device_ip, timeout=8)
                if not connect_addr:
                    connect_addr = adb.scan_mdns("connect", target_ip=None, timeout=5)
                if connect_addr:
                    c_ip, c_port = connect_addr.split(":")[0], connect_addr.split(":")[-1]
                    adb.run_adb(["disconnect"])
                    time.sleep(1)
                    out2, _, _ = adb.run_adb(["connect", connect_addr])
                    if ("connected" in out2.lower() or "already" in out2.lower()) and adb.is_device_online(connect_addr):
                        return _apply_reconnect(out2, c_ip, c_port, device_ip, password, saved)

    print("[!] Auto-reconnect failed.")
    state.status_msg = "waiting"
    return False

def _apply_reconnect(out, new_ip, new_port, device_ip, password, saved):
    state.connect_result = out
    state.phone_ip = f"{new_ip}:{new_port}"
    state.status_msg = "connected"
    adb.ensure_single_device(device_ip)
    config.save_last_connection(new_ip, new_port, state.phone_ip, password)
    print(f"[+] Auto-reconnect OK: {state.phone_ip}")
    return True

def try_auto_reconnect_then_mirror():
    if try_auto_reconnect():
        time.sleep(1)
        runner.run_scrcpy()
    else:
        do_pairing_flow(state._pair_password)

def do_pair_via_qr():
    state.status_msg = "waiting"
    print("[*] Waiting for phone via QR pairing...")
    result = adb.scan_mdns("pairing", timeout=90)
    if result:
        state.phone_ip = result
        state.status_msg = "pairing"
        print(f"\n[+] Phone found at {state.phone_ip}")
        return True
    return False

def do_adb_pair(password):
    if not state.phone_ip:
        return False
    print(f"[*] Running: adb pair {state.phone_ip} [password]")
    out, err, code = adb.run_adb(["pair", state.phone_ip, password])
    state.pair_result = out or err
    print(f"[*] Pair result: {state.pair_result}")
    if "error" in err.lower() and code != 0:
        return False
    if "success" in out.lower() or "pair" in out.lower():
        return True
    return code == 0

def do_adb_connect():
    device_ip = state.phone_ip.split(":")[0] if ":" in state.phone_ip else state.phone_ip
    time.sleep(2)

    connect_addr = adb.scan_mdns("connect", target_ip=device_ip, timeout=8)
    connect_port = connect_addr.split(":")[-1] if connect_addr else ""

    adb.run_adb(["disconnect"])
    time.sleep(1)

    targets = []
    if connect_port:
        targets.append(f"{device_ip}:{connect_port}")
    targets += [f"{device_ip}:5555", device_ip]

    for target in targets:
        out, err, _ = adb.run_adb(["connect", target])
        state.connect_result = out or err
        print(f"[*] adb connect {target} -> {state.connect_result}")
        if "connected" in out.lower() or "already" in out.lower():
            state.status_msg = "connected"
            state.phone_ip = target
            adb.ensure_single_device(device_ip)
            return True
    state.status_msg = "error"
    return False

def save_connection_from_state(password):
    if not state.phone_ip:
        return
    device_ip = state.phone_ip.split(":")[0] if ":" in state.phone_ip else state.phone_ip
    port = state.phone_ip.split(":")[1] if ":" in state.phone_ip else "5555"
    serial = adb.get_connected_serial(device_ip)
    config.save_last_connection(device_ip, port, serial, password)

def do_pairing_flow(password="", target_serial=""):
    if state.status_msg == "connected":
        return

    state.status_msg = "scanning"
    state.log_msg("[*] Starting connection flow...")

    if target_serial:
        state.device_serial = target_serial
        state.log_msg(f"[*] Target device specified: {state.device_serial}")
        if "." in state.device_serial:
            state.log_msg(f"[+] Device {state.device_serial} selected. Starting scrcpy...")
            state.phone_ip = state.device_serial
            state.status_msg = "connected"
            save_connection_from_state(password)
            time.sleep(1)
            runner.run_scrcpy()
            return
    else:
        out, err, code = adb.run_adb(["devices"])
        for line in out.split("\n")[1:]:
            line = line.strip()
            if line and "device" in line and "offline" not in line:
                serial = line.split("\t")[0]
                if "." not in serial:
                    state.device_serial = serial
                    state.log_msg(f"[+] USB device detected: {state.device_serial}")
                    break

    if state.device_serial and "." not in state.device_serial:
        if state.status_msg == "connected":
            return
        state.log_msg("[*] USB device found. Using USB-assisted wireless mode...")
        state.status_msg = "pairing"

        out, err, code = adb.run_adb(["-s", state.device_serial, "shell", "ip", "route"])
        ip_match = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", out)
        if not ip_match:
            out2, _, _ = adb.run_adb(["-s", state.device_serial, "shell", "ifconfig", "wlan0"])
            ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out2)
        if not ip_match:
            out3, _, _ = adb.run_adb(["-s", state.device_serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"])
            ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out3)

        if ip_match:
            state.phone_ip = ip_match.group(1)
            state.log_msg(f"[*] Phone WiFi IP: {state.phone_ip}")
        else:
            if state.status_msg == "connected":
                return
            state.status_msg = "error"
            state.connect_result = "Could not detect phone IP"
            state.log_msg("[X] Could not detect phone IP over USB.")
            return

        if state.status_msg == "connected":
            return

        out, err, code = adb.run_adb(["-s", state.device_serial, "tcpip", "5555"])
        state.log_msg(f"[*] tcpip 5555: {out}")
        time.sleep(3)

        if state.status_msg == "connected":
            return

        adb.run_adb(["disconnect"])
        time.sleep(1)

        if state.status_msg == "connected":
            return

        out, err, code = adb.run_adb(["connect", f"{state.phone_ip}:5555"])
        state.connect_result = out or err
        state.log_msg(f"[*] adb connect {state.phone_ip}:5555 -> {state.connect_result}")

        if "connected" in out.lower() or "already" in out.lower():
            state.log_msg("[+] Wireless connection established!")
            state.status_msg = "connected"
            state.phone_ip = f"{state.phone_ip}:5555"
            adb.ensure_single_device(state.phone_ip)
            save_connection_from_state(password)
            time.sleep(1)
            runner.run_scrcpy()
            return

        if state.status_msg == "connected":
            return
        state.status_msg = "error"
        return

    if password:
        if state.status_msg == "connected":
            return

        state.log_msg("[*] Disconnecting stale devices...")
        adb.run_adb(["disconnect"])
        time.sleep(1)

        if state.status_msg == "connected":
            return

        if not do_pair_via_qr():
            if state.status_msg == "connected":
                return
            state.status_msg = "error"
            state.connect_result = "Phone not found via mDNS. Try manual pairing."
            state.log_msg("[X] QR pairing timeout (90s).")
            return

        if state.status_msg == "connected":
            return

        if not do_adb_pair(password):
            if state.status_msg == "connected":
                return
            state.status_msg = "error"
            state.log_msg("[X] adb pair failed.")
            return

        if state.status_msg == "connected":
            return

        do_adb_connect()

        if state.status_msg == "connected":
            state.log_msg("[+] Wireless connection established!")
            save_connection_from_state(password)
            time.sleep(1)
            runner.run_scrcpy()


def manual_pair_flow(addr, code):
    state.status_msg = "pairing"
    print(f"[*] Manual pairing: {addr} code={code}")

    adb.run_adb(["disconnect"])
    time.sleep(1)

    state.phone_ip = addr.split(":")[0] if ":" in addr else addr

    out, err, _ = adb.run_adb(["pair", addr, code])
    state.pair_result = out or err
    print(f"[*] Pair: {state.pair_result}")
    time.sleep(2)

    out, err, _ = adb.run_adb(["connect", f"{state.phone_ip}:5555"])
    state.connect_result = out or err
    print(f"[*] Connect 5555: {state.connect_result}")

    if ("connected" in out.lower() or "already" in out.lower()) and adb.is_device_online(f"{state.phone_ip}:5555"):
        state.status_msg = "connected"
        state.phone_ip = f"{state.phone_ip}:5555"
        adb.ensure_single_device(state.phone_ip)
        save_connection_from_state(code)
        time.sleep(1)
        runner.run_scrcpy()
        return

    connect_addr = adb.scan_mdns("connect", target_ip=state.phone_ip, timeout=8)
    if connect_addr:
        c_ip, c_port = connect_addr.split(":")[0], connect_addr.split(":")[-1]
        out, err, _ = adb.run_adb(["connect", connect_addr])
        state.connect_result = out or err
        if ("connected" in out.lower() or "already" in out.lower()) and adb.is_device_online(connect_addr):
            state.status_msg = "connected"
            state.phone_ip = f"{c_ip}:{c_port}"
            adb.ensure_single_device(state.phone_ip)
            save_connection_from_state(code)
            time.sleep(1)
            runner.run_scrcpy()
            return

    state.status_msg = "error"

def _do_reconnect_flow():
    state.status_msg = "reconnecting"
    reconnected = try_auto_reconnect()
    if reconnected:
        print("[+] Reconnect to saved device successful!")
        time.sleep(1)
        runner.run_scrcpy()
    else:
        state.status_msg = "error"
        print("[!] Reconnect to saved device failed.")

def device_monitor_loop():
    time.sleep(6)
    last_seen_devices = set()
    while True:
        try:
            time.sleep(3)
            
            scrcpy_running = False
            with state.scrcpy_lock:
                if state.scrcpy_process and state.scrcpy_process.poll() is None:
                    scrcpy_running = True
            
            if not scrcpy_running and state.status_msg == "connected":
                state.status_msg = "waiting"
                state.log_msg("[*] scrcpy mirror window closed.")
            
            out, _, _ = adb.run_adb(["devices"], timeout=5)
            current_devices = []
            for line in out.split("\n")[1:]:
                line = line.strip()
                if not line or "offline" in line or "unauthorized" in line:
                    continue
                if "device" in line:
                    parts = line.split()
                    if parts:
                        current_devices.append(parts[0])
            
            newly_appeared = [d for d in current_devices if d not in last_seen_devices]
            last_seen_devices = set(current_devices)
            
            if not scrcpy_running and state.status_msg in ("waiting", "error"):
                if newly_appeared:
                    target = newly_appeared[0]
                    state.log_msg(f"[*] New device detected: {target}. Auto-connecting...")
                    state.status_msg = "scanning"
                    threading.Thread(target=do_pairing_flow, args=(state._pair_password, target), daemon=True).start()
        except Exception as e:
            state.log_msg(f"[X] Error in device monitor loop: {e}")
