"""LMemM - the first-run window. It draws onboarding.Setup.view() and forwards presses; it decides
nothing (rule S8). Every word, every enabled button and every permission state comes from the
model, which is tested without a Mac. This file is only layout.

    welcome → you → access → try → done          (docs/specs/2026-10-09-first-run-onboarding.md)

The "try" screen uses the real ⌃⌥N hotkey and the real note card, as a rehearsal: what you say
is not stored. Closing the window leaves setup where it was; the next start resumes there.
"""

import objc
from Foundation import NSObject
from AppKit import (NSApplication, NSBezierPath, NSColor, NSFont, NSImageView, NSMakeRect,
                    NSScrollView, NSVisualEffectView, NSWindow, NSWorkspace)

import apps
import config
import dictation
import macos
import onboarding
import permissions
import widget
from widget import ACTIVE, BEHIND_WINDOW, POPOVER_MATERIAL, _Fields, _field, _Flipped, _label, _Ring, _symbol, _Tap

W, H, X = 480, 580, 36
CW = W - 2 * X
ACCENT = (0.91, 0.455, 0.165)                 # the pill's orange
ICON_SYMBOLS = {"voice": "mic", "ax": "figure.stand", "screen": "display"}


def _accent(alpha=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(*ACCENT, alpha)


class _Mark(_Flipped):
    """The app's mark: a dark tile with the pill's shape, a white capsule and a small orange dot."""

    def drawRect_(self, rect):
        NSColor.colorWithRed_green_blue_alpha_(0.09, 0.09, 0.1, 1.0).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 15, 15).fill()
        NSColor.whiteColor().setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(NSMakeRect(14, 26, 24, 8), 4, 4).fill()
        _accent().setFill()
        NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(42, 26, 8, 8)).fill()


class _Dots(_Flipped):
    """Five little dots; the current screen's is orange."""

    def initWithIndex_(self, index):
        self = objc.super(_Dots, self).initWithFrame_(NSMakeRect(0, 0, 5 * 13, 8))
        self.index = index
        return self

    def drawRect_(self, rect):
        for i in range(5):
            (_accent() if i <= self.index else NSColor.tertiaryLabelColor()).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(i * 13 + 1, 1, 6, 6)).fill()


class _Tile(_Flipped):
    """A permission's icon: a soft rounded square with an SF Symbol; green once granted, red when off."""

    def initWithSymbol_tone_(self, symbol, tone):
        self = objc.super(_Tile, self).initWithFrame_(NSMakeRect(0, 0, 34, 34))
        self.tone = tone
        image = _symbol(symbol)
        if image is not None:
            holder = NSImageView.alloc().initWithFrame_(NSMakeRect(8, 8, 18, 18))
            holder.setImage_(image)
            holder.setContentTintColor_(NSColor.systemGreenColor() if tone == "good" else
                                        NSColor.systemRedColor() if tone == "bad" else NSColor.labelColor())
            self.addSubview_(holder)
        return self

    def drawRect_(self, rect):
        base = (NSColor.systemGreenColor() if self.tone == "good" else
                NSColor.systemRedColor() if self.tone == "bad" else NSColor.labelColor())
        base.colorWithAlphaComponent_(0.07 if self.tone == "soft" else 0.14).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 10, 10).fill()


class _Box(_Flipped):
    """A soft rounded outline (the name field)."""

    def drawRect_(self, rect):
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0.75, 0.75, self.bounds().size.width - 1.5, self.bounds().size.height - 1.5), 12, 12)
        path.setLineWidth_(1.5)
        NSColor.tertiaryLabelColor().setStroke()
        path.stroke()


class _Window(NSWindow):
    def canBecomeKeyWindow(self):
        return True


class _Closing(NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_Closing, self).init()
        self.owner = owner
        return self

    def windowShouldClose_(self, window):
        self.owner.closed = True
        return True


