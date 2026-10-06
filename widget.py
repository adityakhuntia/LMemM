"""LMemM - the on-screen pill. A tiny bar at the bottom of the screen, like Wispr Flow.

    resting   a 40×6 pt translucent pill; a small dot when the thing in front has edits left
    hover     grows a little so it's easy to hit
    click     a small card above it, for the project of the thing in front:
                Left   edits still to do (this thing's first) - tick one to mark it done
                Plan   every note on the project, open then done, and its history
              click the pill again (or ×) to close it

Everything is a non-activating panel: it never takes focus from the app you're in,
and it shows on every Space and over full-screen apps. Data comes from
notes.card(); ticking a box calls back into the tracker, which saves under its lock.
"""

from datetime import datetime

import objc
from AppKit import (NSBackingStoreBuffered, NSBezierPath, NSButton, NSColor, NSFont,
                    NSMakeRect, NSObject, NSPanel, NSScreen, NSScrollView, NSSegmentedControl,
                    NSTextField, NSTrackingArea, NSView, NSVisualEffectView)

BORDERLESS, NONACTIVATING = 0, 1 << 7
# all Spaces, stationary, over full-screen apps, not in the window cycle
COLLECTION = 1 | 16 | 256 | 64
FLOATING = 25                       # NSStatusWindowLevel: above normal windows

PILL_REST, PILL_HOVER = (40, 6), (60, 14)
CARD_W, CARD_MAX_H = 320, 340
TRACK = 1 | 128 | 512               # mouseEnteredAndExited | activeAlways | inVisibleRect


def _label(text, size=11, bold=False, color=None, frame=(0, 0, 10, 10)):
    field = NSTextField.labelWithString_(text)
    field.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    field.setTextColor_(color or NSColor.labelColor())
    field.setFrame_(NSMakeRect(*frame))
    field.cell().setTruncatesLastVisibleLine_(True)
    field.setLineBreakMode_(4)      # truncate tail
    return field


def _when(iso):
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return d.strftime("%-d %b %H:%M") if d.date() != datetime.now().date() else d.strftime("%H:%M")


def _panel(width, height):
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height), BORDERLESS | NONACTIVATING, NSBackingStoreBuffered, False)
    panel.setLevel_(FLOATING)
    panel.setCollectionBehavior_(COLLECTION)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setHasShadow_(True)
    panel.setHidesOnDeactivate_(False)
    panel.setReleasedWhenClosed_(False)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    return panel


class _Flipped(NSView):
    def isFlipped(self):
        return True


class _PillView(NSView):
    def initWithWidget_(self, widget):
        self = objc.super(_PillView, self).initWithFrame_(NSMakeRect(0, 0, *PILL_HOVER))
        self.widget = widget
        self.hover = False
        self.badge = 0
        self.addTrackingArea_(NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), TRACK, self, None))
        return self

    def drawRect_(self, rect):
        w, h = PILL_HOVER if self.hover or self.widget.card_open else PILL_REST
        bw, bh = self.bounds().size.width, self.bounds().size.height
        r = NSMakeRect((bw - w) / 2, (bh - h) / 2, w, h)
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, h / 2, h / 2)
        NSColor.colorWithWhite_alpha_(0.08, 0.85 if self.hover or self.widget.card_open else 0.45).setFill()
        path.fill()
        NSColor.colorWithWhite_alpha_(1.0, 0.28 if self.hover else 0.16).setStroke()
        path.setLineWidth_(0.5)
        path.stroke()
        if self.badge:                                   # edits left on what you're on
            d = 4 if self.hover or self.widget.card_open else 3
            dot = NSMakeRect(r.origin.x + r.size.width - h / 2 - d / 2, (bh - d) / 2, d, d)
            NSColor.systemOrangeColor().colorWithAlphaComponent_(0.9).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(dot).fill()

    def mouseEntered_(self, event):
        self.hover = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hover = False
        self.setNeedsDisplay_(True)

    def mouseDown_(self, event):
        self.widget.toggle_card()

    def acceptsFirstMouse_(self, event):
        return True


class _Actions(NSObject):
    """Target for the card's controls (checkboxes, segments, close)."""

    def initWithWidget_(self, widget):
        self = objc.super(_Actions, self).init()
        self.widget = widget
        return self

    def check_(self, sender):
        self.widget.ticked(sender.tag(), sender.state() == 1)

    def mode_(self, sender):
        self.widget.mode = "left" if sender.selectedSegment() == 0 else "plan"
        self.widget.render()

    def close_(self, sender):
        self.widget.toggle_card()


