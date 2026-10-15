"""Why does LMemM not verify the VS Code window? Run this, switch to VS Code within 5 seconds, and read the steps.

    .venv/bin/python scripts/focus_check.py

It runs the same checks as semantic_memory/live_focus.py and prints the first one that fails. It prints only
metadata (names of roles, error codes, the window title), never file text. Terminal itself needs Accessibility to run it."""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))


def say(step, value):
    print(f'{step:<32}{value}')


def main():
    import AppKit, Quartz
    import ApplicationServices as AX
    from input_monitor import secure_input_enabled
    say('this program may see windows', AX.AXIsProcessTrusted())
    print('Switch to VS Code now. Click inside a file.')
    for n in range(5, 0, -1):
        print(n, end=' ', flush=True)
        time.sleep(1)
    print()
    say('secure keyboard input is off', secure_input_enabled() is False)
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    say('frontmost app', app.bundleIdentifier())
    if app.bundleIdentifier() != 'com.microsoft.VSCode':
        return say('RESULT', 'VS Code was not in front')
    pid = app.processIdentifier()
    error, focused = AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateSystemWide(), 'AXFocusedUIElement', None)
    say('focused element (system)', 'error %s' % error if error else 'found')
    if error in (-25204, -25205, -25212):
        error, focused = AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateApplication(pid), 'AXFocusedUIElement', None)
        say('focused element (app)', 'error %s' % error if error else 'found')
    if error or focused is None:
        return say('RESULT', 'VS Code does not expose its focused element (error %s)' % error)
    _e, role = AX.AXUIElementCopyAttributeValue(focused, 'AXRole', None)
    _e, subrole = AX.AXUIElementCopyAttributeValue(focused, 'AXSubrole', None)
    say('role / subrole', '%s / %s' % (role, subrole))
    element = AX.AXUIElementCreateApplication(pid)
    error, window = AX.AXUIElementCopyAttributeValue(element, 'AXFocusedWindow', None)
    say('focused window', 'error %s' % error if error else 'found')
    if error or window is None:
        return say('RESULT', 'no focused window')
    _e, title = AX.AXUIElementCopyAttributeValue(window, 'AXTitle', None)
    say('window title', title)
    say('title names an LMemM tab', isinstance(title, str) and 'LMemM ' in title)
    print('Done. Send me everything above.')


if __name__ == '__main__':
    main()