class SetupWindow:
    def __init__(self, setup):
        self.setup = setup
        self.closed = False
        self.show_saved = False
        self.picker = None
        self.hotkey_flag = False
        self.signature = None
        self.panel = dictation.NotePanel()
        self.icons = {}
        self.name_field = self.primary_tap = self.hint = None

        style = 1 | 2 | (1 << 15)                                  # titled, closable, content under the title bar
        self.window = _Window.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), style, 2, False)
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setTitleVisibility_(1)
        for button in (1, 2):                                      # no minimise, no zoom: only a way out
            self.window.standardWindowButton_(button).setHidden_(True)
        self.window.setReleasedWhenClosed_(False)
        self.closing = _Closing.alloc().initWithOwner_(self)
        self.window.setDelegate_(self.closing)
        effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        effect.setMaterial_(POPOVER_MATERIAL)
        effect.setBlendingMode_(BEHIND_WINDOW)
        effect.setState_(ACTIVE)
        self.window.setContentView_(effect)
        self.root = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        effect.addSubview_(self.root)
        self.window.center()
        self.fields = _Fields.alloc().initWithChange_submit_cancel_(self._typed, lambda _t: self._primary(), lambda: None)

    # ------------------------------------------------------------ the loop calls these

    def show(self):
        self.render()
        self.window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def close(self):
        if self.panel.open:
            self.panel.close(save=False)
        self.window.orderOut_(None)

    def hotkey(self):
        self.hotkey_flag = True

    def tick(self):
        """Called about ten times a second."""
        if self.panel.open:
            self.panel.poll()
        if self.hotkey_flag:
            self.hotkey_flag = False
            if self.setup.step == "try":
                self.open_rehearsal()
        changed = self.setup.refresh()
        if changed or self._signature() != self.signature:
            self.render()

    def _signature(self):
        v = self.setup.view()
        if v["step"] == "you":                                     # typing must not rebuild the field under your fingers
            v = {**v, "name": None, "primary": None}
        return repr(v) + repr(self.picker is not None)

    # ------------------------------------------------------------ presses

    def _primary(self):
        button = self.setup.view()["primary"]
        if not button or not button["enabled"]:
            return
        if button["action"] == "show_note":
            self.open_rehearsal()
            return
        self.setup.press_primary()
        self.render()

    def _secondary(self):
        secondary = self.setup.view()["secondary"]
        if not secondary:
            return
        {"next": self.setup.next, "finish": self.setup.finish}.get(secondary["action"], lambda: None)()
        self.render()

    def _do(self, fn, *args):
        fn(*args)
        self.render()

    def _typed(self, text):
        self.setup.set_name(text)
        view = self.setup.view()
        if self.primary_tap is not None:
            self.primary_tap.setAlphaValue_(1.0 if view["primary"]["enabled"] else 0.35)
            self.primary_tap.callback = self._primary
        if self.hint is not None:
            self.hint.setStringValue_(view["name"]["hint"])

    def open_rehearsal(self):
        if self.panel.open or self.setup.step != "try":
            return
        self.panel.show("LMemM setup", self._rehearsed)

    def _rehearsed(self, text):
        """The rehearsal card closed. A note that was actually written counts; nothing is stored."""
        if text:
            self.setup.rehearsed()
        self.render()

    # ------------------------------------------------------------ drawing

    def render(self):
        for sub in list(self.root.subviews()):
            sub.removeFromSuperview()
        self.name_field = self.primary_tap = self.hint = None
        view = self.setup.view()
        self.signature = self._signature()
        root = self.root
        dots = _Dots.alloc().initWithIndex_(view["index"])
        dots.setFrame_(NSMakeRect((W - 65) / 2, 24, 65, 8))
        root.addSubview_(dots)
        if view["back"]:
            self._link(root, "‹ Back", 18, 16, lambda: self._do(self.setup.back))
        step = view["step"]
        y = {"welcome": self._intro, "done": self._intro, "you": self._you, "access": self._access,
             "try": self._try}[step](root, view)
        self._foot(root, view)
        if self.picker is not None:
            self._picker_view()
        elif step == "you":
            self.window.makeFirstResponder_(self.name_field)
        return y

    def _text(self, parent, text, y, size=14, bold=False, color=None, x=X, w=CW, gap=0):
        field, h = _label(text, size, bold=bold, color=color or NSColor.labelColor(), frame=(x, y, w, 20), wrap=True)
        parent.addSubview_(field)
        return y + h + gap

    def _link(self, parent, text, x, y, callback, color=None, w=None):
        label, h = _label(text, 13, color=color or NSColor.secondaryLabelColor(), frame=(0, 3, 10, 16))
        width = w or widget._text_width(text, NSFont.systemFontOfSize_(13)) + 16
        tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, width, 24), callback)
        label.setFrame_(NSMakeRect(8, 3, width - 8, 16))
        tap.addSubview_(label)
        parent.addSubview_(tap)
        return tap

    def _button(self, parent, text, x, y, w, h, callback, kind="primary", enabled=True, size=16):
        tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, h), callback if enabled else (lambda: None))
        if kind == "primary":
            tap.tint = _accent()
        else:
            tap.fill = True
        color = NSColor.whiteColor() if kind == "primary" else NSColor.labelColor()
        label, lh = _label(text, size, bold=True, color=color, frame=(0, (h - 20) / 2, w, 20))
        label.setAlignment_(2)
        label.setFrame_(NSMakeRect(0, (h - lh) / 2, w, lh))
        tap.addSubview_(label)
        tap.setAlphaValue_(1.0 if enabled else 0.35)
        parent.addSubview_(tap)
        return tap

    def _foot(self, root, view):
        y = H - 148
        if view["trust"]:
            lock = _symbol("lock.fill")
            if lock is not None:
                holder = NSImageView.alloc().initWithFrame_(NSMakeRect(X, y + 1, 12, 14))
                holder.setImage_(lock)
                holder.setContentTintColor_(NSColor.systemGreenColor())
                root.addSubview_(holder)
            self._text(root, view["trust"], y, 12, color=NSColor.secondaryLabelColor(), x=X + 20, w=CW - 20)
        if view["error"]:
            self._text(root, view["error"], y - 20, 12, color=NSColor.systemRedColor())
        primary = view["primary"]
        if primary:
            quiet = primary["quiet"]
            self.primary_tap = self._button(root, primary["label"], X, H - 112, CW, 48, self._primary,
                                            kind="quiet" if quiet else "primary", enabled=primary["enabled"])
        if view["secondary"]:
            self._link(root, view["secondary"]["label"], (W - 100) / 2, H - 52, self._secondary, w=100)

    # -- the five screens

    def _intro(self, root, view):
        mark = _Mark.alloc().initWithFrame_(NSMakeRect(X, 96, 60, 60))
        root.addSubview_(mark)
        y = self._text(root, view["title"], 184, 28, bold=True, gap=12)
        y = self._text(root, view["sub"], y, 16, color=NSColor.secondaryLabelColor(), gap=16)
        for note in view["notes"]:
            color = NSColor.systemOrangeColor() if note["tone"] == "warn" else NSColor.secondaryLabelColor()
            y = self._text(root, note["text"], y, 13, color=color, gap=8)
        return y

    def _you(self, root, view):
        y = self._text(root, view["title"], 78, 28, bold=True, gap=22)
        box = _Box.alloc().initWithFrame_(NSMakeRect(X, y, CW, 48))
        root.addSubview_(box)
        self.name_field = _field(view["name"]["value"], view["name"]["placeholder"], 20, False,
                                 (X + 14, y + 11, CW - 28, 26), self.fields)
        root.addSubview_(self.name_field)
        y += 56
        self.hint, _ = _label(view["name"]["hint"], 12, color=NSColor.secondaryLabelColor(), frame=(X, y, CW, 16))
        root.addSubview_(self.hint)
        y += 34
        label, h = _label("What do you mostly work on?  Optional", 13, bold=True, frame=(X, y, CW, 16))
        root.addSubview_(label)
        y += 26
        x, row_y = X, y
        for role in view["roles"]:
            width = widget._text_width(role["name"], NSFont.systemFontOfSize_(14)) + 28
            if x + width > X + CW:
                x, row_y = X, row_y + 34
            chip = self._button(root, role["name"], x, row_y, width, 28, (lambda r=role["name"]: self._do(self.setup.toggle_role, r)),
                                kind="quiet", size=14)
            if role["on"]:
                chip.tint, chip.fill = NSColor.labelColor(), False
                chip.subviews()[0].setTextColor_(NSColor.windowBackgroundColor())
            x += width + 7
        y = row_y + 44
        self._link(root, "What gets saved ▾" if not self.show_saved else "What gets saved ▴", X - 8, y,
                   lambda: (setattr(self, "show_saved", not self.show_saved), self.render()))
        if self.show_saved:
            y += 28
            for line in view["saved"]:
                y = self._text(root, "•  " + line, y, 12, color=NSColor.secondaryLabelColor(), gap=2)
        return y

    def _access(self, root, view):
        y = self._text(root, view["title"], 66, 28, bold=True, gap=14)
        for row in view["rows"]:
            y = self._permission(root, row, view, y)
        return y

    def _permission(self, root, row, view, y):
        state = row["state"]
        tone = "good" if state == onboarding.GRANTED else "bad" if state == onboarding.DENIED else "soft"
        tile = _Tile.alloc().initWithSymbol_tone_(ICON_SYMBOLS[row["key"]], tone)
        tile.setFrame_(NSMakeRect(X, y + 4, 34, 34))
        root.addSubview_(tile)
        text_x, button_w = X + 46, 134
        text_w = CW - 46 - button_w - 10
        head = row["title"] + (f"   {row['tag']}" if row["tag"] else "")
        ty = self._text(root, head, y + 2, 15, bold=True, x=text_x, w=text_w)
        color = NSColor.systemRedColor() if state == onboarding.DENIED else \
            NSColor.systemOrangeColor() if state == onboarding.RESTART else NSColor.secondaryLabelColor()
        ty = self._text(root, row["line"], ty, 12, color=color, x=text_x, w=text_w, gap=2)
        if row["key"] == "screen":
            some = bool(view["watch_apps"])
            seg_y = ty + 4
            for i, (label, active, cb) in enumerate((("All apps", not some, lambda: self._do(self.setup.set_apps, [])),
                                                       ("Only some apps", some, self._open_picker))):
                width = 82 if i == 0 else 108
                tap = self._button(root, label, text_x + (0 if i == 0 else 86), seg_y, width, 24, cb,
                                   kind="quiet", size=12)
                if active:
                    tap.tint, tap.fill = NSColor.labelColor(), False
                    tap.subviews()[0].setTextColor_(NSColor.windowBackgroundColor())
            ty = seg_y + 28
        if row["action"]:
            self._button(root, row["button"], X + CW - button_w, y + 5, button_w, 30,
                         (lambda a=row["action"], k=row["key"]: self._do(self.setup.press, a, k)),
                         kind="primary" if row["action"] == "restart" else "quiet", size=12)
        else:
            label, _ = _label("✓ On", 13, bold=True, color=NSColor.systemGreenColor(),
                              frame=(X + CW - button_w, y + 10, button_w, 20))
            label.setAlignment_(1)
            root.addSubview_(label)
        return max(ty, y + 44) + 14

    def _try(self, root, view):
        y = self._text(root, view["title"], 78, 28, bold=True, gap=22)
        for i, key in enumerate(view["keys"]):
            cap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(X + i * 62, y, 54, 54), lambda: None)
            cap.fill = True
            label, _ = _label(key, 22, bold=True, frame=(0, 13, 54, 28))
            label.setAlignment_(2)
            cap.addSubview_(label)
            root.addSubview_(cap)
        y += 74
        y = self._text(root, view["sub"], y, 15, color=NSColor.secondaryLabelColor(), gap=14)
        for note in view["notes"]:
            y = self._text(root, note["text"], y, 14, color=NSColor.systemGreenColor(), gap=8)
        return y

    # -- the app picker (Screen Recording, only some apps)

    def _open_picker(self):
        listing = apps.installed()
        chosen = [a["id"] for a in self.setup.state["watch_apps"]]
        self.picker = {"all": listing, "chosen": chosen, "query": "", "scroll": None, "count": None, "done": None}
        self.render()

    def _picker_view(self):
        state = self.picker
        sheet = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        sheet.setMaterial_(POPOVER_MATERIAL)
        sheet.setBlendingMode_(BEHIND_WINDOW)
        sheet.setState_(ACTIVE)
        body = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        sheet.addSubview_(body)
        y = self._text(body, "Where should LMemM look?", 40, 24, bold=True, gap=8)
        y = self._text(body, "Apps installed on this Mac. LMemM looks only at the ones you pick and stays off in every other app.",
                       y, 13, color=NSColor.secondaryLabelColor(), gap=14)
        box = _Box.alloc().initWithFrame_(NSMakeRect(X, y, CW, 36))
        body.addSubview_(box)
        search = _field(state["query"], "Search apps", 14, False, (X + 12, y + 8, CW - 24, 20),
                        _Fields.alloc().initWithChange_submit_cancel_(self._query, lambda _t: None, lambda: None))
        body.addSubview_(search)
        y += 46
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(X, y, CW, H - y - 120))
        scroll.setDrawsBackground_(False)
        scroll.setHasVerticalScroller_(True)
        state["scroll"] = scroll
        body.addSubview_(scroll)
        self._fill_picker()
        state["done"] = self._button(body, "", X, H - 100, CW, 46, self._picker_done)
        self._link(body, "Allow all apps instead", (W - 150) / 2, H - 46, self._picker_all, w=150)
        self._update_picker_button()
        self.root.addSubview_(sheet)

    def _query(self, text):
        self.picker["query"] = text
        self._fill_picker()

    def _fill_picker(self):
        state = self.picker
        rows = apps.search(state["all"], state["query"])
        doc = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, CW, max(1, len(rows)) * 40))
        if not rows:
            label, _ = _label(f"No app named “{state['query']}”.", 13, color=NSColor.secondaryLabelColor(),
                              frame=(8, 10, CW - 16, 18))
            doc.addSubview_(label)
        for i, app in enumerate(rows):
            tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(0, i * 40, CW, 40), (lambda a=app: self._toggle_app(a)))
            icon = self._icon(app)
            if icon is not None:
                holder = NSImageView.alloc().initWithFrame_(NSMakeRect(6, 6, 28, 28))
                holder.setImage_(icon)
                tap.addSubview_(holder)
            label, _ = _label(app["name"], 14, frame=(46, 11, CW - 46 - 40, 18))
            tap.addSubview_(label)
            ring = _Ring.alloc().initWithChecked_(app["id"] in state["chosen"])
            ring.setFrame_(NSMakeRect(CW - 30, 11, 17, 17))
            tap.addSubview_(ring)
            doc.addSubview_(tap)
        state["scroll"].setDocumentView_(doc)

    def _icon(self, app):
        if app["id"] not in self.icons:
            try:
                image = NSWorkspace.sharedWorkspace().iconForFile_(app["path"])
                image.setSize_((28, 28))
            except Exception:
                image = None
            self.icons[app["id"]] = image
        return self.icons[app["id"]]

    def _toggle_app(self, app):
        chosen = self.picker["chosen"]
        if app["id"] in chosen:
            chosen.remove(app["id"])
        else:
            chosen.append(app["id"])
        self._fill_picker()
        self._update_picker_button()

    def _update_picker_button(self):
        tap, n = self.picker["done"], len(self.picker["chosen"])
        tap.subviews()[0].setStringValue_(f"Use {n} app{'s' * (n != 1)}" if n else "Pick at least one app")
        tap.setAlphaValue_(1.0 if n else 0.35)

    def _picker_done(self):
        state = self.picker
        if not state["chosen"]:
            return
        known = {a["id"]: {"id": a["id"], "name": a["name"]} for a in state["all"]}
        for kept in self.setup.state["watch_apps"]:                      # an app no longer installed stays chosen
            known.setdefault(kept["id"], kept)
        self.setup.set_apps([known[i] for i in state["chosen"] if i in known])
        self.picker = None
        self.render()

    def _picker_all(self):
        self.setup.set_apps([])
        self.picker = None
        self.render()


def run():
    """Show first-run setup until it is finished or the window is closed. True when finished.
    A restart (Screen Recording) replaces this process; the next one resumes on the same screen."""
    p = config.paths()
    system = permissions.MacSystem()
    setup = onboarding.Setup(system, p.onboarding_file)
    if setup.completed:
        return True
    app = dictation.start_app()
    dictation.ensure_listener()                       # build the speech helper now, so the voice row can ask
    system.start()
    window = SetupWindow(setup)
    dictation.register_hotkey(window.hotkey)
    window.show()
    try:
        while not window.closed and not setup.completed:
            macos.next_event(app, 0.1)
            window.tick()
    finally:
        dictation.release_hotkey()
        window.close()
        system.stop()
    return setup.completed
