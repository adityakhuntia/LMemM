"""LMemM - the on-screen pill. A tiny bar at the bottom of the screen, like Wispr Flow.

    resting   a thin pill, nearly invisible
    notes     a small pill with a number: edits waiting on the thing in front
    hover     the pill unfolds to show the first one
    speaking  while the ⌃⌥N note window is open: a waveform and the words so far
    click     a quiet card above it for the thing in front: its open notes, tick one to
              finish it, and an "Add a note…" row. "N more in <project>" goes one level
              deeper to the whole project (grouped by thing, finished notes behind "Done").
              Click the pill again, or anywhere else, to close it.

Everything is a non-activating panel: it never takes focus from the app you're in,
and it shows on every Space and over full-screen apps. It follows the system light/dark
setting. What the card shows is decided in notes.card_view() (plain data, tested);
this file only draws it. Ticking a box calls back into the tracker, which saves under its lock.
"""

import math
import time

import objc
from AppKit import (NSApplication, NSBackingStoreBuffered, NSBezierPath, NSColor, NSEvent,
                    NSFont, NSFontAttributeName, NSForegroundColorAttributeName, NSMakeRect,
                    NSPanel, NSScreen, NSScrollView, NSStrikethroughStyleAttributeName, NSTextField,
                    NSTrackingArea, NSView, NSVisualEffectView, NSAttributedString)

import notes

BORDERLESS, NONACTIVATING = 0, 1 << 7
# all Spaces, stationary, over full-screen apps, not in the window cycle
COLLECTION = 1 | 16 | 256 | 64
FLOATING = 25                       # NSStatusWindowLevel: above normal windows

CARD_W, CARD_MAX_H, PAD = 272, 360, 14
PILL_MARGIN = (10, 6)               # hit area around the drawn capsule
PILL_BOTTOM = 6
TRACK = 1 | 128 | 512               # mouseEnteredAndExited | activeAlways | inVisibleRect
POPOVER_MATERIAL, BEHIND_WINDOW, ACTIVE = 6, 0, 1
CLICK_MASK = (1 << 1) | (1 << 3)    # left and right mouse down, in any app
FADE_SECONDS = 0.8                  # a ticked note stays struck through this long
ADD_LABEL = "Add a note…"
EMPTY_HINT = "Nothing left here. Hold {key} and say what to remember for this page."


def _dark():
    app = NSApplication.sharedApplication()
    match = app.effectiveAppearance().bestMatchFromAppearancesWithNames_(
        ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"])
    return match == "NSAppearanceNameDarkAqua"


def _text_width(text, font):
    return NSAttributedString.alloc().initWithString_attributes_(text, {NSFontAttributeName: font}).size().width


def _label(text, size=11, bold=False, color=None, frame=(0, 0, 10, 10), wrap=False, strike=False):
    """A text field. wrap=True lets it run to several lines; the frame's height is then
    set from the text. Returns (field, height)."""
    font = NSFont.systemFontOfSize_weight_(size, 0.4) if bold else NSFont.systemFontOfSize_(size)
    color = color or NSColor.labelColor()
    field = NSTextField.labelWithString_(text)
    if strike:
        field.setAttributedStringValue_(NSAttributedString.alloc().initWithString_attributes_(
            text, {NSFontAttributeName: font, NSForegroundColorAttributeName: color,
                   NSStrikethroughStyleAttributeName: 1}))
    else:
        field.setFont_(font)
        field.setTextColor_(color)
    field.setLineBreakMode_(0 if wrap else 4)         # wrap words / truncate tail
    x, y, w, h = frame
    if wrap:
        h = max(h, field.cell().cellSizeForBounds_(NSMakeRect(0, 0, w, 10000)).height)
    field.setFrame_(NSMakeRect(x, y, w, h))
    return field, h


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


class _Tap(_Flipped):
    """A clickable area (a note row, "more", "Add a note…"). Optionally a soft rounded fill."""

    def initWithFrame_callback_(self, frame, callback):
        self = objc.super(_Tap, self).initWithFrame_(frame)
        self.callback = callback
        self.fill = False
        return self

    def drawRect_(self, rect):
        if self.fill:
            NSColor.labelColor().colorWithAlphaComponent_(0.07).setFill()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 10, 10).fill()

    def mouseDown_(self, event):
        self.callback()

    def acceptsFirstMouse_(self, event):
        return True


