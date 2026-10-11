"""LMemM - sample project histories for trying Resume this project without waiting for real work.

Four projects, one for each return moment the brief has to handle honestly:

    Remote work essay   rich       your notes, a task reading, text seen, one decision quote
    Garage shelves      limited    one window, no notes, nothing readable
    Tax 2024            stale      good history, nothing for 5 weeks
    Pricing page        conflict   two places that read like different decisions

`build(now)` returns (registry, items, book); `seed(dir)` writes them as a data folder LMemM can start on, so the
real memory is never touched. Everything here is made up.
"""

from datetime import datetime, timedelta

import config
import notes
import projects
import store


def _item(iid, app, title, last, seconds=600, visits=3, lines=(), quotes=(), url=None, note_texts=(), project=None):
    iso = last.isoformat(timespec="seconds")
    item = {"id": iid, "app": app, "kind": "document", "title": title, "doing": "Working", "mostly": "reading",
            "activity": {c: {"seconds": 0, "text": []} for c in store.CATEGORIES}, "first_seen": iso, "last_seen": iso,
            "seconds": seconds, "visits": visits, "updates": visits, "ref": f"{app}|document|{iid}", "project_id": project}
    if lines or quotes:
        item["content"] = {"version": 1, "excerpts": [
            {"id": f"{iid}-{n}", "text": text, "source": {"app": app, "window": title, "url": url},
             "first_seen": iso, "last_seen": iso, "decision_quotes": list(quotes) if n == 0 else []}
            for n, text in enumerate(lines)] or [
            {"id": f"{iid}-q", "text": "", "source": {"app": app, "window": title, "url": url}, "first_seen": iso,
             "last_seen": iso, "decision_quotes": list(quotes)}]}
    item["notes"] = [{"at": (last - timedelta(minutes=5 * (n + 1))).isoformat(timespec="seconds"), "text": t}
                     for n, t in enumerate(note_texts)]
    return item


def build(now=None):
    now = now or datetime.now()
    reg = projects.empty()
    essay, garage, tax, pricing = (projects.create(reg, n, now=now) for n in
                                   ("Remote work essay", "Garage shelves", "Tax 2024", "Pricing page"))
    items = {}

    def add(item):
        items[item["id"]] = item

    h = lambda **d: now - timedelta(**d)
    add(_item("e1", "Google Docs", "Remote work essay - draft 3", h(hours=19), 2400, 6, project=essay,
              url="https://docs.google.com/document/d/essay-demo/edit",
              lines=["The case for async work rests on one claim: that the best hours of the day belong to the person, not the calendar.",
                     "Section 3 still needs the counter-argument about onboarding new people remotely."],
              quotes=["We decided to lead with the focus-time argument and move the cost argument to section 4."],
              note_texts=["Write the onboarding counter-argument for section 3", "Is the 2023 Stanford figure still the right citation?"]))
    add(_item("e2", "Safari", "Stanford remote work study - summary", h(hours=21), 900, 2, project=essay,
              url="https://example.org/remote-work-study",
              lines=["Employees working from home two days a week were as productive and 33 percent less likely to quit."]))
    add(_item("e3", "Notes", "Essay outline", h(days=3), 300, 2, project=essay,
              lines=["Outline: focus time, async habits, onboarding, cost, what managers should change."]))
    add(_item("g1", "Safari", "Garage shelving ideas", h(days=2, hours=3), 120, 1, project=garage))
    add(_item("t1", "Numbers", "2024 income and deductions", h(days=38), 1500, 4, project=tax,
              lines=["Total deductible expenses so far: home office, software, and the laptop purchase from March."],
              note_texts=["Ask the accountant whether the laptop counts as equipment"]))
    add(_item("t2", "Preview", "Receipts - March", h(days=40), 300, 1, project=tax))
    add(_item("p1", "Google Docs", "Pricing page copy", h(days=1, hours=2), 1200, 3, project=pricing,
              url="https://docs.google.com/document/d/pricing-demo/edit",
              lines=["Starter, Team and Business plans, billed monthly or yearly."],
              quotes=["Decision: two plans only, Starter at $9 and Team at $29."]))
    add(_item("p2", "Slack", "#growth - pricing thread", h(days=1, hours=5), 400, 2, project=pricing,
              lines=["Agreed in the thread: we ship three plans, Starter, Team and Business, and drop the free tier."],
              quotes=["We agreed to ship three plans and drop the free tier."],
              note_texts=["Who signs off on the final price list?"]))
    book = {"demo": {"at": h(hours=19).isoformat(timespec="seconds"), "tasks": [
        {"title": "Finish the remote work essay", "goal": "Finish the essay arguing that async work protects focus time.",
         "stage": "building", "items": ["e1", "e2"], "open": "Write the onboarding counter-argument in section 3."}]}}
    return reg, items, book


def seed(data_dir, now=None):
    """Write the sample histories as a data folder; returns the project ids by name."""
    reg, items, book = build(now)
    import json
    import os
    import tasks
    with config.use_paths(data_dir):
        os.makedirs(config.paths().memory_dir, exist_ok=True)
        store.save_memory(items)
        projects.save(reg)
        with open(tasks.tasks_path(), "w") as fh:
            json.dump(book, fh)
    return {p["name"]: pid for pid, p in reg["projects"].items()}
