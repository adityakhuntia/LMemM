#!/usr/bin/env python3
"""
LMemM - press a hotkey, say what's on your mind, and it's stored on the memory
entry for whatever you're working on.

    HOTKEY (⌃⌥N)  -> a small note window opens and it's already listening:
                     your words appear as you speak (you can also type)
    Return         -> saved on the current memory entry as one of your notes
    Esc            -> cancelled

The hotkey uses Carbon's RegisterEventHotKey: macOS tells us about that one key
combination only. No keyboard monitoring, no Accessibility permission.

Speech to text is Apple's on-device speech recognizer, run by a tiny helper app
(native/listen/listen.m -> bin/LMemM Listen.app, built with clang on first use). It has
to be its own app: macOS only lets an app with its own microphone/speech usage
strings use the recognizer. It only runs while the note window is open. First
time, macOS asks to allow Microphone and Speech Recognition for "LMemM Listen".
"""

import ctypes
import os
import shutil
import signal
import subprocess
import tempfile
import time
from ctypes import CFUNCTYPE, POINTER, Structure, c_int32, c_uint32, c_void_p

from AppKit import NSApplication

import notecard

# ⌃⌥N  ("note"). kVK_ANSI_N = 45; Carbon modifier bits: control 4096, option 2048
HOTKEY_CODE = 45
HOTKEY_MODS = 4096 | 2048
HOTKEY_LABEL = "⌃⌥N"

_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")


class _EventTypeSpec(Structure):
    _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]


class _EventHotKeyID(Structure):
    _fields_ = [("signature", c_uint32), ("id", c_uint32)]


_HANDLER = CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
_carbon.GetApplicationEventTarget.restype = c_void_p
_carbon.InstallEventHandler.argtypes = [c_void_p, _HANDLER, c_uint32, POINTER(_EventTypeSpec),
                                        c_void_p, c_void_p]
_carbon.InstallEventHandler.restype = c_int32
_carbon.RegisterEventHotKey.argtypes = [c_uint32, c_uint32, _EventHotKeyID, c_void_p, c_uint32,
                                        POINTER(c_void_p)]
_carbon.RegisterEventHotKey.restype = c_int32


def _fourcc(s):
    return int.from_bytes(s.encode(), "big")


_keep = []      # ctypes callbacks must outlive the registration
_hot = {"callback": None, "installed": False}     # one registration for the whole process


def release_hotkey():
    """Stop calling the current callback (the key stays registered; the next register_hotkey()
    just points it somewhere else). First-run setup uses ⌃⌥N, then hands it to the tracker."""
    _hot["callback"] = None


def register_hotkey(callback):
    """Call callback() whenever ⌃⌥N is pressed anywhere. Returns True on success. Safe to call
    again later in the same process (setup, then the tracker): the key is registered once."""
    _hot["callback"] = callback
    if _hot["installed"]:
        return True

    def handler(_call, _event, _data):
        try:
            if _hot["callback"]:
                _hot["callback"]()
        except Exception as e:                      # never let it kill the event loop
            print(f"  ! hotkey: {e}", flush=True)
        return 0
    cb = _HANDLER(handler)
    _keep.append(cb)
    spec = _EventTypeSpec(_fourcc("keyb"), 5)           # kEventClassKeyboard, kEventHotKeyPressed
    target = _carbon.GetApplicationEventTarget()
    if _carbon.InstallEventHandler(target, cb, 1, ctypes.byref(spec), None, None) != 0:
        return False
    ref = c_void_p()
    ok = _carbon.RegisterEventHotKey(HOTKEY_CODE, HOTKEY_MODS, _EventHotKeyID(_fourcc("LMem"), 1),
                                     target, 0, ctypes.byref(ref)) == 0
    _keep.append(ref)
    _hot["installed"] = ok
    return ok


_started = []


def start_app():
    """An invisible app (no Dock icon) so we can receive the hotkey and show the note window.
    Started once per process: first-run setup and the tracker share it."""
    app = NSApplication.sharedApplication()
    if not _started:
        app.setActivationPolicy_(1)                    # accessory
        app.finishLaunching()
        _started.append(True)
    return app


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTEN_APP = os.path.join(HERE, "bin", "LMemM Listen.app")


