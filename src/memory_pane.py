"""LMemM - the Memory tab's drawing. The words, rows and groups it shows come from memory_view.py (pure, tested)."""

from AppKit import NSBezierPath, NSColor, NSFont, NSMakeRect, NSScrollView, NSTextField, NSTextView
import objc

import setup_kit as kit
from memory_view import ADMIN_GROUPS, evidence_rows, pause_action, source_presentation, state_tone
from widget import _Fields, _Flipped, _Tap


def when(stamp, empty):
    """An ISO time as words for a person ("Oct 14, 6:03 PM", in their time zone); `empty` when there is none."""
    if not stamp:
        return empty
    try:
        from datetime import datetime
        moment = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if moment.tzinfo is not None:
            moment = moment.astimezone()
        return moment.strftime('%b %-d, %-I:%M %p')
    except (ValueError, TypeError):
        return str(stamp)


class _StateDot(_Flipped):
    """The small round dot beside the state."""

    def initWithTone_(self, tone):
        self = objc.super(_StateDot, self).initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.tone = tone
        return self

    def drawRect_(self, rect):
        {"good": NSColor.systemGreenColor(), "accent": kit.accent(), "warn": NSColor.systemOrangeColor()}.get(
            self.tone, NSColor.tertiaryLabelColor()).setFill()
        NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(1, 1, 8, 8)).fill()


