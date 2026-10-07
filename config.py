"""LMemM - every tunable, privacy rule and data path in one place."""

import contextlib
import os
import re
from dataclasses import dataclass, replace

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- capture schedule

EVERY = 5               # seconds between captures while nothing else happens
SETTLE = 1.0            # debounce: wait this long after the last trigger
MAX_SETTLE = 3.0        # ...but never longer than this after the first one
MIN_GAP = 2.0           # never two captures closer than this (pinned excepted)
POLL = 0.5              # seconds between window/tab title checks
IDLE = 60               # no input for this long -> pause
MAX_QUEUE = 8           # resolver backlog above which timer captures are skipped
SCALE_PX = 1280         # downscale screenshots to this long edge

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
    def items_file(self):         # readable export
        return os.path.join(self.memory_dir, "memory.json")

    @property
    def index_file(self):         # full internal state (source of truth)
        return os.path.join(self.memory_dir, ".index.json")

    @property
    def pending_file(self):       # readable project view of open notes
        return os.path.join(self.memory_dir, "pending.json")

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
