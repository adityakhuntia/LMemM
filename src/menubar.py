"""LMemM - the menu-bar item: the icon and its menu. It draws menu_model.view() and forwards
clicks; it decides nothing (rule M1-M3 in menu_model.py). Only the drawing is here, so a Mac is
needed to look at it; the words, marks and rows are tested in test_menu_model.py.

The icon is drawn, not a bitmap: macOS re-runs the drawing handler when the menu bar turns
dark or light, so the capsule always reads against the bar.
"""

import objc
from Foundation import NSObject
from AppKit import (NSAttributedString, NSBezierPath, NSColor, NSFont, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSImage, NSMakeRect, NSMakeSize, NSMenu, NSMenuItem,
                    NSMutableAttributedString, NSStatusBar)

import menu_model

ICON_W, ICON_H = 24, 18
VARIABLE_LENGTH = -1                          # NSVariableStatusItemLength


class _MenuTarget(NSObject):
    """Receives the menu's clicks and passes the row's id on."""

    def initWithCallback_(self, callback):
        self = objc.super(_MenuTarget, self).init()
        self.callback = callback
        return self

    def picked_(self, sender):
        self.callback(sender.representedObject())


def _badge_colour(kind):
    return NSColor.systemRedColor() if kind == "red" else NSColor.secondaryLabelColor()


def _draw_icon(spec):
    """An NSImage whose drawing is re-run for the current menu-bar appearance."""
    def draw(rect):
        NSColor.labelColor().setFill()
        w, h = 16, 8
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(1, (ICON_H - h) / 2 - 1, w, h), h / 2, h / 2).fill()
        if spec["badge"]:
            d = 9
            x, y = ICON_W - d - 1, ICON_H - d - 1
            _badge_colour(spec["badge"]).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(x, y, d, d)).fill()
            if spec["glyph"] == "pause":
                NSColor.windowBackgroundColor().setFill()
                NSBezierPath.fillRect_(NSMakeRect(x + 2.6, y + 2.5, 1.3, 4))
                NSBezierPath.fillRect_(NSMakeRect(x + 5.1, y + 2.5, 1.3, 4))
        return True
    image = NSImage.imageWithSize_flipped_drawingHandler_(NSMakeSize(ICON_W, ICON_H), False, draw)
    image.setTemplate_(False)
    return image


def _row_item(row, target):
    """One clickable row. A row with "children" opens a submenu; "detail" is the quiet second
    half of a title ("1 hour  Back on at 4:00 PM")."""
    title = row["title"]
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        title, None if row.get("children") else "picked:", row.get("key", ""))
    if row.get("detail"):
        quiet = NSAttributedString.alloc().initWithString_attributes_(
            "   " + row["detail"], {NSFontAttributeName: NSFont.systemFontOfSize_(12),
                                    NSForegroundColorAttributeName: NSColor.secondaryLabelColor()})
        text = NSMutableAttributedString.alloc().initWithString_attributes_(
            title, {NSFontAttributeName: NSFont.systemFontOfSize_(13)})
        text.appendAttributedString_(quiet)
        item.setAttributedTitle_(text)
    if row.get("children"):
        sub = NSMenu.alloc().init()
        sub.setAutoenablesItems_(False)
        for child in row["children"]:
            sub.addItem_(_row_item(child, target))
        item.setSubmenu_(sub)
    else:
        item.setTarget_(target)
        item.setRepresentedObject_(row["id"])
        item.setEnabled_(row.get("enabled", True))
    return item


def _title_item(text, bold, dot=None):
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(text, None, "")
    font = NSFont.boldSystemFontOfSize_(13) if bold else NSFont.systemFontOfSize_(12)
    colour = NSColor.labelColor() if bold else NSColor.secondaryLabelColor()
    item.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(
        text, {NSFontAttributeName: font, NSForegroundColorAttributeName: colour}))
    item.setEnabled_(False)
    return item


class MenuBar:
    """on_pick(row id) is called when a row is clicked."""

    def __init__(self, on_pick):
        self.target = _MenuTarget.alloc().initWithCallback_(on_pick)
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(VARIABLE_LENGTH)
        self.item.button().setToolTip_("LMemM")
        self.shown = None
        self.update(menu_model.view({}))

    def update(self, view):
        """Redraw only when something a person would see has changed."""
        sig = menu_model.signature(view)
        if sig == self.shown:
            return
        self.shown = sig
        self.item.button().setImage_(_draw_icon(view["icon"]))
        self.item.button().setToolTip_(view["title"])
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.addItem_(_title_item(view["title"], True))
        if view["line"]:
            menu.addItem_(_title_item(view["line"], False))
        menu.addItem_(NSMenuItem.separatorItem())
        for row in view["rows"]:
            if row["id"] == "-":
                menu.addItem_(NSMenuItem.separatorItem())
                continue
            menu.addItem_(_row_item(row, self.target))
        self.item.setMenu_(menu)

    def remove(self):
        NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