class Widget:
    """provider() -> notes.card(...) for the thing in front, or None.
    on_tick(note ids, done) marks notes done / open again."""

    def __init__(self, provider, on_tick):
        self.provider = provider
        self.on_tick = on_tick
        self.card_open = False
        self.mode = "left"
        self.rows = []                      # tag -> note id
        self.actions = _Actions.alloc().initWithWidget_(self)
        self.pill = _panel(*PILL_HOVER)
        self.pill_view = _PillView.alloc().initWithWidget_(self)
        self.pill.setContentView_(self.pill_view)
        self.card = _panel(CARD_W, 200)
        self.place()
        self.pill.orderFrontRegardless()

    # -- placement

    def place(self):
        scr = NSScreen.mainScreen().visibleFrame()
        x = scr.origin.x + (scr.size.width - PILL_HOVER[0]) / 2
        self.pill.setFrameOrigin_((x, scr.origin.y + 6))

    # -- state from the tracker

    def refresh(self):
        """Called ~once a second: keep the dot (and an open card) current."""
        data = self.provider()
        badge = len(data["left"]) if data else 0
        if badge != self.pill_view.badge:
            self.pill_view.badge = badge
            self.pill_view.setNeedsDisplay_(True)
        if self.card_open:
            self.render(data)

    def toggle_card(self):
        self.card_open = not self.card_open
        if self.card_open:
            self.mode = "left"
            self.render()
            self.card.orderFrontRegardless()
        else:
            self.card.orderOut_(None)
        self.pill_view.setNeedsDisplay_(True)

    def ticked(self, tag, done):
        if 0 <= tag < len(self.rows):
            self.on_tick([self.rows[tag]], done)
            self.render()

    # -- the card

    def render(self, data=None):
        data = data if data is not None else self.provider()
        self.rows = []
        content = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, 100))
        content.setMaterial_(13)            # hudWindow
        content.setBlendingMode_(0)         # behind window
        content.setState_(1)                # active
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(12)
        content.layer().setMasksToBounds_(True)

        body = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, 10))
        y = 12
        if data is None:
            body.addSubview_(_label("Nothing here yet. Press ⌃⌥N to add a note to what you're on.",
                                    11, color=NSColor.secondaryLabelColor(), frame=(14, y, CARD_W - 28, 16)))
            y += 28
        else:
            body.addSubview_(_label(data["project"], 13, bold=True, frame=(14, y, CARD_W - 48, 17)))
            close = NSButton.buttonWithTitle_target_action_("×", self.actions, "close:")
            close.setBordered_(False)
            close.setFrame_(NSMakeRect(CARD_W - 30, y - 2, 18, 18))
            body.addSubview_(close)
            y += 18
            body.addSubview_(_label(f"{data['app']} · {data['title']}", 10,
                                    color=NSColor.secondaryLabelColor(), frame=(14, y, CARD_W - 28, 14)))
            y += 22
            seg = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
                [f"Left {len(data['left'])}", "Plan"], 0, self.actions, "mode:")
            seg.setControlSize_(1)          # small
            seg.setSelectedSegment_(0 if self.mode == "left" else 1)
            seg.setFrame_(NSMakeRect(14, y, CARD_W - 28, 20))
            body.addSubview_(seg)
            y += 30
            y = self._left(body, data, y) if self.mode == "left" else self._plan(body, data, y)
            hours = data["seconds"] // 3600
            spent = f"{hours}h {data['seconds'] % 3600 // 60}m" if hours else f"{data['seconds'] // 60}m"
            body.addSubview_(_label(f"{data['things']} thing{'s' * (data['things'] != 1)} · "
                                    f"{data['visits']} visits · {spent}", 10,
                                    color=NSColor.tertiaryLabelColor(), frame=(14, y + 4, CARD_W - 28, 14)))
            y += 26

        height = min(y, CARD_MAX_H)
        body.setFrame_(NSMakeRect(0, 0, CARD_W, y))
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, height))
        scroll.setDrawsBackground_(False)
        scroll.setHasVerticalScroller_(y > CARD_MAX_H)
        scroll.setDocumentView_(body)
        content.setFrame_(NSMakeRect(0, 0, CARD_W, height))
        content.addSubview_(scroll)
        self.card.setContentView_(content)
        pill = self.pill.frame()
        self.card.setFrame_display_(NSMakeRect(pill.origin.x + pill.size.width / 2 - CARD_W / 2,
                                               pill.origin.y + pill.size.height + 8, CARD_W, height), True)

    def _row(self, body, y, note, checked, detail):
        box = NSButton.checkboxWithTitle_target_action_(note["text"], self.actions, "check:")
        box.setFont_(NSFont.systemFontOfSize_(12))
        box.setState_(1 if checked else 0)
        box.setTag_(len(self.rows))
        box.setFrame_(NSMakeRect(12, y, CARD_W - 24, 18))
        box.cell().setLineBreakMode_(4)
        self.rows.append(note["id"])
        body.addSubview_(box)
        y += 18
        if detail:
            body.addSubview_(_label(detail, 10, color=NSColor.tertiaryLabelColor(), frame=(34, y, CARD_W - 48, 13)))
            y += 14
        return y + 6

    def _left(self, body, data, y):
        if not data["left"]:
            body.addSubview_(_label("Nothing left on this project ✓", 11,
                                    color=NSColor.secondaryLabelColor(), frame=(14, y, CARD_W - 28, 16)))
            return y + 24
        for n in data["left"]:
            y = self._row(body, y, n, False, _when(n["at"]) + ("" if n["here"] else f" · on {n['on']}"))
        return y

    def _plan(self, body, data, y):
        for n in data["plan"]:
            detail = (f"done {_when(n['done'])}" if n["done"] else _when(n["at"])) \
                + ("" if n["here"] else f" · on {n['on']}")
            y = self._row(body, y, n, bool(n["done"]), detail)
        if data["history"]:
            y += 4
            body.addSubview_(_label("History", 11, bold=True, color=NSColor.secondaryLabelColor(),
                                    frame=(14, y, CARD_W - 28, 15)))
            y += 18
            for h in data["history"][:20]:
                mark = "✓" if h["event"] == "done" else "+"
                body.addSubview_(_label(f"{_when(h['at'])}  {mark}  {h['text']}", 10,
                                        color=NSColor.secondaryLabelColor(), frame=(14, y, CARD_W - 28, 14)))
                y += 16
        return y