class _Ring(_Flipped):
    """The round tick box: an outline, filled orange with a tick once done."""

    def initWithChecked_(self, checked):
        self = objc.super(_Ring, self).initWithFrame_(NSMakeRect(0, 0, 17, 17))
        self.checked = checked
        return self

    def drawRect_(self, rect):
        circle = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(1, 1, 15, 15))
        if self.checked:
            NSColor.systemOrangeColor().setFill()
            circle.fill()
            tick = NSBezierPath.bezierPath()
            tick.moveToPoint_((5, 8.8))
            tick.lineToPoint_((7.5, 11.5))
            tick.lineToPoint_((12, 5.5))
            tick.setLineWidth_(1.8)
            tick.setLineCapStyle_(1)
            tick.setLineJoinStyle_(1)
            NSColor.whiteColor().setStroke()
            tick.stroke()
        else:
            NSColor.tertiaryLabelColor().setStroke()
            circle.setLineWidth_(1.5)
            circle.stroke()


class _PillView(NSView):
    """The pill. It draws whatever the widget says it is: a thin bar, a count, the first
    note, or a waveform with the words so far. The panel is resized to match (see Widget.layout)."""

    def initWithWidget_(self, widget):
        self = objc.super(_PillView, self).initWithFrame_(NSMakeRect(0, 0, 80, 20))
        self.widget = widget
        self.hover = False
        self.addTrackingArea_(NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), TRACK, self, None))
        return self

    def drawRect_(self, rect):
        w = self.widget
        bw, bh = self.bounds().size.width, self.bounds().size.height
        cw, ch = bw - 2 * PILL_MARGIN[0], bh - 2 * PILL_MARGIN[1]
        capsule = NSMakeRect(PILL_MARGIN[0], PILL_MARGIN[1], cw, ch)
        dark = _dark()
        ink = NSColor.colorWithWhite_alpha_(0.97 if dark else 0.09, 1.0)       # the pill itself
        on_ink = NSColor.colorWithWhite_alpha_(0.09 if dark else 1.0, 1.0)     # text on the pill
        quiet = w.mode_of_pill() == "rest"
        ink.colorWithAlphaComponent_(0.45 if quiet and not self.hover else 0.94).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(capsule, ch / 2, ch / 2).fill()
        state = w.mode_of_pill()
        mid = PILL_MARGIN[1] + ch / 2
        if state == "count":
            self._text(str(w.count), 12, True, on_ink, capsule, centre=True)
        elif state == "peek":
            self._dot(PILL_MARGIN[0] + 11, mid)
            self._text(w.peek_text(), 13, False, on_ink, NSMakeRect(PILL_MARGIN[0] + 22, 0, cw - 32, bh))
        elif state == "listening":
            self._bars(PILL_MARGIN[0] + 12, mid)
            self._text(w.heard_text(), 13, False, on_ink, NSMakeRect(PILL_MARGIN[0] + 26, 0, cw - 36, bh))

    @objc.python_method
    def _dot(self, x, y):
        NSColor.systemOrangeColor().setFill()
        NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(x - 4, y - 4, 8, 8)).fill()

    @objc.python_method
    def _bars(self, x, y):
        NSColor.systemOrangeColor().setFill()
        for i, base in enumerate((5, 12, 8, 13, 6)):
            h = max(3, base * (0.6 + 0.4 * math.sin(time.time() * 7 + i * 1.3)))
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(x - 7 + i * 3.6, y - h / 2, 2.5, h), 1.2, 1.2).fill()

    @objc.python_method
    def _text(self, text, size, bold, color, area, centre=False):
        font = NSFont.systemFontOfSize_weight_(size, 0.4) if bold else NSFont.systemFontOfSize_(size)
        attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: color}
        wide = _text_width(text, font)
        high = NSAttributedString.alloc().initWithString_attributes_(text, attrs).size().height
        x = area.origin.x + ((area.size.width - wide) / 2 if centre else 0)
        text_y = area.origin.y + (area.size.height - high) / 2
        NSAttributedString.alloc().initWithString_attributes_(text, attrs).drawAtPoint_((x, text_y))

    def mouseEntered_(self, event):
        self.hover = True
        self.widget.layout()

    def mouseExited_(self, event):
        self.hover = False
        self.widget.layout()

    def mouseDown_(self, event):
        self.widget.toggle_card()

    def acceptsFirstMouse_(self, event):
        return True


