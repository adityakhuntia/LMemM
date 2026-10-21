# Project Resume beta — Astra scope proposal

Status: proposed scope, not an approved implementation plan. No feature work or
publication is authorized by this document alone. Prepared with Astra after
reading the actual project state and the user's preference to serve developers
and general knowledge workers together.

## Outcome

Help a person resume an interrupted project without reconstructing context:
recover recorded decisions, unfinished actions and historical supporting evidence.
Use the same experience for coding and research/operations projects.

The next uncertainty is repeated usefulness, not whether we can add more vectors
or graph relationships. LMemM must reduce context reconstruction work compared
with manually pasting material into a generic AI chat.

## First coordination step

The user has now requested publication of the integrated/reviewed local main.
After pulling this delivery, put both founders on that exact commit and run
fresh second-Mac setup. Before this publication, remote main was 9b8efb3 and
the readiness/integration fixes were local. The
current alias app depends on its checkout and venv, so call this a supervised
beta rather than a portable release.

## Minimum scope

1. Create a named project without requiring a coding folder or Codex setup.
2. Save intentional decisions/actions and an explicit excerpt with title and
   source URL. Label excerpts as user-supplied; the URL does not prove the saved
   text matches a live page. No automatic page fetching or passive browsing.
3. Return to a Resume view with last saved activity, recorded decisions and
   open actions. Every item has retained evidence; missing evidence stays absent.
4. Copy project context into the user's preferred AI. Keep VS Code capture and
   AskCodex as optional enhancements with their existing permission/disclosure
   requirements. Generated explanations remain distinct from retained evidence.

Reuse the current retrieval, retention and citation engine. Start with a simple
Save excerpt form. A browser Save selection connector follows only if pilot
users value resuming but find manual saving too burdensome.

## Constraints requiring design before implementation

Project bindings currently require a unique workspace root. Native notes also
use editor-shaped source envelopes, and current retrieval filters local-file
origins. Folder-free enrollment and URL-attributed intentional excerpts therefore
need explicit project/source authority semantics. Hiding the folder picker or
labelling research excerpts as observed VS Code content would be incorrect.

The next spec must define native-note/excerpt source identity, ownership, URL
metadata versus verified observation, migration of existing projects, and exact
revocation/deletion behavior. Do not broaden source permissions implicitly.

## Dependency order

- Specify project identity and intentional sources independent of editor capture.
- Implement that enrollment/source slice with migration and isolation checks.
- Add explicit excerpt saving through the same evidence lifecycle.
- Assemble Resume and context copy from supported evidence.
- Run the shared demo and a pilot with two developers and two knowledge workers.

## Shared demonstration

Use one launch project containing an implementation note, a research excerpt,
an explicit decision and a next action. Close the app and change the original
document. Return after an interruption: recover the decision, verify the retained
historical excerpt and identify the next action. Show an unrelated project's
results staying isolated. Both personas should use the same flow.

## Proposed acceptance

- Each tester creates a project and saves useful context within five minutes.
- After a real interruption, each recovers a correct next action and supporting
  source within two minutes.
- At least three of four return voluntarily on another day. This is a pilot
  signal, not statistical proof of product-market fit.
- Isolation, source removal, deletion, task state and restart checks pass.
- Complete original crash-sequence and sustained-resource acceptance before
  widening access. Second-Mac onboarding must be observed, not inferred.

No testers have been contacted and no pilot results are claimed.

## Effort and exclusions

Astra estimates 8–12 focused engineering days, then a week of pilot observation,
assuming reuse of the existing engine. This is not a delivery commitment. A
nearer launch date calls for testing the existing supervised beta first rather
than promising this whole new scope before it can be built and verified.

Exclude a visual graph explorer, many connectors, fully automatic personal
memory, unsourced narrative generation, mandatory hosted AI and broad passive
browser ingestion. Portable distribution is separate launch work, not solved
by the existing alias build.

The remaining product choice is which real interrupted project anchors the
pilot; it should determine examples and source priorities rather than splitting
the product into separate developer and knowledge-worker apps.