class MemoryPane:
    def __init__(self, on_action):
        self.project = None
        self.show_admin = False                      # "Connections and setup" is folded until asked for
        self.action = on_action
        self.host = _Flipped.alloc().initWithFrame_(NSMakeRect(0, 0, 800, 600))
        self.query_typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: self.action('query', {'text': text}), lambda text: self.action('submit', {}),
            lambda: self.action('query', {'text': ''}))
        self.query = self._field(self.query_typing, 'Search this project’s memory', 'Search project memory')
        self.note_typing = _Fields.alloc().initWithChange_submit_cancel_(
            lambda text: None, self._save_note, lambda: self.note.setStringValue_(''))
        self.note = self._field(self.note_typing, 'Add a project note', 'New intentional project note')
        self.host.addSubview_(self.query)
        self.host.addSubview_(self.note)

    @staticmethod
    def _field(delegate, placeholder, label):
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 30))
        field.setBezeled_(True)
        field.setBezelStyle_(1)
        field.setDelegate_(delegate)
        field.setPlaceholderString_(placeholder)
        field.setAccessibilityLabel_(label)
        return field

    def _save_note(self, text):
        if text.strip():
            self.action('note', {'text': text})
            self.note.setStringValue_('')

    def render(self, view, width=800, x=32, w=None):
        w = w or width - 64
        host = self.host
        for sub in list(host.subviews()):
            if sub is not self.query and sub is not self.note:
                sub.removeFromSuperview()
        y = 16

        def text(value, size=13, weight=400, color=None, gap=10):
            nonlocal y
            y += kit.put_text(host, str(value), x, y, w, size, weight, color or kit.ink()) + gap

        def buttons(items):
            """Small buttons side by side, wrapping when the column is narrow: (label, action, payload, kind)."""
            nonlocal y
            cx = x
            for label, action, payload, kind, *rest in items:
                enabled = rest[0] if rest else True
                wide = min(w, kit.text_width(label, 13, 500) + 28)       # never wider than the column: the label is not cut
                if cx > x and cx + wide > x + w:
                    cx, y = x, y + 38
                kit.button(host, label, cx, y, wide, 32, (lambda a=action, p=payload: self.action(a, p or {})),
                           kind=kind, size=13, weight=500, enabled=enabled)
                cx += wide + 8
            y += 44

        def card(build):
            """A soft box; build(box, inner width) draws inside it from (14, 12) and returns the inner height."""
            nonlocal y
            box = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, 10), None)
            box.fill = True
            inner = build(box, w - 28)
            box.setFrame_(NSMakeRect(x, y, w, inner + 24))
            host.addSubview_(box)
            y += inner + 24 + 10

        def in_card(box, value, top, inner, size=13, weight=400, color=None):
            return kit.put_text(box, str(value), 14, 12 + top, inner, size, weight, color or kit.ink())

        # -- status, and the two actions that apply right now
        mode = view['state']
        dot = _StateDot.alloc().initWithTone_(state_tone(mode))
        dot.setFrame_(NSMakeRect(x, y + 6, 10, 10))
        host.addSubview_(dot)
        kit.put_text(host, mode, x + 18, y, 220, 15, 700, wrap=False, height=22)
        right = x + w
        binding = view.get('binding')
        shown = ([pause_action(mode)] if pause_action(mode) else []) + ([('Refresh', 'refresh')] if binding else [])
        for label, action in reversed(shown):
            wide = kit.text_width(label, 13, 500) + 28
            right -= wide
            kit.button(host, label, right, y - 4, wide, 30, (lambda a=action: self.action(a, {})), kind='quiet', size=13, weight=500)
            right -= 8
        y += 30
        text(view['message'], 13, 400, kit.mute(), gap=8)
        status = view.get('status', {})
        if binding:
            text('Enrolled ' + when(status.get('enrolled_at') or binding.get('enrolled_at'), 'unknown') + ' · last indexed '
                 + when(status.get('indexed_at'), 'not yet') + ' · ' + str(status.get('pending', 0)) + ' waiting',
                 12, 400, kit.mute())
        if view.get('error'):
            y += kit.note(host, 'warn', str(view['error']), x, y, w) + 12
        if mode == 'Needs attention':
            buttons([('Recover saved notes', 'recover_native_notes', None, 'primary')])
        project = binding.get('project_id') if binding else None
        if project != self.project:
            self.project = project
            self.note.setStringValue_('')
        if str(self.query.stringValue()) != view['query']:
            self.query.setStringValue_(view['query'])
        self.query.setHidden_(not binding)
        self.note.setHidden_(not binding)

        if not binding:
            text('Choose one workspace folder. Only new text you view in VS Code, and notes you add yourself, are kept. '
                 'Nothing is scanned and no history is imported.')
            busy = view.get('busy')
            if busy:                                              # the press was heard: say so, and stop a second press
                buttons([(busy, 'choose_root', None, 'primary', False)])
                text('Starting the memory service and setting up this workspace. This can take a few seconds. '
                     'If it fails, the reason appears here.', 12, 400, kit.mute())
            else:
                buttons([('Enable Memory…', 'choose_root', None, 'primary')])
        else:
            text(binding['workspace_root'], 12, 400, kit.mute(), gap=12)
            self.query.setFrame_(NSMakeRect(x, y, w, 32))
            y += 44
            buttons([(period, 'time_filter', {'period': period}, 'primary' if period == view['period'] else 'quiet')
                     for period in view['periods']])
            if view['loading']:
                text('Searching…', 13, 400, kit.mute())
            if view['empty']:
                text(view['empty'], 14, 500)
            previous = None
            for row in ([] if view.get('source') else evidence_rows(view['result'])):
                if row['section'] != previous:
                    text(row['section'], 15, 700, gap=8)
                    previous = row['section']

                def evidence(box, inner, row=row):
                    top = in_card(box, row['text'], 0, inner, 14, 500) + 6
                    notes = [row['provenance'] + (' · shortened excerpt' if row['truncated'] else ''),
                             row['reason'], (row['at'] + '  ' + row['locator']).strip()]
                    for line in notes:
                        if line:
                            top += in_card(box, line, top, inner, 12, 400, kit.mute()) + 2
                    if row['citation_id']:
                        kit.button(box, 'View retained source', 14, 12 + top + 6, kit.text_width('View retained source', 12, 500) + 24,
                                   28, (lambda c=row['citation_id']: self.action('source', {'citation_id': c})),
                                   kind='quiet', size=12, weight=500)
                        top += 40
                    return top
                card(evidence)
            source = view.get('source')
            if source:
                p = source_presentation(source)

                def detail(box, inner):
                    top = in_card(box, 'Retained source', 0, inner, 16, 700) + 8
                    top += in_card(box, p['locator'] + '  ·  ' + p['at'], top, inner, 12, 400, kit.mute()) + 2
                    top += in_card(box, p['provenance'] + (' · shortened excerpt' if p['truncated'] else ''), top, inner, 12, 400, kit.mute()) + 10
                    top += in_card(box, p['text'], top, inner, 14) + 10
                    top += in_card(box, p['open_explanation'], top, inner, 12, 400, kit.mute()) + 8
                    return top
                card(detail)
                items = [('Close source', 'close_source', None, 'quiet')]
                if p['open_enabled']:
                    items.insert(0, ('Open current file…', 'open_file', {'citation_id': source['citation_id']}, 'quiet'))
                buttons(items)

            text('Project notes', 15, 700, gap=6)
            text('Start with “TODO:” for a task, or “We decided … because …” to record a decision and its reason. Return saves.',
                 12, 400, kit.mute())
            self.note.setFrame_(NSMakeRect(x, y, w, 32))
            y += 52

            # -- set up once, then leave alone
            showing = self.show_admin or bool(view.get('preview'))
            kit.button(host, 'Connections and setup  ' + ('▴' if showing else '▾'), x, y, kit.text_width('Connections and setup  ▾', 13, 600) + 24,
                       32, (lambda: self.action('toggle_admin', {})), kind='ghost', size=13, weight=600)
            y += 44
            if showing:
                for title, line, items in ADMIN_GROUPS:
                    if title == 'Stop':
                        rule = kit._KitRule.alloc().initWithFrame_(NSMakeRect(x, y, w, 1))
                        host.addSubview_(rule)
                        y += 16
                    text(title, 14, 700, gap=4)
                    text(line, 12, 400, kit.mute(), gap=8)
                    buttons([(label, action, None, kind) for label, action, kind in items])
                    if title == 'Codex' and view.get('preview'):
                        import json
                        text('Proposed context for Codex · no access granted' if view['preview'].get('proposed')
                             else 'Exact context preview for Codex', 13, 600, gap=6)
                        box = _Tap.alloc().initWithFrame_callback_(NSMakeRect(x, y, w, 200), None)
                        box.fill = True
                        host.addSubview_(box)
                        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(8, 8, w - 16, 184))
                        scroll.setDrawsBackground_(False)
                        scroll.setHasVerticalScroller_(True)
                        scroll.setBorderType_(0)
                        mono = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, w - 16, 184))
                        mono.setEditable_(False)
                        mono.setSelectable_(True)
                        mono.setDrawsBackground_(False)
                        mono.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
                        mono.setString_(json.dumps(view['preview'], ensure_ascii=False, indent=2))
                        mono.setVerticallyResizable_(True)
                        mono.setHorizontallyResizable_(False)
                        mono.textContainer().setWidthTracksTextView_(True)
                        mono.setAccessibilityLabel_('Exact context preview')
                        scroll.setDocumentView_(mono)
                        box.addSubview_(scroll)
                        y += 210
                        buttons([('Copy context preview', 'copy_preview', None, 'quiet')])
        self.host.setFrame_(NSMakeRect(0, 0, width, max(y + 24, 500)))
        return y + 24
