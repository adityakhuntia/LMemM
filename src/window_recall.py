"""LMemM - what the pill brings back, in the window: "For you now" boxes, the side card, and the three actions.

The same four boxes as the pill (Pick up, Left open, Next step, From earlier; widget.RECALL) sit at the top of Home.
Pressing a box's words opens the side card with everything in it; only the circle ticks a box and only × sends it
away. Three buttons beside the title do what the pill's rows do: Copy context for AI and Copy today's recap open the
side card first, so you read what you are about to paste; Ask your memory opens it with a question box.
The text, the model calls and the clipboard are the tracker's (callbacks); this file only draws. Drawn on a Mac only.
"""

import objc
from AppKit import NSBezierPath, NSColor, NSImageView, NSMakeRect, NSTextField

import setup_kit as kit
from widget import RECALL, _Box, _Fields, _Flipped, _Ring, _Tap, _label, _short, _symbol, recall_rows, round_actions

PANEL_W = 400
HEAD_H = 44
FOOT_H = 66
PAD_P = 20
MAX_BOXES = 4
ASK_HINT = "Answered from what you have seen and written on this Mac. The sources are listed so you can check."
EMPTY_FOR_YOU = "Nothing waiting. What you left open, can pick up, or wrote before shows up here as you work."
WORKING = {"brief": "Writing it from your last 25 minutes…", "recap": "Reading today’s tasks…"}
TITLES = {"brief": "Context for AI", "recap": "Today’s recap"}
LEADS = {"brief": "Read it, then copy. Paste it into Claude or ChatGPT.", "recap": "Paste it into a standup or a status update."}
NOTHING = {"brief": "Nothing to brief yet. Use your Mac for a few minutes with LMemM running.",
           "recap": "No tasks yet today. LMemM works them out while it runs."}
FIELDS = (("goal", "Making"), ("last_wrote", "Last wrote"), ("open", "Open"), ("from", "From"))


class _PanelBack(_Flipped):
    """The side card's own background and the hairline on its left."""

    def drawRect_(self, rect):
        kit.card_background().setFill()
        NSBezierPath.fillRect_(self.bounds())
        kit.faint(0.12).setFill()
        NSBezierPath.fillRect_(NSMakeRect(0, 0, 1, self.bounds().size.height))


