"""Run window.py's drawing code against a fake AppKit, to catch Python mistakes (a wrong key, a bad call) that
only show on a Mac. It cannot judge looks. Run on its own: it stubs modules, so tests/test_window_smoke.py
starts it in a separate process. Exits 1 and prints the traceback when any page fails to draw."""
import sys, types, traceback
from unittest import mock
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), HERE]

class Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"): raise AttributeError(name)
        return mock.MagicMock()

class Base(metaclass=Meta):
    def __init__(self, *a, **k): pass
    @classmethod
    def alloc(cls): return cls()
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return mock.MagicMock()

def fake(name, bases=()):
    m = types.ModuleType(name)
    def getattr_(attr):
        if attr.startswith("__"): raise AttributeError(attr)
        if attr[:2] in ("NS",) and attr[2:3].isupper() and attr not in ("NSMakeRect","NSMakePoint"):
            return type(attr, (Base,), {})
        return mock.MagicMock()
    m.__getattr__ = getattr_
    sys.modules[name] = m
    return m
for n in ("objc", "Foundation", "AppKit", "Quartz", "CoreText", "Cocoa", "UserNotifications", "ApplicationServices", "AVFoundation", "Speech"):
    fake(n)
sys.modules["objc"].super = lambda *a: mock.MagicMock()
sys.modules["objc"].python_method = lambda f: f

fake_widget = types.ModuleType("widget")
for n in ("_Fields", "_Flipped", "_Ring", "_Tap"):
    setattr(fake_widget, n, type(n, (Base,), {"initWithChange_submit_cancel_": lambda self,*a: self, "initWithFrame_callback_": lambda self,*a: self, "initWithFrame_": lambda self,*a: self, "initWithChecked_": lambda self,*a: self}))
fake_widget.RECALL = {"earlier": ("From earlier", "doc.on.doc", (0.45, 0.36, 0.78), False), "resume": ("Pick up", "a", (0.9, 0.4, 0.1), False),
                      "hanging": ("Left open", "b", (0.7, 0.5, 0.0), True), "next": ("Next step", "c", (0.2, 0.5, 0.5), False)}
fake_widget._Box = type("_Box", (Base,), {"initWithTone_dashed_": lambda self, *a: self})
fake_widget._label = lambda *a, **k: (mock.MagicMock(), 20)
fake_widget._short = lambda text, n: text
fake_widget._symbol = lambda name: mock.MagicMock()
SIZE = types.SimpleNamespace(width=1080, height=720)
fake_widget._Flipped.frame = lambda self: types.SimpleNamespace(size=SIZE)
sys.modules["widget"] = fake_widget
kit = types.ModuleType("setup_kit")
for n in ("put_text","tile","button","text_width","text_height","ink","mute","accent","card_background","faint","line","icon","first_symbol","note"):
    setattr(kit, n, mock.MagicMock(return_value=20))
kit.LEFT, kit.RIGHT, kit.CENTER = 0, 2, 1
kit.text_width = lambda *a, **k: 50
sys.modules["setup_kit"] = kit
import window
print("window imported with fakes")

from datetime import datetime
from test_project_actions import world
import projects, suggestions as sg, page_model, notes, time
import settings_model as sm
USER = {"name": "Ada", "works_on": ["code"], "watch_apps": [{"id": "com.a", "name": "A"}], "skip_apps": [{"id": "com.x", "name": "X"}]}
FACTS = {"screen": False, "screen_fresh": True, "ax": False, "mic": "denied", "speech": "granted"}

reg, items, ids = world()
sug = sg.empty()
sg.offer_project(sug, items, "Trip", ["a", "e"])
sg.offer_items(sug, reg, items, ids["q3"], ["c", "d", "e"])
data = lambda: (reg, items)
calls = []
def on_project(action, args):
    calls.append((action, args))
    if action in sm.ACTIONS:
        r = sm.apply(USER, action, args.get("value"))
        return {"message": r["message"], "go": None, "stay": True, "undo": {"settings": USER}}
    import project_actions as pa
    return pa.do(reg, items, action, **({**args, "sug": sug} if action in sg.ACTIONS else args))
