"""LMemM - the main window. It draws window_model.view() (the state banner) and
page_model.view() (the project page), and forwards presses; it decides nothing (S8, W1-W6 in
window_model.py, P1-P8 in page_model.py). Only the drawing is here, so a Mac is needed to look at it.

Layout: the banner across the top when there is one; under it the sidebar (search, Needs you, the
project tree) and the page. The search field is built once and never rebuilt, so typing is never
interrupted by a redraw; the two scrolling areas keep their place when the data underneath changes.
"""

import sys
import traceback

from Foundation import NSObject
from AppKit import (NSApplication, NSColor, NSImageView, NSMakePoint, NSMakeRect, NSScrollView, NSTextField,
                    NSWindow, NSWorkspace)

import apps
import page_model
import setup_kit as kit
import window_model
from setup_kit import LEFT, RIGHT
from widget import _Fields, _Flipped, _Tap

W, H = 980, 680
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


def _scroll(parent):
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    scroll.setDrawsBackground_(False)
    scroll.setHasVerticalScroller_(True)
    scroll.setAutohidesScrollers_(False)                          # a visible bar says "this scrolls"
    scroll.setScrollerStyle_(0)                                   # legacy: always shown
    parent.addSubview_(scroll)
    return scroll


class MainWindow:
    """on_press(row id) is called when the banner's button is pressed (ids the menu already knows).
    data() returns (project registry, things by id) for the page."""

    def __init__(self, on_press, data):
        self.on_press = on_press
        self.data = data
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
        self.banner_host = _Flipped.alloc().initWithFrame_(NSMakeRect(SIDE_W, TOP, W - SIDE_W, 0))
        self.root.addSubview_(self.banner_host)
        self.typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: self.press("search", text), lambda text: self.press("search", text), self._cancel_search)
        self.search = NSTextField.alloc().initWithFrame_(NSMakeRect(14, 0, SIDE_W - 28, 28))
        self.search.setPlaceholderString_("Search")
        self.search.setBezeled_(True)
        self.search.setBezelStyle_(1)
        self.search.setDelegate_(self.typing)
        self.root.addSubview_(self.search)
        self.side_scroll = _scroll(self.root)
        self.main_scroll = _scroll(self.root)
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
        self.nav = page_model.press(reg, self.nav, action, arg, items)
        self.render()

    def back(self, kind):
        if kind == "thing":
            self.press("back")
        elif kind == "search":
            self.press("clear")
        else:
            self.press("home")

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
        page = page_model.view(reg, items, self.nav)
        sig = repr((window_model.signature(self.banner), page))
        if sig == self.shown:
            return
        self.shown = sig
        top = self._banner(self.banner["banner"])
        self.search.setFrame_(NSMakeRect(14, TOP + 8, SIDE_W - 28, 28))
        self.side_scroll.setFrame_(NSMakeRect(0, TOP + 44, SIDE_W, H - TOP - 44))
        self.main_scroll.setFrame_(NSMakeRect(SIDE_W, top, W - SIDE_W, H - top))
        here = (self.nav["view"], self.nav["pid"], self.nav["q"], self.nav["tid"])
        moved, self.where = here != self.where, here
        self._fill(self.side_scroll, SIDE_W, lambda doc: self._side(doc, page["side"]))
        self._fill(self.main_scroll, W - SIDE_W, lambda doc: self._main(doc, page["main"]), top=moved)

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
            tap = self._tap(doc, 8, y, SIDE_W - 16, 28, (lambda r=row: self.press("go", r["id"])), fill=row["selected"])
            if row["expandable"]:
                caret = self._tap(tap, x - 8, 0, 22, 28, (lambda r=row: self.press("toggle", r["id"])))
                kit.put_text(caret, "▾" if row["expanded"] else "▸", 0, 0, 22, 11, 600, kit.mute(), align=kit.CENTER,
                             wrap=False, height=28, middle=True)
            self._project_icon(tap, row["hue"], x + 16, 4, 20)
            kit.put_text(tap, row["name"], x + 42, 0, SIDE_W - 16 - x - 42 - 40, 13, 500, wrap=False, height=28, middle=True)
            if row["count"]:
                kit.put_text(tap, str(row["count"]), SIDE_W - 16 - 38, 0, 30, 12, 400, kit.mute(), align=RIGHT,
                             wrap=False, height=28, middle=True)
            y += 28
        if not tree:
            self._label(doc, "None yet. They appear as you work.", 16, y, SIDE_W - 32, size=13, weight=400)
            y += 26
        return y

    # ------------------------------------------------------------ the page

    def _main(self, doc, page):
        x, w = PAD, MAIN_W
        y = 30
        kind = page["kind"]
        if kind in ("search", "needs", "thing"):
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
        elif kind in ("home", "needs"):
            kit.tile(doc, ("square.stack.3d.up.fill", "folder.fill") if kind == "home" else ("bell.badge.fill", "bell.fill"),
                     kit.ink(), x, y - 2, 40)
            tx = x + 54
        kit.put_text(doc, page["title"], tx, y, w - (tx - x), 26, 700, wrap=False, height=34)
        y += 36
        if page.get("meta"):
            self._label(doc, page["meta"], tx, y, w - (tx - x), size=13, weight=400)
            y += 34
        build = {"home": self._home, "project": self._project, "needs": self._needs, "search": self._search,
                 "thing": self._thing_page}[kind]
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

    def _thing(self, doc, t, x, y, w, notes=False):
        """A thing: its title, where it is, when. With notes: the open ones underneath. Returns the new y."""
        box = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, 10), (lambda i=t["id"]: self.press("thing", i)))
        self._app_icon(box, t["app"], 0, 8, 34)
        tx = 46
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

    def _needs(self, doc, page, x, y, w):
        for t in page["things"]:
            y = self._card(doc, t, x, y, w)
        if not page["things"]:
            y = self._empty(doc, {"title": "All caught up", "line": "No open notes anywhere."}, x, y, w,
                                 symbol=("checkmark.circle.fill", "checkmark.circle"))
        return y

    def _project(self, doc, page, x, y, w):
        if page.get("empty"):
            return self._empty(doc, page["empty"], x, y, w)
        y = self._section(doc, "Pick up where you left off", x, y, w)
        if page["pick_up"]:
            for t in page["pick_up"]:
                y = self._card(doc, t, x, y, w)
        else:
            caught = page["caught_up"]
            tap = self._tap(doc, x, y, w, 10, lambda: None, fill=True)
            kit.put_text(tap, caught["title"], 14, 12, w - 28, 14, 600, wrap=False, height=20)
            h = kit.put_text(tap, caught["line"], 14, 36, w - 28, 13, 400, kit.mute())
            tap.setFrame_(NSMakeRect(x, y, w, 36 + h + 14))
            y += 36 + h + 14 + 10
        if page["subs"]:
            y = self._section(doc, f"Sub-projects · {len(page['subs']) + page['subs_more']}", x, y + 8, w)
            y = self._rows_of_projects(doc, page["subs"], x, y, w)
            if page["subs_more"]:
                self._link(doc, f"Show {min(page['subs_more'], page_model.SUBS_SHOWN)} more sub-projects", x - 6, y - 4,
                           lambda: self.press("more_subs"))
                y += 30
        y = self._section(doc, f"Things · {page['total']}", x, y + 8, w)
        chips = []
        if page["deep"]["show"]:
            chips += [("Only here", not page["deep"]["on"], lambda: self.press("deep", False)),
                      ("With sub-projects", page["deep"]["on"], lambda: self.press("deep", True))]
        if len(page["filters"]) > 1:
            chips += [("All apps", self.nav["app"] is None, lambda: self.press("app", None))]
            chips += [(f["app"], self.nav["app"] == f["app"], (lambda a=f["app"]: self.press("app", a))) for f in page["filters"]]
        if chips:
            y += self._chips(doc, x, y, chips) + 12
        for group in page["groups"]:
            self._label(doc, group["title"].upper(), x, y, w)
            y += 24
            for t in group["things"]:
                y = self._thing(doc, t, x, y, w)
        if not page["groups"]:
            self._label(doc, "Nothing matches this filter.", x, y, w, size=13, weight=400)
            y += 26
        if page["things_more"]:
            kit.button(doc, f"Show {min(page['things_more'], page_model.THINGS_SHOWN)} more of {page['things_more']}",
                       x, y + 8, 240, 36, lambda: self.press("more"), kind="quiet", size=13, weight=500)
            y += 52
        return y

    def _thing_page(self, doc, page, x, y, w):
        """One thing in full: where it lives, its notes, the numbers, what LMemM read from it."""
        if page["places"]:
            y = self._section(doc, "In", x, y, w)
            px = x
            for p in page["places"]:
                label = p["name"] + (" · main" if p["main"] else "")
                width = kit.text_width(label, 13, 500) + 52
                tap = self._tap(doc, px, y, width, 32, (lambda i=p["id"]: self.press("go", i)), fill=True)
                self._project_icon(tap, p["hue"], 6, 5, 22)
                kit.put_text(tap, label, 34, 0, width - 40, 13, 500, wrap=False, height=32, middle=True)
                px += width + 8
            y += 48
        y = self._section(doc, f"Notes · {len(page['open'])} open", x, y, w)
        for n in page["open"]:
            y += kit.put_text(doc, "○  " + n["text"], x, y, w, 14, 500) + 2
            self._label(doc, n["when"], x + 22, y, w, size=12, weight=400)
            y += 24
        if not page["open"]:
            self._label(doc, "No open notes.", x, y, w, size=13, weight=400)
            y += 26
        if page["done"]:
            y = self._section(doc, f"Finished · {len(page['done'])}", x, y + 8, w)
            for n in page["done"]:
                y += kit.put_text(doc, "✓  " + n["text"], x, y, w, 13, 400, kit.mute()) + 6
        if page["stats"]:
            y = self._section(doc, "About this", x, y + 8, w)
            for k, v in page["stats"]:
                self._label(doc, k, x, y, 140, size=13, weight=400)
                kit.put_text(doc, v, x + 150, y, w - 150, 13, 500, wrap=False, height=20)
                y += 24
        if page["latest"]:
            y = self._section(doc, "What LMemM saw", x, y + 8, w)
            for k, v in page["latest"]:
                self._label(doc, k, x, y, 140, size=13, weight=400)
                y += kit.put_text(doc, v, x + 150, y, w - 150, 13, 500) + 8
        if page["content"]:
            y = self._section(doc, "Its text", x, y + 8, w)
            y += kit.put_text(doc, page["content"], x, y, w, 12, 400, kit.mute()) + 6
        return y

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
