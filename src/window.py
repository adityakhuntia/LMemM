"""LMemM - the main window. It draws window_model.view() (the state banner) and
page_model.view() (the project page), and forwards presses; it decides nothing (S8, W1-W6 in
window_model.py, P1-P8 in page_model.py). Only the drawing is here, so a Mac is needed to look at it.

Layout: the banner across the top when there is one; under it the sidebar (search, Needs you, the
project tree) and the page. The search field is built once and never rebuilt, so typing is never
interrupted by a redraw; the two scrolling areas keep their place when the data underneath changes.
"""

import sys
import time
import traceback

from Foundation import NSObject
from AppKit import (NSApplication, NSBezierPath, NSColor, NSImageView, NSMakePoint, NSMakeRect, NSScrollView, NSTextField,
                    NSStrikethroughStyleAttributeName, NSWindow, NSWorkspace)

import apps
import notes
import page_model
import project_actions
import rules
import setup_kit as kit
import thing_actions
import window_model
from setup_kit import LEFT, RIGHT
from widget import _Fields, _Flipped, _Ring, _Tap

W, H = 1080, 720
SIDE_W = 250
PAD = 32
MAIN_W = W - SIDE_W - 2 * PAD
TOP = 32                                               # below the title bar
TONES = {"red": "red", "grey": None, "calm": None}      # the banner box's tone (red is only for what is off)


def hue_color(hue):
    """The eight calm colours projects wear. Never red: red is only for a permission that is off."""
    names = ("systemBlue", "systemPurple", "systemPink", "systemOrange", "systemTeal", "systemGreen",
             "systemIndigo", "systemBrown")
    return getattr(NSColor, names[hue % len(names)] + "Color")()


class _MainWindow(NSWindow):
    def canBecomeKeyWindow(self):
        return True


class _MainClosing(NSObject):
    """A closed window is only hidden; it opens again from the menu."""

    def windowShouldClose_(self, window):
        window.orderOut_(None)
        return False


class _SideBackdrop(_Flipped):
    """The sidebar's soft tint and the hairline between it and the page."""

    def drawRect_(self, rect):
        kit.faint(0.035).setFill()
        NSBezierPath.fillRect_(self.bounds())
        kit.faint(0.09).setFill()
        NSBezierPath.fillRect_(NSMakeRect(self.bounds().size.width - 1, 0, 1, self.bounds().size.height))


class _Bar(_Flipped):
    """A thin accent bar beside a quoted decision."""

    def drawRect_(self, rect):
        kit.accent().setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 1.5, 1.5).fill()


def _scroll(parent):
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    scroll.setDrawsBackground_(False)
    scroll.setHasVerticalScroller_(True)
    scroll.setAutohidesScrollers_(True)
    scroll.setScrollerStyle_(1)                                   # overlay: thin, over the content's empty edge, never beside it
    scroll.setBorderType_(0)
    parent.addSubview_(scroll)
    return scroll