def _rgb(kind, alpha=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(*RECALL[kind][2], alpha)


class RecallPanes:
    """Mixed into MainWindow."""

    def init_recall(self, root, recall, on_recall, ask, ask_state, ask_reset, text, text_state, text_reset, copy):
        self.recall_fn = recall or (lambda: [])
        self.on_recall = on_recall or (lambda sid, state: None)
        self.ask_fn = ask or (lambda question: None)
        self.ask_state_fn = ask_state or (lambda: {"state": "idle"})
        self.ask_reset = ask_reset or (lambda: None)
        self.text_fn = text or (lambda name: None)
        self.text_state_fn = text_state or (lambda: {"state": "idle"})
        self.text_reset = text_reset or (lambda: None)
        self.copy_fn = copy or (lambda text: False)
        self.panel = None                       # None, or {"kind": "step"|"text"|"ask", ...}
        self.recall_now = []
        self.panel_host = _PanelBack.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_W, 100))
        self.panel_host.setHidden_(True)
        root.addSubview_(self.panel_host)
        self.panel_scroll = _new_scroll(self.panel_host)
        self.panel_foot = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_W, FOOT_H))
        self.panel_host.addSubview_(self.panel_foot)
        self.ask_typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: None, self.ask_go, self.close_panel)
        self.ask_field = NSTextField.alloc().initWithFrame_(NSMakeRect(PAD_P, 60, PANEL_W - 2 * PAD_P, 28))
        self.ask_field.setPlaceholderString_("What was that figure from the sheet?")
        self.ask_field.setBezeled_(True)
        self.ask_field.setBezelStyle_(1)
        self.ask_field.setDelegate_(self.ask_typing)
        self.ask_field.setHidden_(True)
        self.panel_host.addSubview_(self.ask_field)

    # ------------------------------------------------------------ state the window redraws on

    def recall_signature(self):
        self.recall_now = self.recall_fn() or []
        return (tuple((r["id"], r["text"]) for r in self.recall_now), self.panel_signature())

    def panel_signature(self):
        p = self.panel
        if not p:
            return None
        if p["kind"] == "ask":
            st = self.ask_state_fn()
            return ("ask", st.get("state"), st.get("question"))
        if p["kind"] == "text":
            st = self.text_state_fn()
            return ("text", p["name"], st.get("state"), p.get("copied"), len(st.get("text") or ""))
        return ("step", p["id"])

    # ------------------------------------------------------------ Home: the actions and the boxes

    def actions_row(self, doc, x, y, w):
        """Brief · Recap · Ask: three round buttons."""
        row, h = round_actions([("sparkles", "Brief", lambda: self.open_text("brief")),
                                ("text.alignleft", "Recap", lambda: self.open_text("recap")),
                                ("magnifyingglass", "Ask", self.open_memory_ask)], min(w, 300))
        row.setFrameOrigin_((x, y))
        doc.addSubview_(row)
        return y + h + 16

    def for_you(self, doc, x, y, w):
        """"For you now": up to four rows in one inset list, as in Settings."""
        steps = self.recall_now[:MAX_BOXES]
        kit.put_text(doc, "For you now", x, y, w, 15, 700, wrap=False, height=22)
        y += 30
        if not steps:
            h = kit.put_text(doc, EMPTY_FOR_YOU, x, y, min(w, 520), 13, 400, kit.mute())
            return y + h + 22
        group, h = recall_rows(steps, w, self.open_step, lambda sid: self.recall_answer(sid, "done"))
        group.setFrameOrigin_((x, y))
        doc.addSubview_(group)
        return y + h + 22

    def recall_answer(self, sid, state):
        self.on_recall(sid, state)
        if self.panel and self.panel.get("id") == sid:
            self.panel = None
        self.shown = None
        self.render()

    # ------------------------------------------------------------ the side card

    def open_step(self, sid):
        self.panel = {"kind": "step", "id": sid}
        self.render()

    def open_text(self, name):
        self.text_reset()
        self.text_fn(name)
        self.panel = {"kind": "text", "name": name}
        self.render()

    def open_memory_ask(self):
        self.ask_reset()
        self.ask_field.setStringValue_("")
        self.panel = {"kind": "ask"}
        self.render()

    def ask_go(self, text):
        if text.strip():
            self.ask_fn(text)
            self.render()

    def close_panel(self):
        if self.panel:
            self.panel = None
            self.shown = None
            self.render()

    def copy_text(self):
        text = (self.text_state_fn().get("text") or "").strip()
        if text and self.copy_fn(text):
            self.panel["copied"] = True
            self.render()

    def draw_panel(self, top, height):
        """Show, hide or redraw the side card to match self.panel. `top`/`height`: the area it covers."""
        p = self.panel
        self.ask_field.setHidden_(True)
        if not p:
            self.panel_host.setHidden_(True)
            return
        self.panel_host.setFrame_(NSMakeRect(self.W - PANEL_W, top, PANEL_W, height))
        self.panel_host.setHidden_(False)
        for sub in list(self.panel_foot.subviews()):
            sub.removeFromSuperview()
        close = _Tap.alloc().initWithFrame_callback_(NSMakeRect(PANEL_W - 44, 8, 30, 28), self.close_panel)
        close.label = "Close"
        close.addSubview_(_label("×", 20, color=NSColor.secondaryLabelColor(), frame=(8, 1, 16, 24))[0])
        for sub in [s for s in self.panel_host.subviews() if getattr(s, "is_close", False)]:
            sub.removeFromSuperview()
        close.is_close = True
        self.panel_host.addSubview_(close)
        build, foot = {"step": self._pane_step, "text": self._pane_text, "ask": self._pane_ask}[p["kind"]], FOOT_H
        feet = []
        doc = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_W, 10))
        used = build(doc, feet)
        foot = FOOT_H if feet else 0
        view_h = height - HEAD_H - foot
        self.panel_scroll.setFrame_(NSMakeRect(0, HEAD_H, PANEL_W, view_h))
        doc.setFrame_(NSMakeRect(0, 0, PANEL_W, max(used + 24, view_h)))
        self.panel_scroll.setDocumentView_(doc)
        self.panel_scroll.contentView().scrollToPoint_((0, 0))
        self.panel_scroll.reflectScrolledClipView_(self.panel_scroll.contentView())
        self.panel_foot.setFrame_(NSMakeRect(0, height - foot, PANEL_W, foot))
        bx = PAD_P
        n = len(feet)
        bw = (PANEL_W - 2 * PAD_P - 8 * (n - 1)) / max(n, 1)
        for label, primary, call in feet:
            kit.button(self.panel_foot, label, bx, 14, bw, 38, call, kind="primary" if primary else "quiet", size=14, weight=600)
            bx += bw + 8
        self.panel_foot.setHidden_(not feet)
        if p["kind"] == "ask" and self.ask_state_fn().get("state") == "idle":
            self.ask_field.setFrame_(NSMakeRect(PAD_P, HEAD_H + 40, PANEL_W - 2 * PAD_P, 28))
            self.ask_field.setHidden_(False)
            self.window.makeFirstResponder_(self.ask_field)

    def _pane_step(self, doc, feet):
        step = next((r for r in self.recall_now if r["id"] == self.panel["id"]), None)
        if step is None:                                      # ticked or gone while it was open
            self.panel = None
            self.panel_host.setHidden_(True)
            return 0
        kind = step["kind"]
        label, symbol, _rgb_, _dashed = RECALL[kind]
        tone = _rgb(kind)
        y = 6
        image = _symbol(symbol)
        if image is not None:
            icon = NSImageView.alloc().initWithFrame_(NSMakeRect(PAD_P, y + 1, 14, 14))
            icon.setImage_(image)
            icon.setContentTintColor_(tone)
            doc.addSubview_(icon)
        doc.addSubview_(_label(label.upper(), 10.5, bold=True, color=tone, frame=(PAD_P + 20, y, 200, 14))[0])
        y += 26
        y += kit.put_text(doc, step["text"], PAD_P, y, PANEL_W - 2 * PAD_P, 17, 700) + 14
        detail = step.get("detail") or {}
        for key, name in FIELDS:
            if detail.get(key):
                kit.put_text(doc, name.upper(), PAD_P, y, PANEL_W - 2 * PAD_P, 10, 700, kit.faint(0.45), wrap=False, height=14)
                y += 17
                y += kit.put_text(doc, str(detail[key]), PAD_P, y, PANEL_W - 2 * PAD_P, 14, 400) + 14
        things = step.get("things") or detail.get("things") or []
        if things:
            kit.put_text(doc, "WHERE", PAD_P, y, PANEL_W - 2 * PAD_P, 10, 700, kit.faint(0.45), wrap=False, height=14)
            y += 17
            for t in things[:6]:
                y += kit.put_text(doc, " · ".join(x for x in (t.get("app"), t.get("title")) if x), PAD_P, y,
                                  PANEL_W - 2 * PAD_P, 13, 400, kit.mute()) + 4
        sid = step["id"]
        feet.append(("Copy" if kind == "earlier" else "Mark done", True, lambda: self.recall_answer(sid, "done")))
        feet.append(("Not now", False, lambda: self.recall_answer(sid, "dismissed")))
        return y

    def _pane_text(self, doc, feet):
        name = self.panel["name"]
        st = self.text_state_fn()
        y = 6
        y += kit.put_text(doc, TITLES[name], PAD_P, y, PANEL_W - 2 * PAD_P, 19, 700) + 6
        y += kit.put_text(doc, LEADS[name], PAD_P, y, PANEL_W - 2 * PAD_P, 12.5, 400, kit.mute()) + 14
        if st.get("state") != "done" or st.get("name") != name:
            kit.put_text(doc, WORKING[name], PAD_P, y, PANEL_W - 2 * PAD_P, 14, 400, kit.mute(), wrap=False, height=20)
            return y + 30
        text = (st.get("text") or "").strip()
        if not text:
            return y + kit.put_text(doc, NOTHING[name], PAD_P, y, PANEL_W - 2 * PAD_P, 14, 400, kit.mute())
        box = _Tap.alloc().initWithFrame_callback_(NSMakeRect(PAD_P - 8, y, PANEL_W - 2 * PAD_P + 16, 10), lambda: None)
        box.fill = True
        h = kit.put_text(box, text, 12, 12, PANEL_W - 2 * PAD_P - 8, 13, 400)
        box.setFrame_(NSMakeRect(PAD_P - 8, y, PANEL_W - 2 * PAD_P + 16, h + 24))
        doc.addSubview_(box)
        feet.append(("Copied" if self.panel.get("copied") else "Copy", not self.panel.get("copied"), self.copy_text))
        return y + h + 24

    def _pane_ask(self, doc, feet):
        st = self.ask_state_fn()
        y = 6
        y += kit.put_text(doc, "Ask your memory", PAD_P, y, PANEL_W - 2 * PAD_P, 19, 700) + 8
        state = st.get("state")
        if state == "idle":
            y += 44                                           # the field sits here
            return y + kit.put_text(doc, ASK_HINT, PAD_P, y, PANEL_W - 2 * PAD_P, 12, 400, kit.faint(0.45)) + 8
        y += kit.put_text(doc, st.get("question", ""), PAD_P, y, PANEL_W - 2 * PAD_P, 12.5, 400, kit.mute()) + 12
        if state == "working":
            kit.put_text(doc, "Looking through what you have seen…", PAD_P, y, PANEL_W - 2 * PAD_P, 14, 400, wrap=False, height=20)
            return y + 30
        y += kit.put_text(doc, st.get("answer", ""), PAD_P, y, PANEL_W - 2 * PAD_P, 15, 600) + 14
        if st.get("sources"):
            kit.put_text(doc, "FROM", PAD_P, y, PANEL_W - 2 * PAD_P, 10, 700, kit.faint(0.45), wrap=False, height=14)
            y += 18
        for src in st.get("sources") or []:
            box = _Box.alloc().initWithTone_dashed_(RECALL["earlier"][2], False)
            tw = PANEL_W - 2 * PAD_P - 24
            h1 = kit.put_text(box, src["text"], 12, 10, tw, 13, 400)
            h2 = kit.put_text(box, src["line"], 12, 10 + h1 + 4, tw, 11, 400, kit.faint(0.45))
            box.setFrame_(NSMakeRect(PAD_P, y, PANEL_W - 2 * PAD_P, h1 + h2 + 24))
            doc.addSubview_(box)
            y += h1 + h2 + 24 + 8
        y += 6
        self._ask_again = kit.button(doc, "Ask something else", PAD_P, y, 170, 32, self.open_memory_ask, kind="quiet", size=13, weight=600)
        return y + 44


def _new_scroll(parent):
    from AppKit import NSScrollView
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    scroll.setDrawsBackground_(False)
    scroll.setHasVerticalScroller_(True)
    scroll.setAutohidesScrollers_(True)
    scroll.setScrollerStyle_(1)
    scroll.setBorderType_(0)
    parent.addSubview_(scroll)
    return scroll