class Widget:
    """provider() -> notes.card(...) for the thing in front, or None.
    on_tick(note ids, done) marks notes done / open again.
    on_add() opens the ⌃⌥N note window.
    heard() -> None, or the words so far while the note window is open (the pill shows them)."""

    def __init__(self, provider, on_tick, on_add=None, heard=None, hotkey="⌃⌥N"):
        self.provider = provider
        self.on_tick = on_tick
        self.on_add = on_add or (lambda: None)
        self.heard = heard or (lambda: None)
        self.hotkey = hotkey
        self.card_open = False
        self.mode = "here"                  # "here" | "project"
        self.show_done = False
        self.fading = {}                    # note id -> when it was ticked
        self.data = None
        self.count, self.first = 0, ""
        self.listening = None               # None, or the words so far
        self.shown = None                   # what the open card currently shows
        self.scroll = None
        self.pill = _panel(80, 20)
        self.pill_view = _PillView.alloc().initWithWidget_(self)
        self.pill.setContentView_(self.pill_view)
        self.card = _panel(CARD_W, 200)
        self.layout(animate=False)
        self.pill.orderFrontRegardless()
        self.monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(CLICK_MASK, self._clicked_elsewhere)

    # -- the pill

    def mode_of_pill(self):
        if self.listening is not None:
            return "listening"
        if self.count and (self.pill_view.hover and not self.card_open):
            return "peek"
        return "count" if self.count else "rest"

    def peek_text(self):
        text = self.first.replace("\n", " ")
        return text if len(text) <= 32 else text[:31] + "…"

    def heard_text(self):
        text = (self.listening or "").replace("\n", " ").strip()
        if not text:
            return "Listening…"
        return text if len(text) <= 30 else "…" + text[-29:]

    def _capsule(self):
        """Size of the drawn capsule for the current state."""
        state = self.mode_of_pill()
        if state == "peek":
            return _text_width(self.peek_text(), NSFont.systemFontOfSize_(13)) + 44, 28
        if state == "listening":
            return _text_width(self.heard_text(), NSFont.systemFontOfSize_(13)) + 48, 30
        if state == "count":
            return 44, 22
        return (44, 10) if self.pill_view.hover else (36, 5)

    def layout(self, animate=True):
        """Resize and place the pill panel for its state (smoothly), keeping it bottom-centre."""
        cw, ch = self._capsule()
        w, h = cw + 2 * PILL_MARGIN[0], ch + 2 * PILL_MARGIN[1]
        scr = NSScreen.mainScreen().visibleFrame()
        frame = NSMakeRect(scr.origin.x + (scr.size.width - w) / 2, scr.origin.y + PILL_BOTTOM - PILL_MARGIN[1], w, h)
        self.pill.setFrame_display_animate_(frame, True, animate)
        self.pill_view.setNeedsDisplay_(True)
        if self.card_open:
            self._place_card()

    def pulse(self, heard):
        """Called on every tick of the tracker's loop: moves the waveform and follows the
        note window (open/closed, words so far)."""
        was = self.listening is not None
        self.listening = heard
        if (heard is not None) != was:
            self.layout()
        elif heard is not None:
            self.pill_view.setNeedsDisplay_(True)
            if abs(_text_width(self.heard_text(), NSFont.systemFontOfSize_(13)) + 48 + 2 * PILL_MARGIN[0]
                   - self.pill.frame().size.width) > 2:
                self.layout()

    # -- state from the tracker

    def refresh(self):
        """Called ~once a second: keep the count (and an open card) current."""
        self.data = self.provider()
        count, first = notes.pill_summary(self.data)
        if (count, first) != (self.count, self.first):
            self.count, self.first = count, first
            self.layout()
        now = time.time()
        for nid in [n for n, at in self.fading.items() if now - at > FADE_SECONDS]:
            del self.fading[nid]
        if self.card_open and self._key() != self.shown:
            self.render()                   # only when something changed: keeps your scroll position

    def toggle_card(self):
        self.card_open = not self.card_open
        if self.card_open:
            self.mode, self.show_done, self.scroll = "here", False, None
            self.data = self.provider()
            self.render()
            self.card.orderFrontRegardless()
            self.card.setAlphaValue_(0.0)
            self.card.animator().setAlphaValue_(1.0)
        else:
            self.card.orderOut_(None)
        self.layout(animate=False)

    def _clicked_elsewhere(self, event):
        # global monitors only see clicks in *other* apps, so this never fires for our own panels
        if self.card_open:
            self.toggle_card()

    def ticked(self, nid, done):
        if done:
            self.fading[nid] = time.time()
        else:
            self.fading.pop(nid, None)
        self.on_tick([nid], done)
        self.data = self.provider()
        self.render()

    def _go(self, mode, show_done=None):
        self.mode = mode
        if show_done is not None:
            self.show_done = show_done
        self.scroll = None                  # a different view starts at the top
        self.render()

    def _add(self):
        self.toggle_card()
        self.on_add()

    # -- the card

    def _key(self):
        return repr((self.data, self.mode, self.show_done, sorted(self.fading)))

    def render(self):
        self.shown = self._key()
        view = notes.card_view(self.data, self.mode, self.show_done, self.fading)
        kept = self.scroll.contentView().bounds().origin.y if self.scroll is not None else 0
        body = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, 10))
        y = 14
        if view.get("empty"):
            y = self._empty(body, y)
        elif view["mode"] == "project":
            y = self._project(body, view, y)
        else:
            y = self._here(body, view, y)
        y += 8

        height = min(y, CARD_MAX_H)
        body.setFrame_(NSMakeRect(0, 0, CARD_W, y))
        content = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, height))
        content.setMaterial_(POPOVER_MATERIAL)          # follows light / dark by itself
        content.setBlendingMode_(BEHIND_WINDOW)
        content.setState_(ACTIVE)
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(18)
        content.layer().setMasksToBounds_(True)
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, CARD_W, height))
        scroll.setDrawsBackground_(False)
        scroll.setHasVerticalScroller_(y > CARD_MAX_H)
        scroll.setAutohidesScrollers_(True)
        scroll.setDocumentView_(body)
        content.addSubview_(scroll)
        self.card.setContentView_(content)
        if kept and y > height:                       # stay where you had scrolled to
            scroll.contentView().scrollToPoint_((0, min(kept, y - height)))
            scroll.reflectScrolledClipView_(scroll.contentView())
        self.scroll = scroll
        self.card_height = height
        self._place_card()

    def _place_card(self):
        pill = self.pill.frame()
        self.card.setFrame_display_(NSMakeRect(pill.origin.x + pill.size.width / 2 - CARD_W / 2,
                                               pill.origin.y + pill.size.height + 4, CARD_W,
                                               getattr(self, "card_height", 100)), True)

    def _header(self, body, y, title, caption, back=None):
        field, h = _label(title, 14, bold=True, frame=(PAD, y, CARD_W - 2 * PAD, 18))
        body.addSubview_(field)
        y += 19
        if back:                                    # "‹ Q3 plan": one step back to this thing
            tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(PAD - 4, y, CARD_W - 2 * PAD + 8, 16), back[1])
            small, _ = _label(f"‹ {back[0]}", 12, color=NSColor.secondaryLabelColor(), frame=(4, 0, CARD_W - 2 * PAD, 16))
            tap.addSubview_(small)
            body.addSubview_(tap)
        else:
            small, _ = _label(caption, 12, color=NSColor.secondaryLabelColor(), frame=(PAD, y, CARD_W - 2 * PAD, 16))
            body.addSubview_(small)
        return y + 24

    def _note(self, body, y, row):
        text_w = CARD_W - 2 * PAD - 28
        color = NSColor.secondaryLabelColor() if row["done"] else NSColor.labelColor()
        field, h = _label(row["text"], 14, color=color, frame=(28 + 8, 0, text_w, 17), wrap=True, strike=row["done"])
        height = h + 14
        tap = _Tap.alloc().initWithFrame_callback_(
            NSMakeRect(6, y, CARD_W - 12, height),
            lambda nid=row["id"], done=row["done"]: self.ticked(nid, not done))
        ring = _Ring.alloc().initWithChecked_(row["done"])
        ring.setFrame_(NSMakeRect(PAD - 6 + 2, 8, 17, 17))
        field.setFrame_(NSMakeRect(PAD - 6 + 2 + 17 + 11, 7, text_w - 4, h))
        tap.addSubview_(ring)
        tap.addSubview_(field)
        body.addSubview_(tap)
        return y + height

    def _link(self, body, y, left, right, callback):
        tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(6, y, CARD_W - 12, 24), callback)
        mute = NSColor.secondaryLabelColor()
        tap.addSubview_(_label(left, 12, color=mute, frame=(PAD - 6, 4, CARD_W - 80, 16))[0])
        tap.addSubview_(_label(right, 13, color=mute, frame=(CARD_W - 12 - PAD - 4, 3, 14, 16))[0])
        body.addSubview_(tap)
        return y + 26

    def _add_row(self, body, y):
        tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(8, y, CARD_W - 16, 34), self._add)
        tap.fill = True
        mute = NSColor.secondaryLabelColor()
        tap.addSubview_(_label(ADD_LABEL, 13, color=mute, frame=(12, 8, 150, 18))[0])
        key = _label(self.hotkey, 11, color=NSColor.tertiaryLabelColor(), frame=(CARD_W - 16 - 12 - 50, 9, 50, 16))[0]
        key.setAlignment_(2)                         # right
        tap.addSubview_(key)
        body.addSubview_(tap)
        return y + 42

    def _empty(self, body, y):
        field, h = _label(EMPTY_HINT.format(key=self.hotkey), 13, color=NSColor.secondaryLabelColor(),
                          frame=(PAD, y, CARD_W - 2 * PAD, 18), wrap=True)
        body.addSubview_(field)
        return y + h + 6

    def _here(self, body, view, y):
        y = self._header(body, y, view["title"], view["caption"])
        if view["rows"]:
            for row in view["rows"]:
                y = self._note(body, y, row)
        else:
            y = self._empty(body, y)
        y = self._add_row(body, y + 4)
        if view["more"]:
            y = self._link(body, y, f"{view['more']} more in {view['project']}", "›", lambda: self._go("project"))
        return y

    def _project(self, body, view, y):
        y = self._header(body, y, view["title"], view["caption"], back=(view["back"], lambda: self._go("here")))
        for thing, rows in view["groups"]:
            field, _ = _label(thing.upper(), 10, bold=True, color=NSColor.tertiaryLabelColor(),
                              frame=(PAD, y + 4, CARD_W - 2 * PAD, 14))
            body.addSubview_(field)
            y += 22
            for row in rows:
                y = self._note(body, y, row)
        if view["done_count"]:
            label = f"Done · {view['done_count']}"
            y = self._link(body, y + 4, label, "⌄" if view["done"] else "›",
                           lambda: self._go("project", show_done=not self.show_done))
            for row in view["done"]:
                y = self._note(body, y, row)
        return y
