# scrcpy Wireless Helper (QR Code + Presets + Diagnostics)

An interactive, web-based control panel that simplifies wireless pairing and configuration for **scrcpy** (Android Screen Mirroring). 

Features include **QR Code pairing via mDNS**, **USB-assisted wireless handover**, **live console logs streaming**, **performance presets**, and **real-time settings hot-reloading**.

---

## 🚀 How to use this with ANY downloaded scrcpy folder

You can drop these helper files into any fresh copy of `scrcpy` downloaded from the internet to instantly add the web control interface.

### Step 1: Download scrcpy
1. Download the official, compiled version of scrcpy for Windows from the [Official scrcpy GitHub Releases Page](https://github.com/Genymobile/scrcpy/releases).
2. Extract the downloaded `.zip` folder to a directory of your choice on your computer.

### Step 2: Copy the Helper Files
Copy the following files from this repository and paste them directly into your extracted `scrcpy` folder (where `adb.exe` and `scrcpy.exe` are located):
*   `scrcpy_qr_pair.py`
*   `scrcpy_ui.html`
*   `scrcpy_qr_pair.bat`
*   `scrcpy-noconsole.vbs`

### Step 3: Run the Helper
1. Make sure you have **Python 3** installed on your system.
2. Double-click the **`scrcpy_qr_pair.bat`** file.
   * *This batch file will automatically verify Python and install the required library packages (`qrcode[pil]` and `pillow`) if they are missing.*
3. A command prompt window will launch the background server and automatically open a web page in your default browser at `http://localhost:<random_port>`.

---

## 📱 How to Pair & Connect Your Phone

### Option A: Wireless QR Code Pairing (Android 11+)
1. Ensure your phone and PC are connected to the **same Wi-Fi network**.
2. Go to **Settings -> Developer Options** on your phone.
3. Toggle on **Wireless debugging**, tap it to enter its settings, and select **Pair device with QR code**.
4. Scan the QR code displayed in the web browser interface.
5. Once paired, the server will connect to your phone and launch the `scrcpy` mirror window automatically.

### Option B: One-Click USB to Wireless Handover (Simplest Method)
1. Turn on **USB Debugging** in your phone's Developer Options.
2. Connect your phone to your PC via a USB cable.
3. Open the web interface. The assistant will detect the USB connection and automatically configure your phone to run wireless debugging over port `5555`.
4. Once completed, you can unplug the USB cable and mirror wirelessly.

### Option C: Manual pairing fallback
* If QR/USB fails, select **Pair device with pairing code** under Wireless Debugging, and enter the displayed IP:Port and 6-digit PIN in the **Manual pair** panel on the web page.

---

## 🎨 Features & Controls

*   **Live Console Log Drawer:** Toggle the "Live Console Logs" drawer at the bottom of the page to inspect standard output streams from the running mirror.
*   **Settings Auto-Save:** Changes made to parameters (resolution, bitrate, FPS, view-only, stay-awake, orientation lock) are saved automatically and hot-reloaded into the active scrcpy window in real-time.
*   **Performance Presets:** Quick preset toggles let you swap between:
    *   `Gaming` (1080p, 8 Mbps, 60 FPS)
    *   `Balanced` (720p, 4 Mbps, 60 FPS)
    *   `Eco` (480p, 2 Mbps, 30 FPS)
*   **Active Target Select:** Select which phone to target using the dynamic dropdown header if you have multiple devices connected to your local network.
*   **Reset ADB Service:** A quick button to reset ADB services instantly in case of network port hangs.
