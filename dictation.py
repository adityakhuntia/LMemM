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
(listen/listen.m -> bin/LMemM Listen.app, built with clang on first use). It has
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

import objc
from AppKit import (NSApp, NSApplication, NSBackingStoreBuffered, NSColor, NSFont,
                    NSMakeRect, NSObject, NSPanel, NSRunningApplication, NSScreen,
                    NSScrollView, NSTextField, NSTextView, NSWorkspace)

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


def register_hotkey(callback):
    """Call callback() whenever ⌃⌥N is pressed anywhere. Returns True on success."""
    def handler(_call, _event, _data):
        try:
            callback()
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
    return ok


def start_app():
    """An invisible app (no Dock icon) so we can receive the hotkey and show the note window."""
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)                        # accessory
    app.finishLaunching()
    return app


class _Keys(NSObject):
    """Return saves, Escape cancels, Shift-Return makes a new line."""

    def initWithPanel_(self, panel):
        self = objc.super(_Keys, self).init()
        self.panel = panel
        return self

    def textView_doCommandBySelector_(self, tv, sel):
        sel = sel.decode() if isinstance(sel, bytes) else str(sel)
        if sel == "insertNewline:":
            self.panel.close(save=True)
            return True
        if sel == "cancelOperation:":
            self.panel.close(save=False)
            return True
        return False

    def windowShouldClose_(self, window):
        self.panel.close(save=False)
        return False


HERE = os.path.dirname(os.path.abspath(__file__))
LISTEN_APP = os.path.join(HERE, "bin", "LMemM Listen.app")


def ensure_listener():
    """Build the speech helper app once (needs Xcode Command Line Tools' clang)."""
    exe = os.path.join(LISTEN_APP, "Contents", "MacOS", "listen")
    src = os.path.join(HERE, "listen", "listen.m")
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
        return True
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    subprocess.run(["cp", os.path.join(HERE, "listen", "Info.plist"),
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


class NotePanel:
    """A small floating window: 'Note for: <what you're doing>' + a text box that
    fills in as you speak."""

    def __init__(self):
        self.win = None
        self.on_done = None
        self.prev_app = None
        self.listener = Listener()
        self.shown = ""                  # last transcript we put in the box

    @property
    def open(self):
        return self.win is not None and self.win.isVisible()

    def show(self, context_label, on_done):
        self.on_done = on_done
        self.prev_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if self.win is None:
            self._build()
        self.label.setStringValue_(f"Note for: {context_label}"[:110])
        self.text.setString_("")
        self.shown = ""
        listening = self.listener.start()
        self.status.setStringValue_("🎙  Listening… speak now  ·  or type" if listening
                                    else "Speech helper unavailable, type your note")
        scr = NSScreen.mainScreen().visibleFrame()
        w, h = 560, 170
        self.win.setFrame_display_(NSMakeRect(scr.origin.x + (scr.size.width - w) / 2,
                                              scr.origin.y + scr.size.height - h - 60, w, h), True)
        NSApp.setActivationPolicy_(0)         # a normal app while the window is up (keyboard focus)
        NSApp.activateIgnoringOtherApps_(True)
        self.win.makeKeyAndOrderFront_(None)
        self.win.makeFirstResponder_(self.text)

    def poll(self):
        """Call often while the window is open: shows what you've said so far."""
        if not self.listener.out:
            return
        err = self.listener.error()
        if err:
            self.status.setStringValue_(f"⚠️  {err}"[:120])
            self.listener.stop(wait=0)
            return
        said = self.listener.text()
        current = self.text.string()
        if said != self.shown and current == self.shown:   # don't overwrite your typing
            self.text.setString_(said)
            self.shown = said
        if not self.win.isKeyWindow():
            NSApp.activateIgnoringOtherApps_(True)
            self.win.makeKeyAndOrderFront_(None)

    def close(self, save):
        final = self.listener.stop(wait=2.0 if save else 0.3)
        text = self.text.string().strip()
        if save and final and self.text.string() == self.shown:
            text = final.strip()                           # include the last words
        self.win.orderOut_(None)
        NSApp.setActivationPolicy_(1)                     # back to invisible
        if self.prev_app is not None:
            self.prev_app.activateWithOptions_(0)       # back to what you were doing
        done, self.on_done = self.on_done, None
        if done:
            done(text if save and text else None)

    def _build(self):
        style = 1 | 2 | 8                                 # titled, closable, resizable
        self.win = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 560, 170), style, NSBackingStoreBuffered, False)
        self.win.setTitle_("LMemM note  ·  Return saves  ·  Esc cancels")
        self.win.setLevel_(3)                             # floating above other windows
        self.win.setReleasedWhenClosed_(False)
        content = self.win.contentView()
        self.label = NSTextField.labelWithString_("")
        self.label.setFrame_(NSMakeRect(14, 136, 532, 20))
        self.label.setFont_(NSFont.boldSystemFontOfSize_(12))
        self.label.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(self.label)
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(14, 20, 532, 110))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(2)
        self.text = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 532, 118))
        self.text.setFont_(NSFont.systemFontOfSize_(15))
        self.text.setRichText_(False)
        self.keys = _Keys.alloc().initWithPanel_(self)
        self.text.setDelegate_(self.keys)
        self.win.setDelegate_(self.keys)
        scroll.setDocumentView_(self.text)
        content.addSubview_(scroll)
        self.status = NSTextField.labelWithString_("")
        self.status.setFrame_(NSMakeRect(14, 2, 532, 14))
        self.status.setFont_(NSFont.systemFontOfSize_(10))
        self.status.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(self.status)
