# 📱 scrcpy Wireless Helper (Web UI + System Tray)

An interactive, web-based control panel and system tray utility that simplifies wireless pairing, configuration, and management for **scrcpy** (Android Screen Mirroring). 

No more command-line arguments or manual configuration files. Drop these helper files in, run it, and control **everything from the Web UI**!

---

## 🚀 How to use this with ANY downloaded scrcpy folder

You can drop these helper files into any fresh copy of `scrcpy` downloaded from the internet to instantly add the web control interface.

### Step 1: Download scrcpy
1. Download the official, compiled version of scrcpy for Windows from the [Official scrcpy GitHub Releases Page](https://github.com/Genymobile/scrcpy/releases).
2. Extract the downloaded `.zip` folder to any directory of your choice on your computer.

### Step 2: Copy the Helper Files
Copy the following files from this repository and paste them directly into your extracted `scrcpy` folder (where `adb.exe` and `scrcpy.exe` are located):
*   `scrcpyqr.bat`
*   `scrcpy_qr_pair.py`
*   `scrcpy_ui.html`

### Step 3: Run the Helper
1. Make sure you have **Python 3** installed on your system.
2. Double-click the **`scrcpyqr.bat`** file.
   * *This batch file will automatically verify Python and install the required library packages (`qrcode[pil]` and `pillow`) if they are missing.*
3. A web browser window will automatically open to the control panel at `http://localhost:<port>`.

---

## 🎮 Controlling Everything from the Web UI

Once the helper is running, you can manage your phone mirroring completely through the web page:

### 1. Connect Your Phone
*   **Option A: Wireless QR Code Pairing (Android 11+)**
    1. Ensure your phone and PC are connected to the **same Wi-Fi network**.
    2. Go to **Settings -> Developer Options -> Wireless debugging** on your phone.
    3. Tap **Pair device with QR code**.
    4. Scan the QR code displayed in the web browser interface.
    5. The server will pair, connect, and launch the `scrcpy` mirror window automatically.
*   **Option B: One-Click USB to Wireless Handover (Simplest Method)**
    1. Turn on **USB Debugging** in your phone's Developer Options.
    2. Connect your phone to your PC via a USB cable.
    3. Click the USB connect button on the UI (or let the auto-handover configure it). The assistant detects the USB connection, configures wireless debugging over port `5555`, and connects.
    4. You can now unplug the USB cable and mirror wirelessly.
*   **Option C: Manual Pairing Fallback**
    * Tap **Pair device with pairing code** under Wireless Debugging, and enter the displayed IP:Port and 6-digit PIN in the **Manual pair** panel on the web page.

### 2. Live Performance Presets & Settings
No need to remember scrcpy CLI command flags. Change options on the fly:
*   **Performance Presets**: Quick toggle buttons for **Gaming** (1080p, 8 Mbps, 60 FPS), **Balanced** (720p, 4 Mbps, 60 FPS), and **Eco** (480p, 2 Mbps, 30 FPS).
*   **Custom Parameters**: Set custom max resolution, bitrates, frame rates, toggle audio, fullscreen, keep-awake, and window orientation lock directly from the UI inputs.
*   **Hot-Reload Settings**: Saving settings instantly re-opens or updates your active scrcpy window.

### 3. Monitoring & Diagnostics
*   **Live Console Log Drawer**: Expand the "Live Console Logs" drawer at the bottom of the page to inspect standard output streams and debugging details from the running mirror.
*   **Active Target Select**: Select which device to target using the dynamic dropdown header if you have multiple devices connected.
*   **Reset ADB Service**: A quick button to restart the ADB server instantly if network ports hang.

---

## 📥 System Tray Control
When running:
*   The script runs silently in the background, keeping your taskbar clean.
*   Right-click the system tray icon to **Show Window** (unhide the python server terminal) or **Exit** (closes the server and kills active scrcpy connections).
