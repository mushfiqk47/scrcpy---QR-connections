# 📱 scrcpy Wireless Mirror Helper

A simple, user-friendly Web Interface for **scrcpy** to pair, connect, and mirror your Android device wirelessly without typing commands!

---

## ⚙️ Installation & Setup

1. **Download scrcpy:** Go to the official [scrcpy Releases Page](https://github.com/Genymobile/scrcpy/releases) and download the compiled Windows `.zip` (e.g., `scrcpy-win64-v4.1.zip`).
2. **Extract:** Extract the downloaded `.zip` file to any folder on your computer.
3. **Copy Helper Files:** Place the following files from this repository directly inside the extracted folder (next to `scrcpy.exe` and `adb.exe`):
   * `scrcpyqr.bat`
   * `main.py`
   * `scrcpy_ui.html`
   * `scrcpy_helper/` (the entire folder)

---

## ⚡ Quick Start

1. **Connect** your phone and computer to the same Wi-Fi network.
2. **Double-click `scrcpyqr.bat`** in this folder.
3. Your browser will open the Web Control Panel automatically.

---

## 🚀 How to Connect

### Option A: Scan QR Code (Wireless Debugging)
1. On your phone, go to **Settings** -> **Developer options** -> enable **Wireless debugging**.
2. Tap **Wireless debugging**, then select **Pair device with QR code**.
3. Scan the QR code shown in the browser.

### Option B: USB Plug-and-Play
1. Enable **USB debugging** on your phone.
2. Plug your phone into your computer via a USB cable.
3. The helper will automatically configure Wi-Fi and connect. You can then unplug the cable!

---

## 🎨 Key Features

* 🎥 **Mirror Display or Camera:** Switch between normal screen mirroring or streaming your device's camera.
* 🎥 **Camera Switcher:** Link to easily switch back to Screen Mirroring directly from the Camera Options.
* 🔴 **One-Click Recording:** Record to MP4 or MKV with automatic audio codec tuning for perfect compatibility.
* ⚙️ **Quick Presets:** Choose from **Gaming** (60 FPS, 1080p), **Balanced**, or **Eco** presets.
* 🔄 **Instant Apply:** Changing settings automatically updates your active mirror screen instantly.
* 🔌 **Zero Subprocess Bloat:** Heavily optimized caching means near-zero background CPU usage.

---

> [!TIP]
> **Need help?** If the connection gets lost, click the **Reset ADB** button in the Web Panel to restart the service instantly.