class MainWindow:
    """on_press(row id) is called when the banner's button is pressed (ids the menu already knows).
    data() returns (project registry, things by id) for the page."""

    def __init__(self, on_press, data, on_tick=None, on_add_note=None, on_project=None, on_project_undo=None, suggest=None):
        self.on_press = on_press
        self.data = data
        self.on_tick = on_tick or (lambda ids, done: None)               # tick or reopen notes (the pill's own function)
        self.on_add_note = on_add_note or (lambda item_id, text: None)
        self.on_project = on_project                                   # (action, args) -> {"message", "go", "undo"}; raises ValueError
        self.on_project_undo = on_project_undo or (lambda undo: None)
        self.suggest = suggest or (lambda: None)                        # the proposals waiting (suggestions.view)
        self.dialog = None                                             # the question or form on screen, if any
        self.done = None                                               # {"message", "undo", "until"}: the last project change
        self.sel = None                                                # None, or the ids of the things ticked in Select mode
        self.flow = rules.FinishFlow()                                 # hold, fold, Undo: the pill's rules (R10)
        self.flow_sig = None
        self.item_here = None
        self.banner = None                                         # the last window_model.view
        self.nav = page_model.new_state()
        self.shown = None
        self.where = None                                          # (view, project, search) the page was last showing
        self.app_icons = {}
        self.app_paths = None
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
        backdrop = _SideBackdrop.alloc().initWithFrame_(NSMakeRect(0, 0, SIDE_W, H))
        self.root.addSubview_(backdrop)
        self.banner_host = _Flipped.alloc().initWithFrame_(NSMakeRect(SIDE_W, TOP, W - SIDE_W, 0))
        self.root.addSubview_(self.banner_host)
        self.head_host = _Flipped.alloc().initWithFrame_(NSMakeRect(SIDE_W, TOP, W - SIDE_W, 0))
        self.root.addSubview_(self.head_host)
        self.typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: self.press("search", text), lambda text: self.press("search", text), self._cancel_search)
        self.search = NSTextField.alloc().initWithFrame_(NSMakeRect(16, 0, SIDE_W - 32, 28))
        self.search.setPlaceholderString_("Search")
        self.search.setBezeled_(True)
        self.search.setBezelStyle_(1)
        self.search.setDelegate_(self.typing)
        self.root.addSubview_(self.search)
        self.side_scroll = _scroll(self.root)
        self.main_scroll = _scroll(self.root)
        self.note_typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: None, self._submit_note, lambda: self.note_field.setStringValue_(""))
        self.note_field = NSTextField.alloc().initWithFrame_(NSMakeRect(SIDE_W + PAD, H - 52, MAIN_W, 30))
        self.note_field.setPlaceholderString_("Add a note to this, then press Return")
        self.note_field.setBezeled_(True)
        self.note_field.setBezelStyle_(1)
        self.note_field.setDelegate_(self.note_typing)
        self.note_field.setHidden_(True)
        self.root.addSubview_(self.note_field)
        self.toast_host = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.toast_host.setHidden_(True)
        self.root.addSubview_(self.toast_host)
        self.side_foot = _Flipped.alloc().initWithFrame_(NSMakeRect(0, H - 48, SIDE_W, 48))
        self.root.addSubview_(self.side_foot)
        self.overlay = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        self.overlay.setHidden_(True)
        self.root.addSubview_(self.overlay)
        self.dlg_typing = _Fields.alloc().initWithChange_submit_cancel_(
            self._dialog_typed, lambda text: self._dialog_submit(), self.close_dialog)
        self.dlg_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.dlg_field.setBezeled_(True)
        self.dlg_field.setBezelStyle_(1)
        self.dlg_field.setDelegate_(self.dlg_typing)
        self.dlg_field.setHidden_(True)
        self.overlay.addSubview_(self.dlg_field)
        self.window.center()

    # ------------------------------------------------------------ the loop calls these

    def visible(self):
        return bool(self.window.isVisible())

    def show(self, banner):
        self.update(banner)
        self.window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def update(self, banner):
        """Redraw only when something a person would see has changed."""
        self.banner = banner
        self.render()

    def press(self, action, arg=None):
        reg, items = self.data()
        if action in {"go", "home", "needs"}:
            self.search.setStringValue_("")                        # leaving a search clears its words
        if action not in {"more", "more_subs", "more_side", "toggle"}:
            self.sel = None                                        # a selection belongs to the page it was made on
        self.nav = page_model.press(reg, self.nav, action, arg, items)
        self.render()

    def back(self, kind):
        if kind == "thing":
            self.press("back")
        elif kind == "search":
            self.press("clear")
        else:
            self.press("home")

    def tick(self):
        """Called a few times a second by the loop: a ticked note's hold and fold, and the Undo line,
        change with the clock, not with a press."""
        if self.visible():
            if self.flow_signature() != self.flow_sig:
                self.render()

    def flow_signature(self):
        """Everything that changes with the clock: a ticked note's hold, and the line at the bottom."""
        now = time.time()
        return (self.flow.signature(now), bool(self.done and now < self.done["until"]))

    def tick_note(self, nid, done):
        """One tap flips a note (R10). A note that is folding away ignores taps."""
        now = time.time()
        phase = self.flow.phase(nid, now)
        if phase == "fold":
            return
        self.on_tick([nid], done)
        left = self._open_left()
        if done:
            self.flow.tick(nid, now, left)
        elif phase == "hold":
            self.flow.cancel(nid, left)                            # changed your mind: no toast
        else:
            self.flow.reopened(now)
        self.render()

    def undo(self):
        ids = self.flow.undo(self._open_left())
        if ids:
            self.on_tick(ids, False)
        self.render()

    def _open_left(self):
        _reg, items = self.data()
        return sum(len(notes.open_notes(i)) for i in items.values())

    def _submit_note(self, text):
        text = " ".join((text or "").split())
        if text and self.item_here:
            self.on_add_note(self.item_here, text)
            self.note_field.setStringValue_("")
            self.render()

    def _cancel_search(self):
        self.search.setStringValue_("")
        self.press("clear")

    # ------------------------------------------------------------ drawing

    def render(self):
        """Draw the window. A failure here is printed and skipped: the window is never allowed to
        stop LMemM from remembering."""
        try:
            self._render()
        except Exception:
            self.shown = None
            print("window: could not draw the page:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    def _render(self):
        reg, items = self.data()
        now = time.time()
        page = page_model.view(reg, items, self.nav, fading=self.flow.holding(now), sugg=self.suggest())
        self.flow_sig = self.flow_signature()
        sig = repr((window_model.signature(self.banner), page, self.flow_sig, self.sel))
        if sig == self.shown:
            return
        self.shown = sig
        top = self._banner(self.banner["banner"])
        main = page["main"]
        split = main["kind"] == "project" and not main.get("empty")      # a project: its top stays put, Things scrolls
        head = self._head(main) if split else self._no_head()
        thing = main["kind"] == "thing"
        self.item_here = main.get("item") if thing else None
        self.note_field.setHidden_(not thing)
        bar = 62 if thing else 0                                   # the note field sits under the page
        self._toast(now, bar)
        self.search.setFrame_(NSMakeRect(16, TOP + 10, SIDE_W - 32, 28))
        self.side_scroll.setFrame_(NSMakeRect(0, TOP + 52, SIDE_W, H - TOP - 52 - 48))
        self._side_foot(page["side"])
        self.head_host.setFrame_(NSMakeRect(SIDE_W, top, W - SIDE_W, head))
        self.main_scroll.setFrame_(NSMakeRect(SIDE_W, top + head, W - SIDE_W, H - top - head - bar))
        here = (self.nav["view"], self.nav["pid"], self.nav["q"], self.nav["tid"])
        moved, self.where = here != self.where, here
        self._fill(self.side_scroll, SIDE_W, lambda doc: self._side(doc, page["side"]))
        self._fill(self.main_scroll, W - SIDE_W, lambda doc: self._main(doc, main, split), top=moved)

    def _fill(self, scroll, width, build, top=False):
        """Swap the scrolling area's contents, keeping the place the person had scrolled to (or
        going to the top when they have moved to another page)."""
        clip = scroll.contentView()
        keep = 0 if top else clip.bounds().origin.y
        doc = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, width, 10))
        height = build(doc)
        view_h = scroll.frame().size.height
        doc.setFrame_(NSMakeRect(0, 0, width, max(height + 24, view_h)))
        scroll.setDocumentView_(doc)
        clip.scrollToPoint_(NSMakePoint(0, max(0, min(keep, height + 24 - view_h))))
        scroll.reflectScrolledClipView_(clip)

    def _toast(self, now, bar):
        """"Marked done · Undo" while R10 says so: a small dark line at the bottom of the page."""
        for sub in list(self.toast_host.subviews()):
            sub.removeFromSuperview()
        toast = self.flow.toast(now)
        undo = self.undo
        if self.done and now < self.done["until"]:
            toast, undo = (self.done["message"], bool(self.done.get("undo"))), self.undo_project
        self.toast_host.setHidden_(toast is None)
        if toast is None:
            return
        text, undoable = toast
        width = min(kit.text_width(text, 13, 500) + (74 if undoable else 36), MAIN_W)
        self.toast_host.setFrame_(NSMakeRect(SIDE_W + (W - SIDE_W - width) / 2, H - bar - 54, width, 36))
        pill = self._tap(self.toast_host, 0, 0, width, 36, lambda: None)
        pill.tint = NSColor.colorWithWhite_alpha_(0.12, 0.94)
        kit.put_text(pill, text, 18, 0, width - 36, 13, 500, NSColor.whiteColor(), wrap=False, height=36, middle=True)
        if undoable:
            link = self._tap(pill, width - 62, 0, 56, 36, undo)
            kit.put_text(link, "Undo", 0, 0, 56, 13, 600, NSColor.colorWithRed_green_blue_alpha_(0.55, 0.75, 1.0, 1.0),
                         align=kit.CENTER, wrap=False, height=36, middle=True)

    BANNER_SYMBOLS = {"paused:manual": "pause.circle.fill", "paused:away": "moon.zzz.fill", "screen_off": "exclamationmark.circle.fill",
                      "mic_off": "mic.slash.fill", "restart": "arrow.clockwise.circle.fill", "private": "lock.fill",
                      "unwatched": "eye.slash.fill", "first_run": "sparkles", "loading": "hourglass",
                      "damaged": "exclamationmark.triangle.fill"}

    def _banner(self, banner):
        """The one state banner: a soft box in the page's own column, its words on the left and
        its one button on the right. Returns where the page starts."""
        for sub in list(self.banner_host.subviews()):
            sub.removeFromSuperview()
        if not banner:
            self.banner_host.setFrame_(NSMakeRect(SIDE_W, TOP, W - SIDE_W, 0))
            return TOP
        button = banner["button"]
        room = MAIN_W - (176 if button else 0)
        symbol = self.BANNER_SYMBOLS.get(banner["kind"], "info.circle.fill")
        height = kit.note(self.banner_host, TONES[banner["tone"]], banner["line"], PAD, 0, room,
                          lead=banner["title"], symbol=symbol)
        if button:
            row = button["id"]
            kit.button(self.banner_host, button["title"], PAD + room + 12, (height - 36) / 2, 164, 36,
                       lambda: self.on_press(row), kind="outline", size=13, weight=600)
        self.banner_host.setFrame_(NSMakeRect(SIDE_W, TOP + 6, W - SIDE_W, height))
        return TOP + 6 + height + 6

    # ------------------------------------------------------------ changing projects

    def project_action(self, action, **args):
        """Do a project change now. Returns True when it worked; on a ValueError the sentence is shown."""
        if self.on_project is None:
            return False
        try:
            result = self.on_project(action, args)
        except ValueError as error:
            if self.dialog:
                self.dialog["error"] = str(error)
                self._dialog()
            else:
                self.done = {"message": str(error), "undo": None, "until": time.time() + 5}
                self.render_now()
            return False
        self.close_dialog()
        self.done = {"message": result["message"], "undo": result["undo"], "until": time.time() + 8}
        if result.get("stay"):                                     # a change to things: the page stays where it is
            self.sel = None
            self.render_now()
            return True
        self.press("go", result["go"]) if result["go"] else self.press("home")
        self.render_now()
        return True

    def render_now(self):
        self.shown = None
        self.render()

    def undo_project(self):
        if self.done and self.done.get("undo"):
            self.on_project_undo(self.done["undo"])
        self.done = None
        self.render_now()

    def _reg(self):
        return self.data()[0]

    def open_name(self, action, pid=None, parent=None):
        reg = self._reg()
        title = {"new": "New project" if parent is None else f"New sub-project in “{reg['projects'][parent]['name']}”",
                 "rename": "Rename project"}[action]
        self.dialog = {"kind": "name", "action": action, "pid": pid, "parent": parent, "title": title, "error": "",
                       "value": reg["projects"][pid]["name"] if action == "rename" else ""}
        self._dialog(focus=True)

    def open_menu(self, pid):
        self.dialog = {"kind": "menu", "pid": pid}
        self._dialog()

    def open_pick(self, action, pid):
        self.dialog = {"kind": "pick", "action": action, "pid": pid, "query": "", "error": ""}
        self._dialog(focus=True)

    def open_ask(self, action, pid, target=None):
        reg, items = self.data()
        try:
            asking = project_actions.plan(reg, items, action, pid, target)
        except ValueError as error:
            self.dialog = {"kind": "ask", "action": action, "pid": pid, "target": target, "error": str(error),
                           "plan": {"title": "That can't be done", "text": str(error), "button": None}}
        else:
            self.dialog = {"kind": "ask", "action": action, "pid": pid, "target": target, "error": "", "plan": asking}
        self._dialog()

    def thing_action(self, action, ids, pid=None):
        """Do something to things (thing_actions.py); the page they are on stays."""
        return self.project_action(action, ids=list(ids), pid=pid, here=self.nav["pid"])

    def open_thing_menu(self, ids):
        self.dialog = {"kind": "tmenu", "ids": list(ids)}
        self._dialog()

    def open_thing_pick(self, action, ids):
        self.dialog = {"kind": "tpick", "action": action, "ids": list(ids), "query": "", "error": ""}
        self._dialog(focus=True)

    def open_thing_forget(self, ids):
        reg, items = self.data()
        try:
            asking = thing_actions.plan_forget(items, ids)
        except ValueError as error:
            asking = {"title": "That can't be done", "text": str(error), "button": None}
        self.dialog = {"kind": "task", "ids": list(ids), "plan": asking}
        self._dialog()

    def answer(self, action, sid, ids=(), name=None):
        """Answer a suggestion (suggestions.py): Create, Dismiss, Add, Not here."""
        return self.project_action(action, sid=sid, ids=list(ids), name=name)

    def start_select(self):
        self.sel = []
        self.render_now()

    def stop_select(self):
        self.sel = None
        self.render_now()

    def pick_thing(self, tid):
        if self.sel is None:
            return
        self.sel = [i for i in self.sel if i != tid] if tid in self.sel else self.sel + [tid]
        self.render_now()

    def close_dialog(self):
        self.dialog = None
        self._dialog()

    def _dialog_typed(self, text):
        if self.dialog and self.dialog["kind"] in ("pick", "tpick"):
            self.dialog["query"] = text
            self._dialog()

    def _dialog_submit(self):
        d = self.dialog
        if not d or d["kind"] != "name":
            return
        name = self.dlg_field.stringValue()
        if d["action"] == "new":
            self.project_action("new", name=name, parent=d["parent"])
        else:
            self.project_action("rename", pid=d["pid"], name=name)

    def _dialog(self, focus=False):
        """Draw the question or form over the page (or take it away). The text field is built once
        and only moved, so typing is never interrupted."""
        for sub in list(self.overlay.subviews()):
            if sub is not self.dlg_field:
                sub.removeFromSuperview()
        d = self.dialog
        self.overlay.setHidden_(d is None)
        self.dlg_field.setHidden_(True)
        if d is None:
            return
        self._tap(self.overlay, 0, 0, W, H, self.close_dialog).tint = NSColor.colorWithWhite_alpha_(0.0, 0.32)
        cw, cx, cy = 460, (W - 460) / 2, 120
        card = self._tap(self.overlay, cx, cy, cw, 100, lambda: None)
        card.tint = kit.card_background()
        reg = self._reg()
        y = 24
        if d["kind"] == "name":
            kit.put_text(card, d["title"], 24, y, cw - 48, 18, 700, wrap=False, height=26)
            y += 42
            self._field_at(cx + 24, cy + y, cw - 48, d["value"] if focus else None, "Name")
            y += 44
            if d["error"]:
                y += kit.put_text(card, d["error"], 24, y, cw - 48, 13, 500) + 12
            y = self._dialog_buttons(card, cw, y + 6, "Cancel", "Save" if d["action"] == "rename" else "Make project", self._dialog_submit)
        elif d["kind"] == "menu":
            name = reg["projects"][d["pid"]]["name"]
            kit.put_text(card, name, 24, y, cw - 48, 18, 700, wrap=False, height=26)
            y += 40
            for label, symbol, call in (
                    ("Rename…", "pencil", lambda: self.open_name("rename", d["pid"])),
                    ("Move to…", "arrow.turn.down.right", lambda: self.open_pick("move", d["pid"])),
                    ("Merge into…", "arrow.triangle.merge", lambda: self.open_pick("merge", d["pid"])),
                    ("Archive", "archivebox", lambda: (self.close_dialog(), self.project_action("archive", pid=d["pid"]))),
                    ("Delete…", "trash", lambda: self.open_ask("delete", d["pid"]))):
                row = self._tap(card, 12, y, cw - 24, 40, call)
                kit.tile(row, (symbol, "circle"), kit.ink(), 8, 7, 26)
                kit.put_text(row, label, 46, 0, cw - 24 - 60, 14, 500, wrap=False, height=40, middle=True)
                y += 42
            y += 12
        elif d["kind"] == "pick":
            name = reg["projects"][d["pid"]]["name"]
            kit.put_text(card, (f"Move “{name}” to…" if d["action"] == "move" else f"Merge “{name}” into…"), 24, y, cw - 48, 18, 700, wrap=False, height=26)
            y += 42
            self._field_at(cx + 24, cy + y, cw - 48, "" if focus else None, "Search projects")
            y += 44
            found = project_actions.targets(reg, d["pid"], d["action"], d["query"])
            y = self._place_rows(card, cw, y, found, self._picked)
            y = self._dialog_buttons(card, cw, y + 10, "Cancel", None, None)
        elif d["kind"] == "tmenu":
            reg, items = self.data()
            found = [items[i] for i in d["ids"] if i in items]
            one = found[0] if len(found) == 1 else None
            title = f"“{page_model.title_of(one)}”" if one else page_model.plural(len(found), "thing")
            kit.put_text(card, title, 24, y, cw - 48, 18, 700, wrap=False, height=26)
            y += 40
            rows = [("Move to…", "arrow.turn.down.right", lambda: self.open_thing_pick("assign", d["ids"])),
                    ("Also in…", "plus.circle", lambda: self.open_thing_pick("also", d["ids"]))]
            if one:
                for p in thing_actions.homes(reg, one)[:4]:
                    rows.append((f"Not in “{p['name']}”", "minus.circle",
                                 (lambda i=p["id"]: (self.close_dialog(), self.thing_action("not_this", d["ids"], i)))))
            rows.append(("Forget this…", "trash", lambda: self.open_thing_forget(d["ids"])))
            for label, symbol, call in rows:
                row = self._tap(card, 12, y, cw - 24, 40, call)
                kit.tile(row, (symbol, "circle"), kit.ink(), 8, 7, 26)
                kit.put_text(row, label, 46, 0, cw - 24 - 60, 14, 500, wrap=False, height=40, middle=True)
                y += 42
            y += 12
        elif d["kind"] == "tpick":
            reg, items = self.data()
            many = len(d["ids"]) > 1
            what = page_model.plural(len(d["ids"]), "thing") if many else "this"
            kit.put_text(card, (f"Move {what} to…" if d["action"] == "assign" else f"Also put {what} in…"), 24, y, cw - 48, 18, 700,
                         wrap=False, height=26)
            y += 42
            self._field_at(cx + 24, cy + y, cw - 48, "" if focus else None, "Search projects")
            y += 44
            found = thing_actions.places(reg, items, d["ids"], d["action"], d["query"])
            y = self._place_rows(card, cw, y, found, (lambda t: self.thing_action(d["action"], d["ids"], t)))
            y = self._dialog_buttons(card, cw, y + 10, "Cancel", None, None)
        elif d["kind"] == "task":
            plan = d["plan"]
            y += kit.put_text(card, plan["title"], 24, y, cw - 48, 17, 700) + 10
            y += kit.put_text(card, plan["text"], 24, y, cw - 48, 13, 400, kit.mute()) + 18
            action = lambda: self.thing_action("forget", d["ids"])
            y = self._dialog_buttons(card, cw, y, "Cancel", plan["button"], action if plan["button"] else None)
        elif d["kind"] == "ask":
            plan = d["plan"]
            y += kit.put_text(card, plan["title"], 24, y, cw - 48, 17, 700) + 10
            y += kit.put_text(card, plan["text"], 24, y, cw - 48, 13, 400, kit.mute()) + 18
            action = lambda: self.project_action(d["action"], pid=d["pid"], target=d["target"])
            y = self._dialog_buttons(card, cw, y, "Cancel", plan["button"], action if plan["button"] else None)
        card.setFrame_(NSMakeRect(cx, cy, cw, y + 22))
        if not self.dlg_field.isHidden():                          # the field was added first: bring it above the backdrop and card
            self.dlg_field.removeFromSuperview()
            self.overlay.addSubview_(self.dlg_field)
        if focus:
            self.window.makeFirstResponder_(self.dlg_field)

    def _place_rows(self, card, cw, y, found, call):
        """The list of places in a picker (rows of {"id", "name", "path"}), then "n more". Returns y."""
        for r in found["rows"][:7]:
            row = self._tap(card, 12, y, cw - 24, 44, (lambda t=r["id"]: call(t)))
            if r["id"] is None:
                kit.tile(row, ("arrow.up.to.line", "tray.fill"), kit.ink(), 8, 7, 30)
            else:
                self._project_icon(row, page_model.hue(r["id"]), 8, 7, 30)
            kit.put_text(row, r["name"], 48, 4, cw - 24 - 60, 14, 600, wrap=False, height=20)
            kit.put_text(row, r["path"], 48, 23, cw - 24 - 60, 12, 400, kit.mute(), wrap=False, height=16)
            y += 46
        left = found["more"] + max(0, len(found["rows"]) - 7)
        if left:
            kit.put_text(card, f"{left} more. Keep typing to narrow it.", 24, y + 2, cw - 48, 12, 400, kit.mute(), wrap=False, height=18)
            y += 26
        if not found["rows"]:
            kit.put_text(card, "No place to put it there.", 24, y + 2, cw - 48, 13, 400, kit.mute(), wrap=False, height=20)
            y += 28
        return y

    def _field_at(self, x, y, w, value, placeholder):
        """Move the one text field into the dialog. `value` replaces its text; None leaves what was typed."""
        self.dlg_field.setFrame_(NSMakeRect(x, y, w, 30))
        self.dlg_field.setPlaceholderString_(placeholder)
        if value is not None:
            self.dlg_field.setStringValue_(value)
        self.dlg_field.setHidden_(False)

    def _dialog_buttons(self, card, cw, y, cancel, go, call):
        kit.button(card, cancel, cw - 24 - 110 - (8 + 140 if go else 0), y, 110, 36, self.close_dialog, kind="quiet", size=13, weight=600)
        if go:
            kit.button(card, go, cw - 24 - 140, y, 140, 36, call, kind="primary", size=13, weight=600)
        return y + 36

    def _picked(self, target):
        d = self.dialog
        if d["action"] == "move":
            self.project_action("move", pid=d["pid"], parent=target)
        else:
            self.open_ask("merge", d["pid"], target)

    # ------------------------------------------------------------ icons

    def _project_icon(self, parent, hue, x, y, size=26):
        kit.tile(parent, "folder.fill", hue_color(hue), x, y, size)

    def _app_icon(self, parent, app, x, y, size=30):
        """The app's own icon; a plain square when this Mac cannot find it."""
        image = self._app_image(app)
        if image is None:
            kit.tile(parent, ("doc.fill", "app.fill"), kit.mute(), x, y, size)
            return
        holder = NSImageView.alloc().initWithFrame_(NSMakeRect(x, y, size, size))
        holder.setImage_(image)
        holder.setImageScaling_(3)
        parent.addSubview_(holder)

    def _app_image(self, app):
        if app not in self.app_icons:
            image = None
            try:
                path = NSWorkspace.sharedWorkspace().fullPathForApplication_(app)
                if not path:
                    if self.app_paths is None:
                        self.app_paths = {a["name"]: a["path"] for a in apps.installed()}
                    path = self.app_paths.get(app)
                image = NSWorkspace.sharedWorkspace().iconForFile_(path) if path else None
            except Exception:
                image = None
            self.app_icons[app] = image
        return self.app_icons[app]

    # ------------------------------------------------------------ small pieces

    def _tap(self, parent, x, y, w, h, callback, fill=False):
        tap = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, h), callback)
        tap.fill = fill
        parent.addSubview_(tap)
        return tap

    def _label(self, parent, text, x, y, w, size=12, weight=600, color=None, align=LEFT):
        kit.put_text(parent, text, x, y, w, size, weight, color or kit.mute(), align=align, wrap=False, height=size + 6)

    def _link(self, parent, text, x, y, callback, size=13, color=None):
        """Quiet clickable text. Returns its width."""
        width = kit.text_width(text, size, 500) + 12
        tap = self._tap(parent, x, y, width, size + 12, callback)
        kit.put_text(tap, text, 6, 0, width - 12, size, 500, color or kit.mute(), wrap=False, height=size + 12, middle=True)
        return width

    def _chips(self, parent, x, y, items):
        """Small buttons side by side; items are (label, on, callback). Returns the height."""
        for label, on, callback in items:
            width = kit.text_width(label, 13, 500) + 26
            kit.button(parent, label, x, y, width, 28, callback, kind="primary" if on else "quiet", size=13, weight=500)
            x += width + 6
        return 28

    # ------------------------------------------------------------ the sidebar

    def _side(self, doc, side):
        y = 6
        needs = side["needs"]
        self._label(doc, "NEEDS YOU", 16, y, 130)
        if needs["count"]:
            self._link(doc, f"See all {needs['count']}", SIDE_W - 96, y - 6, lambda: self.press("needs"), size=12)
        y += 24
        for row in needs["rows"]:
            tap = self._tap(doc, 8, y, SIDE_W - 16, 34, (lambda r=row: self.press("thing", r["id"])))
            self._app_icon(tap, row["app"], 8, 5, 24)
            kit.put_text(tap, row["title"], 40, 0, SIDE_W - 16 - 40 - 40, 13, 500, wrap=False, height=34, middle=True)
            kit.put_text(tap, str(row["open"]), SIDE_W - 16 - 34, 0, 26, 12, 500, kit.mute(), align=RIGHT, wrap=False, height=34, middle=True)
            y += 34
        if not needs["count"]:
            self._label(doc, "Nothing waiting.", 16, y, SIDE_W - 32, size=13, weight=400)
            y += 26
        y += 14
        self._label(doc, "PROJECTS", 16, y, 130)
        y += 24
        tree = side["tree"]
        for row in tree:
            x = 8 + min(row["level"], 9) * 14
            if row["id"] is None:                                  # "Show 8 more of 22"
                more = row["more"]
                self._link(doc, row["name"], x + 18, y, (lambda m=more: self.press("more_side", m)), size=12)
                y += 26
                continue
            call = (lambda: self.press("archived")) if row.get("folder") else (lambda r=row: self.press("go", r["id"]))
            tap = self._tap(doc, 8, y, SIDE_W - 16, 28, call, fill=row["selected"])
            if row["expandable"]:
                caret = self._tap(tap, x - 8, 0, 22, 28, (lambda r=row: self.press("toggle", r["id"])))
                kit.put_text(caret, "▾" if row["expanded"] else "▸", 0, 0, 22, 11, 600, kit.mute(), align=kit.CENTER,
                             wrap=False, height=28, middle=True)
            if row.get("folder"):
                kit.tile(tap, ("archivebox.fill", "tray.fill"), kit.mute(), x + 16, 4, 20)
            else:
                self._project_icon(tap, row["hue"], x + 16, 4, 20)
            kit.put_text(tap, row["name"], x + 42, 0, SIDE_W - 16 - x - 42 - 40, 13, 500,
                         kit.mute() if row.get("archived") else None, wrap=False, height=28, middle=True)
            if row["count"]:
                kit.put_text(tap, str(row["count"]), SIDE_W - 16 - 38, 0, 30, 12, 400, kit.mute(), align=RIGHT,
                             wrap=False, height=28, middle=True)
            y += 28
        if not tree:
            self._label(doc, "None yet. They appear as you work.", 16, y, SIDE_W - 32, size=13, weight=400)
            y += 26
        return y

    # ------------------------------------------------------------ the page

    def _main(self, doc, page, split=False):
        x, w = PAD, MAIN_W
        if split:
            return self._things(doc, page, x, 6, w)
        y = 30
        kind = page["kind"]
        if kind in ("search", "needs", "thing", "archived"):
            self._link(doc, "‹ Back", x - 6, y - 8, lambda: self.back(kind))
            y += 24
        if kind == "project":
            y = self._crumbs(doc, page["crumbs"], x, y)
        tx = x
        if kind == "project":
            self._project_icon(doc, page["hue"], x, y - 2, 40)
            tx = x + 54
        elif kind == "thing":
            self._app_icon(doc, page["app"], x, y - 2, 40)
            tx = x + 54
        elif kind in ("home", "needs", "archived"):
            kit.tile(doc, {"home": ("square.stack.3d.up.fill", "folder.fill"), "needs": ("bell.badge.fill", "bell.fill"),
                           "archived": ("archivebox.fill", "tray.fill")}[kind], kit.ink(), x, y - 2, 40)
            tx = x + 54
        kit.put_text(doc, page["title"], tx, y, w - (tx - x) - (170 if kind in ("project", "thing") else 0), 26, 700, wrap=False, height=34)
        y += 36
        if page.get("meta"):
            self._label(doc, page["meta"], tx, y, w - (tx - x), size=13, weight=400)
            y += 34
        if kind == "home":
            kit.button(doc, "+ New project", x + w - 150, 30, 150, 34, lambda: self.open_name("new"), kind="quiet", size=13, weight=600)
        if kind == "project":
            self._project_actions(doc, x + w, 28, page["pid"])
        if kind == "thing":
            self._thing_buttons(doc, x + w, 28, page["item"])
        build = {"home": self._home, "project": self._project, "needs": self._needs, "search": self._search,
                 "thing": self._thing_page, "archived": self._archived}[kind]
        return build(doc, page, x, y + 6, w)

    def _crumbs(self, doc, chain, x, y):
        cx = x - 6
        cx += self._link(doc, "All projects", cx, y - 12, lambda: self.press("home"), size=12)
        for i, c in enumerate(chain):
            self._label(doc, "›", cx, y - 8, 12, size=12, weight=400)
            cx += 12
            last = i == len(chain) - 1
            if c["id"] and not last:
                cx += self._link(doc, c["name"], cx, y - 12, (lambda p=c["id"]: self.press("go", p)), size=12)
            else:
                cx += self._link(doc, c["name"], cx, y - 12, lambda: None, size=12, color=kit.ink() if last else kit.mute())
        return y + 18

    def _section(self, doc, text, x, y, w):
        kit.put_text(doc, text, x, y, w, 15, 700, wrap=False, height=22)
        return y + 30

    def _empty(self, doc, empty, x, y, w, symbol=("tray.fill", "folder.fill")):
        kit.tile(doc, symbol, kit.mute(), x, y + 10, 56)
        kit.put_text(doc, empty["title"], x, y + 80, w, 18, 600, wrap=False, height=26)
        h = kit.put_text(doc, empty["line"], x, y + 112, min(w, 460), 14, 400, kit.mute())
        return y + 112 + h

    def _thing(self, doc, t, x, y, w, notes=False, select=False):
        """A thing: its title, where it is, when. With notes: the open ones underneath. While selecting,
        a tap ticks it instead of opening it. Returns the new y."""
        call = (lambda i=t["id"]: self.pick_thing(i)) if select else (lambda i=t["id"]: self.press("thing", i))
        box = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, 10), call)
        lead = 0
        if select:
            on = t["id"] in self.sel
            kit.tile(box, ("checkmark.circle.fill", "checkmark.circle") if on else ("circle", "circle"),
                     kit.ink() if on else kit.mute(), 0, 12, 22)
            lead = 32
        self._app_icon(box, t["app"], lead, 8, 34)
        tx = 46 + lead
        kit.put_text(box, t["title"], tx, 6, w - tx - 130, 14, 600, wrap=False, height=20)
        if t["ago"]:
            kit.put_text(box, t["ago"], w - 120, 6, 120, 12, 400, kit.mute(), align=RIGHT, wrap=False, height=20)
        kit.put_text(box, t["sub"], tx, 27, w - tx - (96 if t["open"] else 0), 12, 400, kit.mute(), wrap=False, height=18)
        if t["open"]:
            kit.put_text(box, f"{t['open']} open", w - 90, 27, 90, 12, 600, kit.ink(), align=RIGHT, wrap=False, height=18)
        h = 52
        if notes:
            for text in t.get("notes", []):
                h += kit.put_text(box, "○  " + text, tx, h - 2, w - tx, 13, 400, height=None) + 4
            if t.get("more_notes"):
                self._label(box, f"+{t['more_notes']} more", tx, h, w - tx, size=12, weight=400)
                h += 20
            h += 6
        box.setFrame_(NSMakeRect(x, y, w, h))
        doc.addSubview_(box)
        return y + h

    def _card(self, doc, t, x, y, w):
        """A pick-up card: a soft box with the thing and its open notes."""
        tap = self._tap(doc, x, y, w, 10, (lambda i=t["id"]: self.press("thing", i)), fill=True)
        end = self._thing(tap, t, 12, 4, w - 24, notes=True)
        tap.setFrame_(NSMakeRect(x, y, w, end + 6))
        return y + end + 6 + 10

    def _rows_of_projects(self, doc, rows, x, y, w):
        for r in rows:
            tap = self._tap(doc, x, y, w, 56, (lambda p=r["id"]: self.press("go", p)), fill=True)
            self._project_icon(tap, r["hue"], 12, 12, 32)
            kit.put_text(tap, r["name"], 56, 9, w - 70, 14, 600, wrap=False, height=20)
            kit.put_text(tap, r["line"], 56, 30, w - 70, 12, 400, kit.mute(), wrap=False, height=16)
            y += 64
        return y

    def _home(self, doc, page, x, y, w):
        if page.get("suggest"):
            y = self._suggest_home(doc, page["suggest"], x, y, w)
        if page["empty"]:
            return self._empty(doc, page["empty"], x, y, w)
        needs = page["needs"]
        if needs["count"]:
            y = self._section(doc, "Needs you", x, y, w)
            for row in needs["rows"]:
                y = self._card(doc, row, x, y, w)
            if needs["count"] > len(needs["rows"]):
                self._link(doc, f"See all {needs['count']}", x - 6, y - 4, lambda: self.press("needs"))
                y += 30
        y = self._section(doc, "Projects", x + 0, y + 6, w)
        y = self._rows_of_projects(doc, page["cards"], x, y, w)
        if page["unplaced"]:
            y += 6
            self._label(doc, f"{page['unplaced']:,} thing{'s' * (page['unplaced'] != 1)} not in a project yet.",
                        x, y, w, size=13, weight=400)
            y += 26
        return y

    def _suggest_home(self, doc, sug, x, y, w):
        """Proposals on the first page: projects to make (Create / Dismiss), and projects with things waiting."""
        y = self._section(doc, f"Suggestions · {sug['count']}", x, y, w)
        for e in sug["projects"]:
            y = self._card_box(doc, x, y, w, lambda box, inner, e=e: self._suggest_project(box, inner, e)) + 8
        for e in sug["items"]:
            tap = self._tap(doc, x, y, w, 56, (lambda p=e["pid"]: self.press("go", p)), fill=True)
            self._project_icon(tap, e["hue"], 12, 12, 32)
            n = e["count"]
            kit.put_text(tap, f"{n} thing{'s' * (n != 1)} may belong in “{e['name']}”", 56, 9, w - 56 - 110, 14, 600, wrap=False, height=20)
            kit.put_text(tap, e["line"], 56, 30, w - 56 - 110, 12, 400, kit.mute(), wrap=False, height=16)
            kit.button(tap, "Review", w - 94, 11, 82, 34, (lambda p=e["pid"]: self.press("go", p)), kind="outline", size=12, weight=600)
            y += 64
        return y + 14

    def _suggest_project(self, box, inner, e):
        """"Make “Trip” a project?" with the things that would go in it. Returns the inner height."""
        w = inner + 28
        kit.tile(box, ("sparkles", "wand.and.stars", "star.fill"), kit.ink(), 14, 12, 32)
        kit.put_text(box, f"Make “{e['name']}” a project?", 58, 12, w - 58 - 190, 14, 600, wrap=False, height=20)
        n = len(e["things"])
        kit.put_text(box, f"{n} things · {e['reason']}", 58, 32, w - 58 - 190, 12, 400, kit.mute(), wrap=False, height=16)
        kit.button(box, "Dismiss", w - 14 - 84 - 8 - 84, 14, 84, 32, (lambda: self.answer("dismiss_project", e["id"])), kind="quiet", size=13, weight=600)
        kit.button(box, "Create", w - 14 - 84, 14, 84, 32, (lambda: self.answer("accept_project", e["id"])), kind="primary", size=13, weight=600)
        top = 56
        for t in e["things"][:3]:
            kit.put_text(box, t["title"], 58, top, w - 58 - 14, 12, 500, wrap=False, height=18)
            top += 20
        if n > 3:
            kit.put_text(box, f"+{n - 3} more", 58, top, w - 58 - 14, 12, 400, kit.mute(), wrap=False, height=18)
            top += 20
        kit.put_text(box, "Dismiss it and LMemM will not suggest this again.", 58, top + 2, w - 58 - 14, 12, 400, kit.mute(), wrap=False, height=18)
        return top + 20 - 12

    def _suggested(self, doc, e, x, y, w):
        """On a project: things that may belong here, each with Add and Not here. Returns the new y."""
        n = len(e["things"])
        kit.put_text(doc, f"Suggested for this project · {n}", x, y, w, 15, 700, wrap=False, height=22)
        if n > 1:
            label = f"Add all {n}"
            self._link(doc, label, x + w - kit.text_width(label, 13, 500) - 12, y - 4, lambda: self.answer("accept_items", e["id"]))
        y += 30

        def rows(box, inner):
            top = 12
            for t in e["things"][:5]:
                call = (lambda i=t["id"]: self.press("thing", i))
                self._app_icon(box, t["app"], 14, top + 6, 30)
                open_it = self._tap(box, 54, top, inner + 28 - 54 - 190, 44, call)
                kit.put_text(open_it, t["title"], 0, 3, inner + 28 - 54 - 190, 14, 600, wrap=False, height=20)
                kit.put_text(open_it, t["sub"], 0, 23, inner + 28 - 54 - 190, 12, 400, kit.mute(), wrap=False, height=16)
                kit.button(box, "Not here", inner + 14 - 84, top + 6, 84, 32, (lambda i=t["id"]: self.answer("reject_items", e["id"], [i])), kind="quiet", size=13, weight=600)
                kit.button(box, "Add", inner + 14 - 84 - 6 - 64, top + 6, 64, 32, (lambda i=t["id"]: self.answer("accept_items", e["id"], [i])), kind="primary", size=13, weight=600)
                top += 44
            if n > 5:
                kit.put_text(box, f"+{n - 5} more after these", 14, top + 2, inner, 12, 400, kit.mute(), wrap=False, height=18)
                top += 22
            kit.put_text(box, "“Not here” keeps a thing out of this project for good. LMemM will not suggest it again.",
                         14, top + 2, inner, 12, 400, kit.mute(), wrap=False, height=18)
            return top + 22 - 12
        return self._card_box(doc, x, y, w, rows) + 20

    def _needs(self, doc, page, x, y, w):
        for t in page["things"]:
            y = self._card(doc, t, x, y, w)
        if not page["things"]:
            y = self._empty(doc, {"title": "All caught up", "line": "No open notes anywhere."}, x, y, w,
                                 symbol=("checkmark.circle.fill", "checkmark.circle"))
        return y

    def _project(self, doc, page, x, y, w):
        """A project with nothing in it yet (one with things is split: _head above, _things below)."""
        if page.get("suggested"):
            y = self._suggested(doc, page["suggested"], x, y, w)
        return self._empty(doc, page["empty"], x, y, w)

    def _project_actions(self, parent, right, y, pid):
        """"+ Sub-project" and the "…" menu, at the right of a project's title."""
        kit.button(parent, "⋯", right - 40, y, 40, 32, lambda: self.open_menu(pid), kind="quiet", size=16, weight=700)
        kit.button(parent, "+ Sub-project", right - 40 - 8 - 120, y, 120, 32, lambda: self.open_name("new", parent=pid),
                   kind="quiet", size=13, weight=600)

    def _thing_buttons(self, parent, right, y, tid):
        """"Move to…" and "⋯" at the right of a thing's title."""
        kit.button(parent, "⋯", right - 40, y, 40, 32, lambda: self.open_thing_menu([tid]), kind="quiet", size=16, weight=700)
        kit.button(parent, "Move to…", right - 40 - 8 - 100, y, 100, 32, lambda: self.open_thing_pick("assign", [tid]),
                   kind="quiet", size=13, weight=600)

    def _side_foot(self, side):
        """Pinned under the tree: make a project."""
        for sub in list(self.side_foot.subviews()):
            sub.removeFromSuperview()
        self.side_foot.setFrame_(NSMakeRect(0, H - 48, SIDE_W, 48))
        tap = self._tap(self.side_foot, 8, 8, SIDE_W - 16, 34, lambda: self.open_name("new"))
        kit.tile(tap, ("plus.circle.fill", "plus"), kit.ink(), 6, 5, 24)
        kit.put_text(tap, "New project", 40, 0, 110, 13, 500, wrap=False, height=34, middle=True)

    def _archived(self, doc, page, x, y, w):
        if page["empty"]:
            return self._empty(doc, page["empty"], x, y, w, symbol=("archivebox.fill", "tray.fill"))
        for r in page["rows"]:
            tap = self._tap(doc, x, y, w, 56, (lambda i=r["id"]: self.press("go", i)), fill=True)
            self._project_icon(tap, r["hue"], 12, 12, 32)
            kit.put_text(tap, r["name"], 56, 9, w - 56 - 110, 14, 600, wrap=False, height=20)
            kit.put_text(tap, (r["where"] + " · " if r["where"] else "") + r["line"], 56, 30, w - 56 - 110, 12, 400, kit.mute(), wrap=False, height=16)
            kit.button(tap, "Bring back", w - 100, 11, 88, 34, (lambda i=r["id"]: self.project_action("restore", pid=i)),
                       kind="outline", size=12, weight=600)
            y += 64
        return y

    # The top of a project page stays where it is; only the list of things under it scrolls.

    def _no_head(self):
        for sub in list(self.head_host.subviews()):
            sub.removeFromSuperview()
        return 0

    def _head(self, page):
        """Breadcrumb, title, Pick up, sub-projects and the Things controls. Returns its height."""
        host = self.head_host
        for sub in list(host.subviews()):
            sub.removeFromSuperview()
        x, w = PAD, MAIN_W
        y = self._crumbs(host, page["crumbs"], x, 26)
        self._project_icon(host, page["hue"], x, y - 2, 40)
        if page["archived"]:
            kit.button(host, "Bring back", x + w - 110, y - 4, 110, 32, lambda: self.project_action("restore", pid=page["pid"]),
                       kind="outline", size=13, weight=600)
        else:
            self._project_actions(host, x + w, y - 4, page["pid"])
        kit.put_text(host, page["title"], x + 54, y, w - 54 - 170, 26, 700, wrap=False, height=32)
        self._label(host, page["meta"], x + 54, y + 33, w - 54, size=13, weight=400)
        y += 62
        self._label(host, "PICK UP WHERE YOU LEFT OFF", x, y, w)
        y += 22
        if page["pick_up"]:
            gap = 12
            cw = (w - gap * 2) / 3
            for i, t in enumerate(page["pick_up"]):
                self._mini_card(host, t, x + i * (cw + gap), y, cw, 88)
            y += 88 + 18
        else:
            caught = page["caught_up"]
            tap = self._tap(host, x, y, w, 52, lambda: None, fill=True)
            kit.tile(tap, ("checkmark.circle.fill", "checkmark.circle"), kit.mute(), 12, 11, 30)
            kit.put_text(tap, caught["title"], 52, 8, w - 64, 14, 600, wrap=False, height=20)
            kit.put_text(tap, caught["line"], 52, 28, w - 64, 12, 400, kit.mute(), wrap=False, height=16)
            y += 52 + 18
        if page["subs"]:
            self._label(host, f"SUB-PROJECTS · {len(page['subs']) + page['subs_more']}", x, y, w)
            y += 22
            y = self._sub_chips(host, page, x, y, w) + 8
        total = f"Things · {page['total']}"
        kit.put_text(host, total, x, y, w, 15, 700, wrap=False, height=22)
        if self.sel is None and page["total"]:
            self._link(host, "Select", x + w - kit.text_width("Select", 13, 500) - 12, y - 4, self.start_select)
        y += 30
        if self.sel is not None:
            y += self._select_bar(host, page, x, y, w) + 10
        chips = []
        if page["deep"]["show"]:
            chips += [("Only here", not page["deep"]["on"], lambda: self.press("deep", False)),
                      ("With sub-projects", page["deep"]["on"], lambda: self.press("deep", True))]
        if len(page["filters"]) > 1:
            chips += [("All apps", self.nav["app"] is None, lambda: self.press("app", None))]
            chips += [(f["app"], self.nav["app"] == f["app"], (lambda a=f["app"]: self.press("app", a))) for f in page["filters"]]
        if chips:
            y += self._chips(host, x, y, chips) + 10
        return y

    def _select_bar(self, parent, page, x, y, w):
        """While selecting: how many, and what to do with them. Returns the height."""
        n = len(self.sel)
        tap = self._tap(parent, x, y, w, 44, lambda: None, fill=True)
        text = f"{n} selected" if n else "Tap things to select them"
        kit.put_text(tap, text, 14, 0, 200, 13, 600, None if n else kit.mute(), wrap=False, height=44, middle=True)
        right = w - 8
        for label, kind, call, width in (
                ("Done", "primary", self.stop_select, 70),
                ("Forget…", "quiet", lambda: self.open_thing_forget(self.sel), 84),
                ("Not in here", "quiet", lambda: self.thing_action("not_this", self.sel, page["pid"]), 104),
                ("Also in…", "quiet", lambda: self.open_thing_pick("also", self.sel), 90),
                ("Move to…", "quiet", lambda: self.open_thing_pick("assign", self.sel), 96)):
            if label != "Done" and not n:
                continue
            right -= width
            kit.button(tap, label, right, 6, width, 32, call, kind=kind, size=13, weight=600)
            right -= 6
        return 44

    def _mini_card(self, parent, t, x, y, w, h):
        """A small Pick up card: the app, the thing, and its first open notes. Opens the thing."""
        tap = self._tap(parent, x, y, w, h, (lambda i=t["id"]: self.press("thing", i)), fill=True)
        self._app_icon(tap, t["app"], 12, 11, 24)
        kit.put_text(tap, t["title"], 44, 11, w - 56, 13, 600, wrap=False, height=24, middle=True)
        shown = t.get("notes", [])[:2]
        more = t["open"] - len(shown)
        for i, text in enumerate(shown):
            tail = f"   +{more}" if more > 0 and i == len(shown) - 1 else ""
            kit.put_text(tap, "○  " + text + tail, 12, 44 + i * 18, w - 24, 12, 400, kit.mute(), wrap=False, height=18)
        return tap

    def _sub_chips(self, parent, page, x, y, w):
        """Sub-projects as small chips, wrapping onto more rows only when they must. Returns the new y."""
        cx = x
        for sub in page["subs"]:
            width = min(kit.text_width(sub["name"], 13, 500) + 52, w)
            if cx + width > x + w:
                cx, y = x, y + 38
            tap = self._tap(parent, cx, y, width, 32, (lambda i=sub["id"]: self.press("go", i)), fill=True)
            self._project_icon(tap, sub["hue"], 6, 5, 22)
            kit.put_text(tap, sub["name"], 34, 0, width - 40, 13, 500, wrap=False, height=32, middle=True)
            cx += width + 8
        if page["subs_more"]:
            label = f"+{page['subs_more']} more"
            width = kit.text_width(label, 13, 500) + 24
            if cx + width > x + w:
                cx, y = x, y + 38
            tap = self._tap(parent, cx, y, width, 32, lambda: self.press("more_subs"))
            kit.put_text(tap, label, 12, 0, width - 24, 13, 500, kit.mute(), wrap=False, height=32, middle=True)
        return y + 32

    def _things(self, doc, page, x, y, w):
        """The scrolling list: things grouped by when, newest first."""
        if page.get("suggested"):
            y = self._suggested(doc, page["suggested"], x, y, w)
        for group in page["groups"]:
            self._label(doc, group["title"].upper(), x, y + 4, w)
            y += 28
            for t in group["things"]:
                y = self._thing(doc, t, x, y, w, select=self.sel is not None)
            y += 6
        if not page["groups"]:
            self._label(doc, "Nothing matches this filter.", x, y + 8, w, size=13, weight=400)
            y += 34
        if page["things_more"]:
            kit.button(doc, f"Show {min(page['things_more'], page_model.THINGS_SHOWN)} more of {page['things_more']}",
                       x, y + 4, 240, 36, lambda: self.press("more"), kind="quiet", size=13, weight=500)
            y += 48
        return y

    def _card_box(self, parent, x, y, w, build, tap=None):
        """A soft box. `build(box, inner_width)` draws inside it from (14, 12) and returns the inner height."""
        box = self._tap(parent, x, y, w, 10, tap or (lambda: None), fill=True)
        inner = build(box, w - 28)
        box.setFrame_(NSMakeRect(x, y, w, inner + 24))
        return y + inner + 24

    def _thing_page(self, doc, page, x, y, w):
        """One thing in full: where it lives, its notes, the numbers, then what LMemM read from it."""
        if page["places"]:
            y = self._section(doc, "In", x, y, w)
            px = x
            for p in page["places"]:
                label = p["name"] + (" · main" if p["main"] else "")
                width = kit.text_width(label, 13, 500) + 52
                if px + width > x + w:
                    px, y = x, y + 40
                tap = self._tap(doc, px, y, width, 32, (lambda i=p["id"]: self.press("go", i)), fill=True)
                self._project_icon(tap, p["hue"], 6, 5, 22)
                kit.put_text(tap, label, 34, 0, width - 40, 13, 500, wrap=False, height=32, middle=True)
                px += width + 8
            y += 48
        reg, items = self.data()
        if page["item"] in items:                                 # why it is here: only what is stored
            y = self._section(doc, "Why it is here", x, y, w)
            for text in thing_actions.why(reg, items[page["item"]]):
                y += kit.put_text(doc, text, x, y, w, 13, 400) + 6
            y += 14
        if page["stats"]:                                         # four quiet tiles, not a table
            gap = 10
            tw = (w - gap * (len(page["stats"]) - 1)) / len(page["stats"])
            for i, (k, v) in enumerate(page["stats"]):
                tile = self._tap(doc, x + i * (tw + gap), y, tw, 62, lambda: None, fill=True)
                kit.put_text(tile, k.upper(), 14, 11, tw - 28, 10, 600, kit.mute(), wrap=False, height=14)
                kit.put_text(tile, v, 14, 28, tw - 28, 17, 700, wrap=False, height=26)
            y += 62 + 22
        y = self._section(doc, f"Notes · {page['open_count']} open", x, y, w)
        for n in page["open"]:
            y = self._card_box(doc, x, y, w, lambda box, inner, n=n: self._note_body(box, inner, n)) + 8
        if not page["open"]:
            self._label(doc, "All caught up." if page["done"] else "No notes yet. Add one below.", x, y, w, size=13, weight=400)
            y += 26
        if page["done"]:
            y = self._section(doc, f"Finished · {len(page['done'])}", x, y + 10, w)
            for n in page["done"]:
                row = self._tap(doc, x, y, w, 30, (lambda i=n["id"]: self.tick_note(i, False)))
                kit.put_text(row, "✓", 0, 0, 20, 13, 600, kit.mute(), wrap=False, height=30, middle=True)
                kit.put_text(row, n["text"], 26, 0, w - 26 - 70, 13, 400, kit.mute(), wrap=False, height=30, middle=True)
                kit.put_text(row, "Reopen", w - 64, 0, 64, 12, 500, kit.accent(), align=RIGHT, wrap=False, height=30, middle=True)
                y += 30
        if page["latest"]:
            y = self._section(doc, "What LMemM noticed", x, y + 10, w)

            def facts(box, inner):
                top = 0
                for k, v in page["latest"]:
                    kit.put_text(box, k, 14, 12 + top, 130, 12, 400, kit.mute(), wrap=False, height=18)
                    top += max(kit.put_text(box, v, 14 + 140, 12 + top, inner - 140, 13, 500), 18) + 8
                return top - 8
            y = self._card_box(doc, x, y, w, facts)
        if page["excerpts"]:
            y = self._section(doc, "What was on screen", x, y + 14, w)
            for e in page["excerpts"]:
                y = self._excerpt(doc, e, x, y, w) + 12
        return y

    def _note_body(self, box, inner, n):
        """A note: the tick on the left (a tap flips it), the words, when. A ticked note is crossed out."""
        tap = self._tap(box, 0, 0, 40, 44, (lambda i=n["id"], d=n["done"]: self.tick_note(i, not d)))
        ring = _Ring.alloc().initWithChecked_(n["done"])
        ring.setFrame_(NSMakeRect(14, 13, 17, 17))
        tap.addSubview_(ring)
        width = inner - 26 - 86
        if n["done"]:
            h = self._struck(box, n["text"], 40, 12, width, 14)
        else:
            h = kit.put_text(box, n["text"], 40, 12, width, 14, 500)
        kit.put_text(box, n["when"], 14 + inner - 80, 12, 80, 12, 400, kit.mute(), align=RIGHT, wrap=False, height=20)
        return max(h, 20)

    def _struck(self, parent, text, x, y, w, size):
        """Muted text with a line through it: a note you just finished."""
        height = kit.text_height(text, size, 500, w)
        view = kit._KitText.alloc().initWithText_size_weight_color_align_wrap_middle_(text, size, 500, kit.mute(), LEFT, True, False)
        view.setFrame_(NSMakeRect(x, y, w, height))
        marked = kit._attributed(text, size, 500, kit.mute(), LEFT, True).mutableCopy()
        marked.addAttribute_value_range_(NSStrikethroughStyleAttributeName, 1, (0, len(text)))
        view.attributed = marked
        parent.addSubview_(view)
        return height

    def _excerpt(self, doc, e, x, y, w):
        """One passage LMemM read: where and when, any decision it found, then its lines as short paragraphs."""
        def body(box, inner):
            top = 0
            head = e["source"] or "Screen"
            kit.put_text(box, head, 14, 12, inner - 100, 13, 600, wrap=False, height=20)
            kit.put_text(box, e["when"], 14 + inner - 96, 12, 96, 12, 400, kit.mute(), align=RIGHT, wrap=False, height=20)
            top = 30
            for quote in e["decisions"]:
                h = kit.put_text(box, "“" + quote + "”", 28, 12 + top, inner - 14, 13, 600, kit.accent())
                bar = _Bar.alloc().initWithFrame_(NSMakeRect(14, 12 + top + 2, 3, max(h - 4, 14)))
                box.addSubview_(bar)
                top += h + 10
            for line in e["lines"]:
                top += kit.put_text(box, line, 14, 12 + top, inner, 13, 400) + 7
            if e["more"] or e["open"]:
                label = f"Show {e['more']} more lines" if e["more"] else "Show less"
                self._link(box, label, 8, 12 + top - 2, (lambda i=e["id"]: self.press("expand", i)), size=12, color=kit.accent())
                top += 24
            return top - 7
        return self._card_box(doc, x, y, w, body)

    def _search(self, doc, page, x, y, w):
        if page["none"]:
            return self._empty(doc, {"title": "Nothing matches", "line": "Try part of a name, a note or a project."}, x, y, w,
                                symbol=("magnifyingglass",))
        if page["projects"]:
            y = self._section(doc, "Projects", x, y, w)
            y = self._rows_of_projects(doc, [{"id": p["id"], "name": p["name"], "line": p["path"]} for p in page["projects"]], x, y, w)
        if page["notes"]:
            y = self._section(doc, "Notes", x, y + 8, w)
            for n in page["notes"]:
                row = self._tap(doc, x, y, w, 42, (lambda i=n["id"]: self.press("thing", i)))
                kit.tile(row, ("note.text", "doc.text.fill"), kit.mute(), 0, 6, 30)
                kit.put_text(row, n["text"], 42, 4, w - 42, 14, 500, wrap=False, height=20)
                kit.put_text(row, n["thing"], 42, 22, w - 42, 12, 400, kit.mute(), wrap=False, height=16)
                y += 46
        if page["things"]:
            y = self._section(doc, "Things", x, y + 8, w)
            for t in page["things"]:
                y = self._thing(doc, t, x, y, w)
            if page["things_more"]:
                self._label(doc, f"{page['things_more']} more. Keep typing to narrow it.", x, y + 6, w, size=13, weight=400)
                y += 30
        return y
