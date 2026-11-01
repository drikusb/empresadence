# Trademark Remediation — Tracking

> Part of the response agreed with EOS Worldwide on their [#17](https://github.com/drikusb/empresadence/issues/17) request.

## Background

EOS Worldwide asked us to either remove their trademarks, terminology, and the two tool copies they identified, or archive the repository. We've chosen to remove and generalize rather than archive. Their full findings and the agreed direction are in [#17](https://github.com/drikusb/empresadence/issues/17) — this document turns that discussion into a concrete, reviewable scope, and tracks what's actually landed against it. Checked against EOS Worldwide's own current list at [branding.eosworldwide.com/us-trademarks](https://branding.eosworldwide.com/us-trademarks/) each time this document is updated.

## Proposed direction (credit: @RCheesley, issue #17)

Rather than swap EOS's names for different-but-equivalent names, make the project genuinely vendor-agnostic: a weekly meeting with a scorecard, quarterly priorities, to-dos, issue-solving, a vision document and a roles chart are shared by EOS, Scaling Up, 4DX, and others — none of that structure belongs to anyone. We ship generic names and a generic default agenda; each organisation can relabel things in their own instance if they want their own vocabulary. That's user content at that point, not something we ship, and it also opens the project to teams who aren't running EOS at all.

## Status

### 1. Project identity — in progress
- The project name itself: **done**. Repo renamed from OpenEOS to **Empresadence** ("EPD" for short — see #58's discussion). Remaining literal "OpenEOS"/"openeos" strings in code and docs swept in #83.
- ~~"EOS App" as the sender name (`DEFAULT_FROM_EMAIL`) and LICENSE copyright holder~~ — **done, #84 (merged).** Both now read Empresadence.
- ~~The "open-source EOS framework" wording, and the `EOS®`/`Entrepreneurial Operating System® (EOS®)`/`V/TO®`/`Level 10 Meeting®`/`IDS®`/`The Accountability Chart®` marks spelled out throughout~~ — **done, #100 (merged).** See item 6 below.
- No statement of trademark ownership or non-affiliation yet — still an open question (see below).

### 2 & 3. Hardcoded trademarked and generic terms — defaults flipped
The per-organisation branding and terminology system landed (#59–#61), and every area of the app now reads its vocabulary from it instead of hardcoding English words:

| Area | PR | Status |
|---|---|---|
| Branding (product name, logo, colour) | #60 | Merged |
| Per-organisation terminology, overridable | #61 | Merged |
| Page titles carry the brand instead of "EOS App" | #62 | Merged |
| To-Dos | #64 | Merged |
| Scorecards, VTO | #65 | Merged |
| Issues / IDS | #66 | Merged |
| Rocks | #67 | Merged |
| Meetings, home dashboard, search, notifications | #68 | Merged |
| Team page module tiles | #72 | Merged |

**Resolved in #90 (merged):** the shipped *defaults* in `Terms` used to be EOS Worldwide's literal words (Rock, Scorecard, Level 10 Meeting, VTO, IDS, Accountability Chart, Segue, Headlines, Cascading Messages, Seat, Core Value, Milestone) — meaning any organisation that never visited its Terminology settings saw the EOS vocabulary exactly as before, which was every organisation on a fresh install. #90 flipped every default to a generic word (Priority, Metrics Board, Weekly Meeting, PRS, Org Chart, Check-in, Headlines→Update, Cascading Messages→Key Message, Role, Value, Step), satisfying EOS Worldwide's core request. The `vto` term's `description` field was flipped in the same PR, away from the literal "Vision/Traction Organizer."

The `vto` term's own default word has since moved again, in #96 (merged): "Vision Plan" → **"Vision and Delivery Board"**, decided with @RCheesley's input on #91 (she proposed the Vision/Execution-or-Delivery split; "Vision and Delivery Board" was chosen over "Vision and Execution Board" as the less clichéd, more outcome-oriented option). #91 itself is now superseded by #96/#97 and should be closed without merging.

~~The "EOS recommends ..." lines were swept for their noun but still say "EOS recommends" literally~~ — **done, #84 (merged).** Reworded to "We recommend ...".

One further hardcoded-term spot, already resolved:
- `templates/vto/vto_detail.html` and `vto_print.html` (now `templates/vision/vision_detail.html` and `vision_print.html`) — the second printed page used to be headed literally "Page 2 — Traction." `Traction®` is its own standalone registered mark (the book), separate from `V/TO®`. **Resolved in #96 (merged):** now headed "Page 2 — Delivery."

### 4. The two structural copies — not started
- The V/TO's fixed section structure and two-page print layout: still fixed. `VTOSection`'s `SectionKey` choices are unchanged.
- The Level 10 Meeting agenda's exact segment timings (`[5, 5, 5, 5, 5, 60, 5]`): still fixed. `SEGMENT_NAMES`/`SEGMENT_DURATIONS` in `apps/meetings/models.py` are unchanged; only the *display* name per segment is configurable now, not the segment list or durations.

### 5. README, docs, repo identity — mostly done
~~README.md's top-level framework description, the Features table, and CONTRIBUTING.md all still read "the full **Entrepreneurial Operating System® (EOS®)** framework," with every module's registered mark (V/TO®, Level 10 Meeting®, IDS®, The Accountability Chart®) spelled out.~~ **Done, #100 (merged):** both files reworded with generic, vendor-neutral copy and the app's own default terminology words. The GitHub repo description is also updated (manual step, done directly in repo settings — not something this tooling can change). The README still has a rendering bug unrelated to this effort — the "on hold" banner was pasted in as a raw diff block and needs fixing regardless; left alone in #100 since it's gated on item 5 below (the structural-copy work) too, not just this sweep.

A few more hardcoded literals turned up while reviewing unrelated community PRs (#93/#95) — missed by every earlier sweep because none is a template-variable substitution: `templates/home.html`'s "EOS Dashboard" heading, "Identify, Discuss, Solve", and "Vision/Traction Organizer"; `templates/accounts/org_terminology.html`'s "EOS building blocks"; `templates/todos/todo_form.html`'s "EOS standard: 7 days from today." Also found in the same pass: `templates/accounts/org_export.html` used `{% block title %}` instead of `{% block page_title %}`, which both hardcoded "EOS App" *and* silently broke per-organisation branding on that one page (it never got the org's brand suffix every other page gets). **All done, #102 (merged).**

### 6. Found in a full sweep against EOS Worldwide's current trademark list — new, not previously tracked
A pass through every file in the repo against [the live US trademark list](https://branding.eosworldwide.com/us-trademarks/) (not just the terms the original 2026-10-16 audit anticipated) turned up several items the area-by-area PRs never touched, because they aren't in `apps/` or `templates/` at all:

- ~~**`.braintree/brain.json` and `.claude/agents/*.md`**~~ — **done.** Both removed from the repo.
- ~~**`static/css/eos.css`**~~ — **done, #84 (merged).** Renamed to `app.css`.
- ~~**`LICENSE`**~~ — **done, #84 (merged).** Copyright line now reads "Empresadence Contributors."
- ~~**`apps/accounts/portability/export.py`**~~ — **done, #99 (merged).** The generated `README.txt`'s record-type sentence named "V/TO" directly (landed with #51, after the original audit) and, found in the same sentence while fixing it, also spelled out "Accountability Chart" and "Level 10 Meeting" — both separately registered. All three replaced with the app's own generic words.
- ~~**`templates/accountability/chart.html`, `node_form.html`**~~ — **done, #84 (merged).** The "typically Visionary and Integrator" example text and the form's placeholder attribute both reworded to CEO/COO.
- ~~**`docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example`**~~ — **done, #98 (merged).** Default DB name/user/password renamed from the `eos_` prefix to `epd_`; `config/settings/base.py`'s own fallback defaults and the README's env var table, found while fixing it, were also still on `eos_`.

## The project's new name — agreed and executed at the repo level

**Empresadence** ("EPD" for short) — agreed between @drikusb and @RCheesley in #58's discussion. The GitHub repo itself has been renamed (now `drikusb/empresadence`), and the leftover "OpenEOS" references in code and docs were swept in #83.

Quick collision checks run so far (not a substitute for a real trademark search):

| Candidate | Result |
|---|---|
| Cadence | Taken — registered mark of Cadence Design Systems (EDA software, actively defended) |
| Helm | Likely collides — Helm is the Kubernetes package manager |
| Compass | Heavily crowded |
| Pulse / PulseOS | Taken — an existing "business operating system" product, same category |
| Keel | Taken — an existing no-code/ERP business platform, same category |
| Flywheel | Taken — registered mark + an existing content/growth tool |
| Trajectory | Taken — an existing project-management tool, same category |
| Wayfinder | Taken — multiple existing open-source projects with this name |
| Groundwork | Existing registered open-source company (different space — IT monitoring — lower risk, but not clean) |
| Northline | No collision found |
| Empresadence / EPD | Agreed direction; full check below not yet run |

**Still outstanding:** the full check proposed earlier — GitHub, PyPI, domain availability, and a UK/EU/US trademark search for Empresadence/EPD specifically. The repo and code now carry the name ahead of that check clearing; worth prioritising if there's any risk it doesn't.

## What's actually left, in order

1. ~~Pick generic default words for every `Terms` entry and flip `DEFAULTS` in `apps/accounts/terminology.py`~~ — **done, #90 (merged).**
2. ~~Reword the "EOS recommends" lines~~ — **done, #84 (merged).** ~~The "Page 2 — Traction" VTO print/detail heading~~ — **done, #96 (merged).** **Item fully addressed.**
3. ~~Replace "Visionary" / "Integrator" in the Accountability Chart's example placeholder text with vendor-neutral examples~~ — **done, #84 (merged).** This was already shipped before this round of work started; the tracking doc just hadn't caught up. **Item fully addressed.**
4. ~~Rename `apps/vto` (the Django app itself)~~ — **done, #96 (merged); the package is now `apps.vision`, served at `/vision/`.** ~~Clear the remaining "EOS App" occurrences (email sender name, LICENSE copyright line)~~ — **done, #84 (merged).** ~~The `eos_`-prefixed infra defaults~~ — **done, #98 (merged).** **Item fully addressed.**
5. Turn the V/TO's section list and the meeting's segment timings into admin-configurable structures instead of fixed copies — not started. The one area still genuinely unscoped — see open questions below.
6. ~~Sweep README, CONTRIBUTING, repo description and GitHub topics~~ — **done, #100 (merged) plus the repo description, updated directly, plus #102 (merged) for a handful more literals found during unrelated PR review.** GitHub topics are still empty; adding some is purely additive (not a trademark fix), so left for whenever, not tracked here as a blocker.
7. Fix the README's broken diff-block rendering and take the "on hold" banner down once 1–6 land — not started, blocked on item 5 above.

**So what's genuinely still open: just item 5** (the structural-copy work) **and item 7** (blocked on it). Every other item — 1 through 4, and 6 — is fully merged.

## Open questions

- ~~Who picks the generic default words~~ — **resolved.** The `Terms` defaults themselves landed in #90. The renamed `apps/vto` package's name and the `vto` term's resulting default word were discussed on #91 with @RCheesley and decided there (see above). #91 was a discussion-only PR with no code; close it without merging once #96 is confirmed landed, since its draft text is now stale.
- Does the structural-copy fix (step 5 above) want its own design discussion before a PR, given it's the one area that's still genuinely unscoped? **Still open — this is the next thing to resolve.**
- Is a trademark/non-affiliation statement wanted in the README once the above lands, or is removal alone sufficient? **Still open.**
