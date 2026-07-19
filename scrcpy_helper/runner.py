import os
import subprocess
import threading
import time
from . import state

def get_scrcpy_cmd():
    cmd = [state.SCRCPY]
    if state.phone_ip:
        cmd += ["-s", state.phone_ip]
    elif state.device_serial:
        cmd += ["-s", state.device_serial]
        
    cfg = state.app_config
    if cfg.get("video_source") == "camera":
        cmd += ["--video-source", "camera"]
        if cfg.get("camera_id"):
            cmd += ["--camera-id", str(cfg["camera_id"])]
        if cfg.get("camera_facing") and cfg["camera_facing"] != "any":
            cmd += ["--camera-facing", cfg["camera_facing"]]
        if cfg.get("camera_size"):
            cmd += ["--camera-size", cfg["camera_size"]]
        if cfg.get("camera_fps"):
            cmd += ["--camera-fps", str(cfg["camera_fps"])]
        if cfg.get("camera_torch"):
            cmd += ["--camera-torch"]
        if cfg.get("camera_high_speed"):
            cmd += ["--camera-high-speed"]
        if cfg.get("camera_zoom"):
            cmd += ["--camera-zoom", str(cfg["camera_zoom"])]
        if cfg.get("camera_ar"):
            cmd += ["--camera-ar", cfg["camera_ar"]]

    if cfg.get("max_size"):
        cmd += ["--max-size", str(cfg["max_size"])]
    if cfg.get("bit_rate"):
        cmd += ["--video-bit-rate", cfg["bit_rate"]]
    if cfg.get("max_fps"):
        cmd += ["--max-fps", str(cfg["max_fps"])]
    
    # Only send non-default codec
    vc = cfg.get("video_codec", "")
    if vc and vc != "h264":
        cmd += ["--video-codec", vc]
    if cfg.get("video_buffer"):
        cmd += ["--video-buffer", str(cfg["video_buffer"])]
        
    if not cfg.get("audio"):
        cmd += ["--no-audio"]
    else:
        # Only send non-default audio source
        asrc = cfg.get("audio_source", "")
        if asrc and asrc != "output":
            cmd += ["--audio-source", asrc]
            
        # audio_dup only valid with playback source
        if cfg.get("audio_dup") and asrc == "playback":
            cmd += ["--audio-dup"]
            
        # Only send non-default audio codec
        ac = cfg.get("audio_codec", "")
        # MP4 recording audio codec override for compatibility (Opus in MP4 often fails/is unsupported)
        rec_fmt = cfg.get("record_format", "")
        if not rec_fmt and cfg.get("record_path"):
            ext = os.path.splitext(cfg["record_path"])[1].lower()
            if ext == ".mp4":
                rec_fmt = "mp4"
        if not rec_fmt and cfg.get("record"):
            rec_fmt = "mp4" # default is mp4
        
        if cfg.get("record") and rec_fmt == "mp4" and (not ac or ac == "opus"):
            ac = "aac"
            state.log_msg("[*] Overriding audio codec to AAC for MP4 recording compatibility")

        if ac and ac != "opus":
            cmd += ["--audio-codec", ac]
        if cfg.get("audio_bit_rate"):
            cmd += ["--audio-bit-rate", cfg["audio_bit_rate"]]
        if cfg.get("audio_buffer"):
            cmd += ["--audio-buffer", str(cfg["audio_buffer"])]

    if cfg.get("turn_screen_off"):
        cmd += ["--turn-screen-off"]
    if cfg.get("stay_awake"):
        cmd += ["--stay-awake"]
    if cfg.get("keep_active"):
        cmd += ["--keep-active"]
        
    if cfg.get("record") and cfg.get("record_path"):
        cmd += ["--record", cfg["record_path"]]
    elif cfg.get("record"):
        ts = time.strftime("%Y%m%d_%H%M%S")
        fmt = cfg.get("record_format", "") or "mp4"
        cmd += ["--record", f"scrcpy_recording_{ts}.{fmt}"]
        
    # Only send record-format and record-orientation when recording
    if cfg.get("record"):
        if cfg.get("record_format"):
            cmd += ["--record-format", cfg["record_format"]]
        if cfg.get("record_orientation") and cfg["record_orientation"] != "0":
            cmd += ["--record-orientation", cfg["record_orientation"]]
            
    if cfg.get("crop"):
        cmd += ["--crop", cfg["crop"]]
        
    # Orientation flags
    if cfg.get("display_orientation") and cfg["display_orientation"] != "0":
        cmd += ["--display-orientation", cfg["display_orientation"]]
    if cfg.get("capture_orientation") and cfg["capture_orientation"] != "0":
        val = cfg["capture_orientation"]
        if cfg.get("capture_orientation_lock"):
            val = "@" + val
        cmd += ["--capture-orientation", val]
        
    if cfg.get("fullscreen"):
        cmd += ["--fullscreen"]
    if cfg.get("always_on_top"):
        cmd += ["--always-on-top"]
    if cfg.get("window_title"):
        cmd += ["--window-title", cfg["window_title"]]
    if cfg.get("no_control"):
        cmd += ["--no-control"]
    if cfg.get("window_borderless"):
        cmd += ["--window-borderless"]
    if cfg.get("show_touches"):
        cmd += ["--show-touches"]
    if cfg.get("time_limit"):
        cmd += ["--time-limit", str(cfg["time_limit"])]
    if cfg.get("screen_off_timeout"):
        cmd += ["--screen-off-timeout", str(cfg["screen_off_timeout"])]
    return cmd

def run_scrcpy():
    with state.scrcpy_lock:
        if state.scrcpy_process and state.scrcpy_process.poll() is None:
            state.log_msg("[*] Stopping running scrcpy instance for configuration update...")
            state.scrcpy_process.terminate()
            try:
                state.scrcpy_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                state.scrcpy_process.kill()
        
        cmd = get_scrcpy_cmd()
        state.log_msg(f"[*] Starting scrcpy: {' '.join(cmd[1:])}")
        try:
            state.scrcpy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            threading.Thread(target=state._read_stream, args=(state.scrcpy_process.stdout, "scrcpy"), daemon=True).start()
            threading.Thread(target=state._read_stream, args=(state.scrcpy_process.stderr, "scrcpy"), daemon=True).start()
        except Exception as e:
            state.log_msg(f"[X] Failed to launch scrcpy: {e}")
