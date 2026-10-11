# Resume project (v1)

Open a project, and in about 30 seconds know where you left off and where each line came from. Rules R20 to R25 are in
`src/resume.py` (tests in `tests/test_resume.py`); `src/window.py` only draws them. Nothing new is captured or stored, no
model is called, the pill is unchanged, and corrections are not stored yet.

## The journey

1. Open LMemM and a project (sidebar, Home, a search result). The project page has a **Resume project** button beside
   "+ Sub-project". It is blue when you have been away 4 hours or more, otherwise grey. Nothing pops up by itself.
2. The page opens at once (it is built from memory already on this Mac). Top: **Open original** (the web address LMemM saw
   for the latest thing, else its app), **Open in LMemM**, **Copy for an AI chat**.
3. The brief, in this order, each only when it has a source: *What you seem to be doing* (AI inference, task book only),
   *Where things stand*, *Open question or blocker* (your note that asks something), *Suggested next step* (your newest
   open note, else the task book's open step, else none), then **Show details** (other open notes, possible decisions,
   last seen on screen).
4. Every line shows its kind and source: **✎ From your note**, **◉ Seen on screen** / **Seen, not confirmed**,
   **✦ AI inference**, then the thing's title and how long ago. Tap the line to open the thing's page in LMemM; **Open
   original** opens the web address or app. Nothing is edited, sent or marked done.
5. Thin or old history says so: *limited context* (only the latest thing is shown) and *nothing new for N weeks, may be out
   of date*. Several decision-looking quotes in different places are shown side by side as "may not agree".
6. A footer says what was used and that no model was asked and nothing left the Mac.

## Try it in a minute

    python3 lmemm.py start --demo-resume        # window opens on four made-up projects; real memory untouched, no Claude calls
    python3 lmemm.py catchup "Tax 2024" --demo   # the same brief as text (also: Remote work essay, Garage shelves, Pricing page)
    python3 lmemm.py catchup MyProject --copy    # a real project's brief, copied

| Demo project | Shows |
|---|---|
| Remote work essay | rich: AI reading, your notes, a question, a decision quote, what was on screen |
| Garage shelves | limited: one window, nothing else; says so |
| Tax 2024 | stale: 5 weeks old; says so |
| Pricing page | conflicting: two places read like different decisions; both shown, none picked |

## Not in v1

"Since you were away" (there is no per-project last-visit time), That's right / Outdated / Edit / Don't use this source
(needs a store), a model-written summary, a pill entry point, opening the exact file or tab (only a web address or app).
Writing capture is not used (only what is in memory.json and tasks.json), so a project with no notes and no task reading
will often be "limited".
