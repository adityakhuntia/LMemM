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

reg, items, ids = world()
sug = sg.empty()
sg.offer_project(sug, items, "Trip", ["a", "e"])
sg.offer_items(sug, reg, items, ids["q3"], ["c", "d", "e"])
data = lambda: (reg, items)
calls = []
def on_project(action, args):
    calls.append((action, args))
    import project_actions as pa
    return pa.do(reg, items, action, **({**args, "sug": sug} if action in sg.ACTIONS else args))
w = window.MainWindow(lambda r: None, data, on_project=on_project, on_project_undo=lambda u: None,
                      suggest=lambda: sg.view(sug, reg, items, datetime.now()))
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

step("home", render)
w.nav = page_model.press(reg, w.nav, "go", ids["q3"])
step("project q3 (suggested)", render)
w.nav = page_model.press(reg, w.nav, "go", ids["home"])
step("project home", render)
w.start_select(); step("select", render)
w.pick_thing("d"); step("select ticked", render)
w.open_thing_menu(["d"]); w.open_thing_pick("assign", ["d"]); w.open_thing_forget(["d"])
w.close_dialog(); w.stop_select()
w.nav = page_model.press(reg, w.nav, "thing", "a"); step("thing page", render)
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
print("FAILED:", FAILED) if FAILED else print("all pages drew")
sys.exit(1 if FAILED else 0)
