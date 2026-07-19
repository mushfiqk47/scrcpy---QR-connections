import os
import time
import socket
import random
import threading
import webbrowser
from http.server import HTTPServer

from scrcpy_helper import state
from scrcpy_helper import config
from scrcpy_helper import adb
from scrcpy_helper import connection

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def generate_qr_image(data):
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def img_to_base64(img):
    import io
    import base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def generate_id(length=14):
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_password(length=21):
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def main():
    print("=" * 55)
    print("  scrcpy Wireless Phone Mirror")
    print("=" * 55)

    if not os.path.exists(state.ADB):
        print(f"\n[!] adb.exe not found at: {state.ADB}")
        print("[!] Make sure this script is in your scrcpy folder.")
        input("\nPress Enter to exit...")
        return

    html_path = state.SCRIPT_DIR / "scrcpy_ui.html"
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

    config.load_config()
    print("[*] Settings loaded from config.json")

    saved = config.load_last_connection()
    if saved:
        print(f"[*] Saved device: {saved.get('ip', '')}:{saved.get('port', '')}")
        print(f"[*] Last connected: {saved.get('timestamp', 'unknown')}")

    state._service_name = f"scrcpy_{generate_id()}"
    password = generate_password()
    state._pair_password = password
    qr_data = f"WIFI:T:ADB;S:{state._service_name};P:{password};;"
    state._local_ip = get_local_ip()

    img = generate_qr_image(qr_data)
    state._qr_b64 = img_to_base64(img)

    from scrcpy_helper.server import StatusHandler
    port = random.randint(8800, 9900)
    server = HTTPServer(("0.0.0.0", port), StatusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    webbrowser.open(f"http://localhost:{port}")

    print(f"\n[*] Browser: http://localhost:{port}")
    print(f"[*] UI served from: {html_path}")

    if saved:
        print(f"\n[*] Saved device: {saved.get('ip', '')}:{saved.get('port', '')}")
        print(f"[*] Auto-connecting...")
    else:
        print(f"\n  On your phone:")
        print(f"  1. Settings -> Developer Options -> Wireless debugging -> ON")
        print(f"  2. Tap Pair device with QR code -> scan QR in browser")
        print(f"  OR: connect USB cable for auto-assisted mode")

    time.sleep(2)
    if saved:
        threading.Thread(target=connection.try_auto_reconnect_then_mirror, daemon=True).start()
    else:
        threading.Thread(target=lambda: connection.do_pairing_flow(state._pair_password), daemon=True).start()

    threading.Thread(target=connection.device_monitor_loop, daemon=True).start()

    while True:
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