def ensure_listener():
    """Build the speech helper app once (needs Xcode Command Line Tools' clang)."""
    exe = os.path.join(LISTEN_APP, "Contents", "MacOS", "listen")
    src = os.path.join(HERE, "native", "listen", "listen.m")
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
        return True
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    subprocess.run(["cp", os.path.join(HERE, "native", "listen", "Info.plist"),
                    os.path.join(LISTEN_APP, "Contents", "Info.plist")], check=False)
    r = subprocess.run(["clang", "-fobjc-arc", "-O2", "-framework", "Foundation", "-framework",
                        "Speech", "-framework", "AVFoundation", src, "-o", exe],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ! couldn't build the speech helper:\n{r.stderr[-800:]}", flush=True)
        return False
    subprocess.run(["codesign", "-s", "-", "--force", "--deep", LISTEN_APP], capture_output=True)
    return True


class Listener:
    """Runs LMemM Listen while the note window is open; reads its running transcript."""

    def __init__(self):
        self.out = None
        self.process = None

    def start(self):
        if not ensure_listener():
            return False
        self.out = os.path.join(tempfile.mkdtemp(prefix="lmemm-"), "transcript.txt")
        # `open` makes macOS treat it as its own app (its own permissions); -g keeps
        # it in the background, -n allows a fresh instance each time
        try:
            self.process = subprocess.Popen(["open", "-W", "-n", "-g", LISTEN_APP, "--args", self.out],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.stop(wait=0)
            return False
        return True

    def text(self):
        try:
            with open(self.out, encoding="utf-8") as fh:
                return fh.read().strip()
        except (OSError, TypeError):
            return ""

    def error(self):
        try:
            with open(self.out + ".error", encoding="utf-8") as fh:
                return fh.read().strip()
        except (OSError, TypeError):
            return None

    def stop(self, wait=2.0):
        """Ask it to stop and wait (briefly) for the last words. Returns the final text."""
        if not self.out:
            return ""
        directory = os.path.dirname(self.out)
        try:
            open(self.out + ".stop", "w").close()
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline and not os.path.exists(self.out + ".done"):
                time.sleep(0.05)
            text = self.text()
            if not os.path.exists(self.out + ".done"):
                try:
                    with open(self.out + ".pid") as fh:
                        pid = int(fh.read())
                    if pid > 1:
                        os.kill(pid, signal.SIGTERM)
                except (OSError, ValueError):
                    pass
            return text
        finally:
            # Removing the private directory also tells a late-starting helper to
            # exit before opening the microphone; it must never recreate it.
            self.out = None
            shutil.rmtree(directory)
            if self.process is not None:
                try:
                    self.process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                self.process = None


MIC = {"off": False}                 # True once the mic or speech helper failed; cleared by the next words heard


def mic_off():
    return MIC["off"]


class NotePanel:
    """The note card (notecard.py) plus the speech helper: your words fill in as you speak."""

    def __init__(self):
        self.card = None
        self.on_done = None
        self.listener = Listener()
        self.shown = ""                  # last transcript we put in the box

    @property
    def open(self):
        return self.card is not None and self.card.visible

    def show(self, context_label, on_done):
        """context_label: what the note is for, e.g. "Pricing › Q3 plan"."""
        self.on_done = on_done
        if self.card is None:
            self.card = notecard.NoteCard(lambda: self.close(save=True), lambda: self.close(save=False))
        self.shown = ""
        listening = self.listener.start()
        self.card.show(context_label, listening)
        MIC["off"] = not listening                  # cleared here; a permission error sets it again in poll()
        if not listening:
            self.card.status_is(False, "Speech helper unavailable. Type your note instead.")

    def poll(self):
        """Call often while the card is open: shows what you've said so far."""
        self.card.animate()
        if not self.listener.out:
            return
        err = self.listener.error()
        if err:
            MIC["off"] = True
            self.card.status_is(False, err[:80])
            self.listener.stop(wait=0)
            return
        said = self.listener.text()
        if said:
            MIC["off"] = False
        if said != self.shown and self.card.string() == self.shown:   # don't overwrite your typing
            self.card.set_text(said)
            self.shown = said

    def close(self, save):
        final = self.listener.stop(wait=2.0 if save else 0.3)
        text = self.card.string().strip()
        if save and final and self.card.string() == self.shown:
            text = final.strip()                           # include the last words
        self.card.hide()
        done, self.on_done = self.on_done, None
        if done:
            done(text if save and text else None)
