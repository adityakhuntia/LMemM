"""LMemM - every tunable, privacy rule and data path in one place."""

import contextlib
import os
import re
from dataclasses import dataclass, replace

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- capture schedule

EVERY = 5               # seconds between captures while you're active on one window
BACKOFF_CAP = 30        # ...doubling up to this while nothing changes and you give no input
BACKOFF_CAP_CHAT = 15   # chats and AI chats: text can arrive with no input from you
SETTLE = 1.0            # debounce: wait this long after the last trigger
MAX_SETTLE = 3.0        # ...but never longer than this after the first one
MIN_GAP = 2.0           # never two captures closer than this (pinned excepted)
POLL = 0.5              # seconds between window/tab title checks
IDLE = 60               # no input for this long -> pause
MAX_QUEUE = 8           # resolver backlog above which timer captures are skipped
MAX_PX = 1600           # a captured screen wider than this is scaled down to it

# ---------------------------------------------------------------- cost control

FAST_CONTINUATION = True    # fast OCR for later frames of the same window; accurate for the first look
THIN_RATIO = 0.5            # fast OCR that finds under this share of the previous frame's lines is redone accurately
THUMB_PX = 480              # kept screenshots are thumbnails with this long edge...
THUMB_QUALITY = 60          # ...at this JPEG quality (~20-30 KB)
SCREENSHOT_DAYS = 7         # a thing's thumbnail is deleted this long after it was taken...
                            # ...unless the thing is pinned or has an open note
SAVE_EVERY = 5              # seconds: write memory files at most this often while running
RETENTION_SWEEP = 3600      # seconds between screenshot-expiry sweeps
RSS_WARN_MB = 800           # warn in the terminal when LMemM itself uses more memory than this
CPU_WARN_PCT = 60           # ...or more than this share of one core over the last 30 s

# ---------------------------------------------------------------- memory

KEEP_TEXT = 15          # newest lines kept per activity category on an item
RESURFACE_COOLDOWN = 600  # seconds: remind about an item's pending edits at most this often

# ---------------------------------------------------------------- privacy: never captured

BROWSERS = {"Google Chrome", "Google Chrome Canary", "Brave Browser", "Microsoft Edge", "Arc", "Safari"}
CHROMIUM = BROWSERS - {"Safari"}
SKIP_APPS = {
    "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop",
    "com.apple.keychainaccess", "com.apple.Passwords", "com.lastpass.LastPass",
    "com.dashlane.dashlanephonefinal", "org.keepassxc.keepassxc", "com.nordpass.macos.NordPass",
}
SKIP_SITES = re.compile(
    r"bank|netbanking|onlinesbi|hdfc|icici|axisbank|kotak|paypal\.|wise\.com|stripe\.com"
    r"|razorpay\.com/(app|dashboard)|paytm|phonepe|zerodha|groww|coinbase|binance"
    r"|accounts\.google\.com|appleid\.apple\.com|/login|/signin|password", re.I)
SKIP_TITLES = re.compile(r"private browsing|incognito|inprivate|password", re.I)
LOCK_APPS = {"loginwindow", "ScreenSaverEngine"}   # frontmost while locked / screensaver


# ---------------------------------------------------------------- data paths

@dataclass(frozen=True)
class Paths:
    data_dir: str                 # screenshots + their capture metadata
    pidfile: str                  # running tracker; .control.json / .status.json beside it

    @property
    def memory_dir(self):
        return os.path.join(self.data_dir, "memory")

    @property
    def items_file(self):         # the one memory file: source of truth + readable view
        return os.path.join(self.memory_dir, "memory.json")

    @property
    def semantic_file(self):
        return os.path.join(self.memory_dir, "semantic.sqlite3")

    @property
    def sessions_dir(self):
        return os.path.join(self.memory_dir, "sessions")

    @property
    def control_file(self):
        return os.path.splitext(self.pidfile)[0] + ".control.json"

    @property
    def status_file(self):
        return os.path.splitext(self.pidfile)[0] + ".status.json"


PATHS = Paths(data_dir=os.path.join(ROOT, "data"), pidfile=os.path.join(ROOT, ".lmemm.pid"))


@contextlib.contextmanager
def use_paths(data_dir, pidfile=None):
    """Point every module at another data directory (tests, replays)."""
    global PATHS
    old = PATHS
    PATHS = replace(old, data_dir=str(data_dir),
                    pidfile=str(pidfile) if pidfile else os.path.join(str(data_dir), ".lmemm.pid"))
    try:
        yield PATHS
    finally:
        PATHS = old


def paths():
    return PATHS
