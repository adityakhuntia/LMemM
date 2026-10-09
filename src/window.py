"""LMemM - the main window. It draws window_model.view() and forwards the banner's button;
it decides nothing (S8, W1-W6 in window_model.py). Only the drawing is here, so a Mac is needed
to look at it. The projects and notes arrive in the next steps; today the window is the
banner and one quiet line.
"""

import objc
from Foundation import NSObject
from AppKit import NSApplication, NSMakeRect, NSWindow

import setup_kit as kit
import window_model
from widget import _Flipped

W, H, X = 520, 360, 36
CW = W - 2 * X
TONES = {"red": "red", "grey": None, "calm": None}      # the banner box's tone (red is only for what is off)


class _MainWindow(NSWindow):
    def canBecomeKeyWindow(self):
        return True


class _MainClosing(NSObject):
    """A closed window is only hidden; it opens again from the menu."""

    def windowShouldClose_(self, window):
        window.orderOut_(None)
        return False


class MainWindow:
    """on_press(row id) is called when the banner's button is pressed (ids the menu already knows)."""

    def __init__(self, on_press):
        self.on_press = on_press
        self.shown = None
        style = 1 | 2 | (1 << 15)                                  # titled, closable, content under the title bar
        self.window = _MainWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), style, 2, False)
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setTitleVisibility_(1)
        for button in (1, 2):                                      # no minimise, no zoom: only a way out
            self.window.standardWindowButton_(button).setHidden_(True)
        self.window.setReleasedWhenClosed_(False)
        self.window.setBackgroundColor_(kit.card_background())
        self.closing = _MainClosing.alloc().init()
        self.window.setDelegate_(self.closing)
        self.root = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        self.window.setContentView_(self.root)
        self.window.center()

    def visible(self):
        return bool(self.window.isVisible())

    def show(self, view):
        self.update(view)
        self.window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def update(self, view):
        """Redraw only when something a person would see has changed."""
        sig = window_model.signature(view)
        if sig == self.shown:
            return
        self.shown = sig
        for sub in list(self.root.subviews()):
            sub.removeFromSuperview()
        y = 64
        kit.put_text(self.root, view["heading"], X, y, CW, size=28, weight=700)
        y += 44
        banner = view["banner"]
        if banner:
            y += self._banner(banner, y) + 18
        if view["line"]:
            kit.put_text(self.root, view["line"], X, y, CW, size=15, color=kit.mute())

    def _banner(self, banner, y):
        """The one banner, with its one button. Returns the height it takes."""
        tone = TONES[banner["tone"]]
        height = kit.note(self.root, tone, banner["line"], X, y, CW, lead=banner["title"])
        button = banner["button"]
        if button:
            y += height + 12
            row = button["id"]
            kit.button(self.root, button["title"], X, y, 220, 40, lambda: self.on_press(row), size=15)
            height += 12 + 40
        return height
