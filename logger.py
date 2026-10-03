#!/usr/bin/env python3
"""
LMemM - Step 1: the capture logger.

Every INTERVAL seconds, grab:
  - a screenshot of the screen
  - the cursor position
  - the frontmost app + window title + browser URL

Writes <timestamp>.jpg and <timestamp>.json into ./data/.
No AI, no judging. Just raw frames to look at afterwards.

Run:  python3 logger.py
Stop: Ctrl-C
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    from AppKit import NSEvent, NSScreen
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install pyobjc-framework-Cocoa")

try:
    from Quartz import CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess
except ImportError:
    CGPreflightScreenCaptureAccess = None
    CGRequestScreenCaptureAccess = None


# ---------------------------------------------------------------- config

INTERVAL = int(os.environ.get("LMEMM_INTERVAL", 60))   # seconds between frames
SCALE_PCT = 50         # downscale screenshots to this % (saves a lot of disk)
JPEG_QUALITY = 60      # 1-100
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ---------------------------------------------------------------- helpers

def osa(script, timeout=3):
    """Run an AppleScript snippet, return stdout or None."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        out = r.stdout.strip()
        return out or None
    except Exception:
        return None


def active_app():
    return osa(
        'tell application "System Events" to get name of '
        'first process whose frontmost is true'
    )


def window_title():
    return osa(
        'tell application "System Events" to tell '
        '(first process whose frontmost is true) to get name of front window'
    )


def browser_url(app):
    """Front tab URL + title, if the frontmost app is a known browser."""
    if not app:
        return None, None
    browsers = {
        "Google Chrome", "Google Chrome Canary", "Brave Browser",
        "Microsoft Edge", "Arc", "Safari",
    }
    if app not in browsers:
        return None, None
    if app == "Safari":
        url = osa('tell application "Safari" to get URL of front document')
        title = osa('tell application "Safari" to get name of front document')
    else:
        url = osa(f'tell application "{app}" to get URL of active tab of front window')
        title = osa(f'tell application "{app}" to get title of active tab of front window')
    return url, title


def cursor():
    """Cursor position in top-left-origin screen coordinates."""
    p = NSEvent.mouseLocation()                       # bottom-left origin
    h = NSScreen.mainScreen().frame().size.height
    return {"x": int(p.x), "y": int(h - p.y)}


def screen_size():
    f = NSScreen.mainScreen().frame().size
    return {"w": int(f.width), "h": int(f.height)}


def capture(path):
    """Silent screenshot of the main display, no cursor, no window shadow."""
    subprocess.run(
        ["screencapture", "-x", "-o", "-t", "jpg", "-m", path],
        check=False,
    )
    # downscale in place with sips (ships with macOS)
    if SCALE_PCT != 100 and os.path.exists(path):
        subprocess.run(
            ["sips", "-Z", str(int(2560 * SCALE_PCT / 100)), path],
            capture_output=True, check=False,
        )


# ---------------------------------------------------------------- main


def check_screen_permission():
    """
    Without Screen Recording permission, macOS does NOT error - screencapture
    silently returns the desktop wallpaper with every window stripped out.
    That looks like working code producing useless data, so fail loudly here.
    """
    if CGPreflightScreenCaptureAccess is None:
        print("! Cannot verify Screen Recording permission "
              "(pip3 install pyobjc-framework-Quartz to enable this check).")
        print("  If your frames show only the wallpaper, that is the cause.\n")
        return

    if CGPreflightScreenCaptureAccess():
        return

    term = os.environ.get("TERM_PROGRAM", "your terminal")
    print("=" * 68)
    print("  SCREEN RECORDING PERMISSION NOT GRANTED")
    print("=" * 68)
    print("  Without it, every screenshot will be just your wallpaper.")
    print()
    print(f"  1. System Settings -> Privacy & Security -> Screen Recording")
    print(f"  2. Enable it for: {term}")
    print("  3. QUIT that app completely (Cmd-Q) and reopen it")
    print("  4. Run this script again")
    print()
    print("  Requesting the permission now - approve the dialog, then")
    print("  quit and reopen your terminal.")
    print("=" * 68)
    if CGRequestScreenCaptureAccess is not None:
        CGRequestScreenCaptureAccess()
    sys.exit(1)


def capture_frame():
    """Take one frame: write <ts>.jpg + <ts>.json into DATA_DIR, return the meta path."""
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    img = os.path.join(DATA_DIR, ts + ".jpg")

    capture(img)

    app = active_app()
    url, tab_title = browser_url(app)
    meta = {
        "ts": ts,
        "iso": datetime.now().isoformat(timespec="seconds"),
        "app": app,
        "window": window_title(),
        "url": url,
        "tab_title": tab_title,
        "cursor": cursor(),
        "screen": screen_size(),
        "image": os.path.basename(img),
        "bytes": os.path.getsize(img) if os.path.exists(img) else 0,
    }
    path = os.path.join(DATA_DIR, ts + ".json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    return path, meta


def main():
    check_screen_permission()
    print(f"LMemM logger -> {DATA_DIR}")
    print(f"interval={INTERVAL}s  scale={SCALE_PCT}%  (Ctrl-C to stop)\n")

    n = 0
    while True:
        started = time.time()
        _, meta = capture_frame()
        ts, app = meta["ts"], meta["app"]
        n += 1
        label = meta["tab_title"] or meta["window"] or "-"
        print(f"[{n:4d}] {ts}  {str(app or '?'):22.22}  {label:.60}")

        time.sleep(max(0, INTERVAL - (time.time() - started)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
