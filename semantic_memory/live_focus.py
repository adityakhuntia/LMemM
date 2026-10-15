"""Metadata-only native focused-window validation. Unknown means denied."""
from dataclasses import dataclass, field, replace

@dataclass(frozen=True)
class Focus:
    pid: int
    window: int
    bounds: tuple
    bundle: str = 'com.microsoft.VSCode'
    title: str = field(default='',compare=False)

def match_window(pid, bounds, windows):
    if bounds is None or len(bounds) != 4:
        return None
    matches = [w for w in windows if w['pid'] == pid and
               all(abs(a-b) <= 2 for a,b in zip(bounds,w['bounds']))]
    return Focus(pid,matches[0]['window'],tuple(bounds)) if len(matches)==1 else None

_asked=set()      # VS Code process ids already asked to expose their accessibility tree

def focused_context(excluded_pids=()):
    try:
        import AppKit
        import Quartz
        import ApplicationServices as AX
        from input_monitor import secure_input_enabled
        if secure_input_enabled() is not False:
            return None
        app=AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app.bundleIdentifier() != 'com.microsoft.VSCode':
            return None
        pid=app.processIdentifier()
        import os
        if pid==os.getpid() or pid in excluded_pids:return None
        error, focused=AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateSystemWide(),'AXFocusedUIElement',None)
        if error in (-25204,-25205,-25212):
            error,focused=AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateApplication(pid),'AXFocusedUIElement',None)
        if error or focused is None:
            # VS Code is built on Chromium, which builds its accessibility tree only after an assistive app asks for it
            # (AXManualAccessibility). Ask once per VS Code process; the tree is ready by the next poll.
            if pid not in _asked:
                _asked.add(pid)
                AX.AXUIElementSetAttributeValue(AX.AXUIElementCreateApplication(pid),'AXManualAccessibility',True)
            return None
        error, owner=AX.AXUIElementGetPid(focused,None)
        if error or owner!=pid: return None
        error,role=AX.AXUIElementCopyAttributeValue(focused,'AXRole',None)
        if error or role not in {'AXTextArea','AXTextField','AXOutline','AXButton','AXGroup','AXScrollArea','AXWebArea'}: return None
        error,subrole=AX.AXUIElementCopyAttributeValue(focused,'AXSubrole',None)
        if subrole=='AXSecureTextField' or error not in (0,-25205,-25212) or role=='AXTextField' and (error or subrole is None): return None
        element=AX.AXUIElementCreateApplication(pid)
        error, window=AX.AXUIElementCopyAttributeValue(element,'AXFocusedWindow',None)
        if error or window is None: return None
        error,position=AX.AXUIElementCopyAttributeValue(window,'AXPosition',None)
        if error: return None
        error,size=AX.AXUIElementCopyAttributeValue(window,'AXSize',None)
        if error: return None
        ok,point=AX.AXValueGetValue(position,AX.kAXValueCGPointType,None)
        if not ok: return None
        ok,extent=AX.AXValueGetValue(size,AX.kAXValueCGSizeType,None)
        if not ok: return None
        bounds=(point.x,point.y,extent.width,extent.height)
        rows=[]
        for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0):
            if w.get('kCGWindowLayer') != 0: continue
            b=w['kCGWindowBounds']
            rows.append(dict(pid=w['kCGWindowOwnerPID'],window=w['kCGWindowNumber'],
                             bounds=(b['X'],b['Y'],b['Width'],b['Height'])))
        result=match_window(pid,bounds,rows)
        error,title=AX.AXUIElementCopyAttributeValue(window,'AXTitle',None)
        return replace(result,title=title if not error and isinstance(title,str) else '') if result else None
    except Exception:
        return None
