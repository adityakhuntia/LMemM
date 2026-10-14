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

## v1.1: work threads, scope and noise (PR 25 Session 2 regression)

Rules R26 to R31 are in `src/evidence.py` and `src/resume.py`; the regression is `tests/test_resume_pr25.py` on
`tests/fixtures/pr25_session2.json` (TEST DATA, a trimmed copy of the real snapshot with contact names redacted).

- Things filed in a project are one body of work, but notes on the thread of the latest activity rank first, and the
  newest note no longer wins on recency alone.
- Things not filed anywhere are grouped into work threads only on shared evidence (a distinctive word seen in 3 or more
  places, or one strong token such as 180DC). Asked for a scope, Resume leads with the thread that names it, lists the other
  threads apart ("Other open work"), and says the project link is unconfirmed. No scope and no clear lead, or a scope nothing
  names: it lists candidates and asks.
- LMemM's own files and screens (its logs, memory, status) and garbled text are left out. AI chat text is never quoted.
- With no usable note, an AI chat that was mid-task at the end is offered as a "likely continuation", never as your plan.

    python3 lmemm.py catchup --scope "PR 25" --memory path/to/memory.json --now 2026-10-12T04:23:00   # read only
    python3 lmemm.py catchup --memory path/to/memory.json                 # asks which work
    python3 lmemm.py catchup --scope "PR 25" --memory FILE --pick ID      # resume a listed candidate

Window: the filed-project page shows the why and confidence under the next step and a "Left out" line. Scope and candidate
choosing are command-line only so far.

## v1.2: next step from your own words

- Typed text is rebuilt from the event trail (`evidence.authored_messages`) and used before anything else: your words, then notes, then the task book. Assistant text only appears as context, never as intent. Recency only breaks ties.
- The generic "open the conversation and see what it finished" step is gone. With no supported continuation Resume says: "I can identify the work, but I can't reliably tell what you planned to do next."
- Shared-word explanations are gone (R28). Only strong shared tokens (e.g. `180dc`) merge threads; weaker overlap shows as "Possibly related (uncertain)".
- `resume_cli --trail FILE` reads a trail copy (read only). The window does not pass trail events yet.
- Not supported by the snapshot: that UI code was pushed or untested on a Mac.

## v1.3: what became of a request, and your corrections

- R33 (evidence.py): a request is intent when written, not proof it is open; a reply is not proof it is done. Statuses: completed (you said so later in that chat), open (you chased it), likely addressed (the screen showed Claude working after it, only when that window holds one chat), unknown (everything else). Claude's replies are speaker-less OCR and establish nothing.
- The next step is an open note on the thread, else a chased request, else "check where it got to" (open that conversation), else "I can identify the work, but I can't reliably tell what you planned to do next. Open the most recent source."
- R34 (resume_feedback.py): Right, Outdated, Edit, Don't use this source. Own file `resume_feedback.json`; memory and trail are never edited. CLI: `--feedback FILE --mark right|outdated --replace TEXT --exclude ITEM`.
- Window: buttons under the next step (Right / Outdated / Edit… / Don't use this source). Written without a Mac to run them on: not yet exercised.

## v1.4: short top, evidence underneath

- R35: the brief opens with one sentence and one action (`brief["top"]`: headline, action label/item). Statuses and quotes are unchanged but sit under "Why this suggestion?" in four groups that are never mixed: what you wrote, what the app observed, what Resume inferred, what Resume cannot determine.
- The headline quotes your words ("You asked Claude: “…”") instead of paraphrasing them; it adds no action the evidence does not support.
- Chat attribution: typed messages are matched to chats by the event trail; only the "running a command" screen observation is called untied when its window held several chats.
- The Mac window was not run for this change (no AppKit in the build container). To try: `python3 lmemm.py --demo-resume`, open a project, Resume.

## v1.6: the disclosure explains the recommendation

- `top["because"]`: one plain reason for the action (the only/most recent source; your latest request and what LMemM cannot read; your open note), including what the action cannot open. Shown first when the row is expanded; evidence follows with sources and times.
- The row is a bordered card with a chevron, labelled by the action ("Why open Safari?"), not bare blue text.
- Buttons are named for their destination: Open Safari (the app, not the page), Show in LMemM, Copy text for an AI chat.
- Demo mode (`config.DEMO`) shows a calm "Demo" banner instead of "Setup is not finished".
- The limited note is now only the counts; the recommendation is not repeated under it.

## v1.7: open the exact source (source_ref.py, R36-R39)

- Capture: `tracker.update_item` keeps `item["source"] = {kind: url|file, value, app, title, seen}` from the frame's browser address (AppleScript, already read for the skip rules) or the focused window's `AXDocument` file:// address. The newest valid address wins; a frame without one leaves the old one.
- Kept only when plain and safe: http(s) only, no user:password, no token-like query values, no sensitive sites (config.SKIP_SITES), no private folders for files. Skipped apps, private windows and unwatched apps never reach this code.
- Reopening: `resume.open_command` -> `open -a <browser> <url>` (the browser it was seen in) or `open <path>`. Checked again first (R39); a missing file or a malformed address becomes a plain sentence, not a guess.
- No address: the primary button is Show in LMemM (the saved title). Open <App> is offered as what it is: it starts the app only.
- Older items have no `source`; Resume still reads an address from their saved text excerpts.
- Never sent to a model; never printed in the copied brief.
- Not exact today: apps that expose neither a web address nor a document path (Claude and ChatGPT desktop apps, Slack, WhatsApp, VS Code windows, Terminal, Mail messages). Chat apps would need a deep link the app doesn't publish through accessibility.