STEPS = [{"id": "n1", "kind": "resume", "text": "Back to “Verify the follow-up automation”", "task": "t", "age": "now",
          "detail": {"goal": "Find out who schedules", "last_wrote": "x" * 200, "open": "Compare"}, "things": [{"app": "Mail", "title": "Draft"}]},
         {"id": "n2", "kind": "hanging", "text": "Unsent draft: “Reminder”", "task": None, "age": "now", "detail": {}, "things": []},
         {"id": "n3", "kind": "next", "text": "Check the trigger", "task": "t", "age": "now", "detail": {}, "things": []},
         {"id": "n4", "kind": "earlier", "text": "“The trigger runs every morning”", "task": None, "age": "now",
          "detail": {"from": "Apps Script · Auto Send", "copy": "The trigger runs every morning"}, "things": []}]
ASK = {"state": "idle"}
TEXT = {"state": "idle"}
ANSWERS, ASKED, COPIED, TEXTS = [], [], [], []
w = window.MainWindow(lambda r: None, data, on_project=on_project, on_project_undo=lambda u: None,
                      recall=lambda: list(STEPS), on_recall=lambda sid, st: ANSWERS.append((sid, st)),
                      ask=ASKED.append, ask_state=lambda: ASK, ask_reset=lambda: ASK.update(state="idle"),
                      text=TEXTS.append, text_state=lambda: TEXT, text_reset=lambda: TEXT.update(state="idle"),
                      copy=lambda t: COPIED.append(t) or True,
                      suggest=lambda: sg.view(sug, reg, items, datetime.now()),
                      prefs=lambda section: sm.view(USER, section, FACTS, {"data_dir": "/x/data", "files": 3, "bytes": 1200}))
class FakeScroll:
    def frame(self): return types.SimpleNamespace(size=types.SimpleNamespace(height=600, width=800))
    def contentView(self):
        return types.SimpleNamespace(bounds=lambda: types.SimpleNamespace(origin=types.SimpleNamespace(y=0)),
                                     scrollToPoint_=lambda p: None)
    def __getattr__(self, n): return mock.MagicMock()
w.side_scroll, w.main_scroll = FakeScroll(), FakeScroll()
import window_model
w.banner = window_model.view({"screen": True})

FAILED = []


def step(name, fn):
    try:
        fn()
        print("ok  ", name)
    except Exception:
        FAILED.append(name)
        print("FAIL", name); traceback.print_exc()

def render():
    w.shown = None
    w._render()

kit.put_text.reset_mock()
step("home", render)
texts = [c.args[1] for c in kit.put_text.call_args_list if len(c.args) > 1]
for want in ("For you now",):
    if want not in texts:
        FAILED.append("home is missing: " + want)
labels_ = [c.args[1] for c in kit.button.call_args_list if len(c.args) > 1]
for want in ("Copy context for AI", "Copy today’s recap", "Ask your memory…"):
    if want not in labels_:
        FAILED.append("home is missing the button: " + want)
w.open_step("n1"); step("side card: a step", render)
w.open_step("n4"); step("side card: from earlier", render)
w.recall_answer("n4", "done"); step("answer from the card", render)
if ANSWERS != [("n4", "done")] or w.panel is not None:
    FAILED.append("answering a step from its card did not close it: %r %r" % (ANSWERS, w.panel))
w.open_text("brief"); step("side card: brief writing", render)
TEXT.update(name="brief", state="done", text="I am building a thing.\n- It works.\nNext: test it.")
step("side card: brief done", render)
w.copy_text()
if COPIED != ["I am building a thing.\n- It works.\nNext: test it."] or not w.panel.get("copied"):
    FAILED.append("copy in the brief card did not copy: %r" % COPIED)
step("side card: brief copied", render)
TEXT.update(name="brief", state="done", text="")
step("side card: nothing to brief", render)
w.open_text("recap"); step("side card: recap", render)
w.open_memory_ask(); step("side card: ask idle", render)
w.ask_go("what was the figure?")
if ASKED != ["what was the figure?"]:
    FAILED.append("ask did not send the question")
ASK.update(state="working", question="what was the figure?"); step("side card: ask working", render)
ASK.update(state="done", answer="31 percent [1]", sources=[{"n": 1, "line": "Sheets · yesterday", "text": "Reply rate was 31 percent"}])
step("side card: ask answered", render)
w.escape()
if w.panel is not None:
    FAILED.append("Escape did not close the side card")
step("side card closed", render)
w.nav = page_model.press(reg, w.nav, "go", ids["q3"])
step("project q3 (suggested)", render)
w.nav = page_model.press(reg, w.nav, "go", ids["home"])
step("project home", render)
w.start_select(); step("select", render)
w.pick_thing("d"); step("select ticked", render)
w.open_thing_menu(["d"]); w.open_thing_pick("assign", ["d"]); w.open_thing_forget(["d"])
w.close_dialog(); w.stop_select()
w.nav = page_model.press(reg, w.nav, "thing", "a"); step("thing page", render)
for section in sm.SECTIONS:
    w.nav = page_model.press(reg, w.nav, "settings", section)
    step("settings " + section, render)
w.installed = [{"id": "com.b", "name": "B", "path": "/Applications/B.app"}, {"id": "com.a", "name": "A", "path": "/Applications/A.app"}]
w.app_paths = {}
w.open_apps("watch"); step("app picker (watch)", lambda: w._dialog())
w.open_apps("skip"); step("app picker (skip)", lambda: w._dialog())
w.dialog["query"] = "b"; step("app picker narrowed", lambda: w._dialog())
w.setting("watch_add", {"id": "com.b", "name": "B"})
if not w.dialog:
    FAILED.append("the app picker closed after adding an app")
w.close_dialog()
w.open_name("me"); step("name dialog", lambda: w._dialog(focus=True)); w.close_dialog()
w.setting("keep_days", 30)
w.nav = page_model.press(reg, w.nav, "back")
step("back from settings", render)
w.nav = page_model.press(reg, w.nav, "go", ids["q3"])
for action, sid, kw in (("accept_items", "s2", {"ids": ["c"]}), ("reject_items", "s2", {"ids": ["d"]}), ("accept_project", "s1", {})):
    step("answer " + action, lambda: w.answer(action, sid, **kw))

reg, items, ids = world()
sug = sg.empty()
sg.offer_project(sug, items, "Trip", ["a", "e"])
sg.offer_items(sug, reg, items, ids["q3"], ["c", "d"])
w.nav = page_model.new_state()
kit.put_text.reset_mock()
render()
texts = [c.args[1] for c in kit.put_text.call_args_list if len(c.args) > 1]
for want in ("Suggestions · 2", "Make “Trip” a project?", "2 things may belong in “Q3 plan”"):
    if want not in texts:
        FAILED.append("home is missing: " + want)
w.nav = page_model.press(reg, w.nav, "go", ids["q3"])
kit.put_text.reset_mock(); render()
if "Suggested for this project · 2" not in [c.args[1] for c in kit.put_text.call_args_list]:
    FAILED.append("project page is missing its suggestions")
for label, wd, ht in (("narrow", 880, 560), ("wide", 2200, 1300), ("small than minimum", 600, 400), ("back", 1080, 720)):
    SIZE.width, SIZE.height = wd, ht
    step("resize " + label, w._resized)
    if not (880 <= w.W and 560 <= w.H and 560 <= w.main_w <= 980 and w.col_x >= 24):
        FAILED.append("bad layout at %s: %s" % (label, (w.W, w.H, w.main_w, w.col_x)))
    if w.col_x + w.main_w > w.W - window.SIDE_W:
        FAILED.append("column overflows at " + label)
    for kind in ("go", "thing"):
        w.nav = page_model.press(reg, w.nav, kind, ids["q3"] if kind == "go" else "a")
        step("page at %s (%s)" % (label, kind), render)
import keynav
w.nav = page_model.new_state(); render()
step("keys: down in page", lambda: w.key(keynav.DOWN))
if w.cur["id"] is None: FAILED.append("Down did not land on a row")
step("keys: left to sidebar", lambda: w.key(keynav.LEFT))
step("keys: down in sidebar", lambda: w.key(keynav.DOWN))
if w.cur["zone"] != "side" or w.cur["id"] is None: FAILED.append("sidebar walk failed %s" % w.cur)
step("keys: return opens", lambda: w.key(keynav.RETURN))
w.dialog = {"kind": "x"}
if w.key(keynav.DOWN): FAILED.append("keys must not move behind a card")
w.dialog = None
w.focus_search(); w.go_back(); w._regular(True); w._regular(False)
print("FAILED:", FAILED) if FAILED else print("all pages drew")
sys.exit(1 if FAILED else 0)
