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

### 4. The two structural copies — done
- The V/TO's fixed section structure and two-page print layout: **resolved, #106 (merged).** `apps/vision/structure.py` ships the existing 14-section layout as a default, overridable per organisation via new `VisionPage`/`VisionSectionGroup`/`VisionSectionDefinition` rows; an organisation with no override rows sees the shipped default, unchanged.
- The Level 10 Meeting agenda's exact segment timings (`[5, 5, 5, 5, 5, 60, 5]`): **resolved, #107 (merged).** `apps/meetings/segments.py` ships the existing 7-segment agenda as a default, overridable per organisation via a new `MeetingSegmentDefinition` model; `Meeting.agenda` freezes the resolved agenda at creation time so existing meetings' positional segment indices are never silently reinterpreted by a later change to an org's live configuration. The trailing "Conclude" segment is always present and not configurable — it's the only UI path to ever finish a meeting.
- The design proposal that scoped this work, incorporating @RCheesley's review feedback (the vocabulary split between "section" and "segment", the bootstrapping options, the vision-section removal "bin"), is [STRUCTURAL-CONFIGURABILITY.md](STRUCTURAL-CONFIGURABILITY.md) — merged as the design record, #104.
- **One piece of that design not yet built:** the doc's agreed `deleted_at`-based time-limited bin for removing a vision section (vs. the simpler hard-delete #106 actually shipped) is flagged in the doc itself as a follow-up, not a blocker — the structure is genuinely configurable either way, which is what resolves the trademark concern.

### 5. README, docs, repo identity — done
~~README.md's top-level framework description, the Features table, and CONTRIBUTING.md all still read "the full **Entrepreneurial Operating System® (EOS®)** framework," with every module's registered mark (V/TO®, Level 10 Meeting®, IDS®, The Accountability Chart®) spelled out.~~ **Done, #100 (merged):** both files reworded with generic, vendor-neutral copy and the app's own default terminology words. The GitHub repo description is also updated (manual step, done directly in repo settings — not something this tooling can change). ~~The README also had a rendering bug unrelated to this effort — the "on hold" banner was pasted in as a raw diff block.~~ **Done** — the whole banner (and the broken block with it) was removed directly on `main` on 2026-11-01.

A few more hardcoded literals turned up while reviewing unrelated community PRs (#93/#95) — missed by every earlier sweep because none is a template-variable substitution: `templates/home.html`'s "EOS Dashboard" heading, "Identify, Discuss, Solve", and "Vision/Traction Organizer"; `templates/accounts/org_terminology.html`'s "EOS building blocks"; `templates/todos/todo_form.html`'s "EOS standard: 7 days from today." Also found in the same pass: `templates/accounts/org_export.html` used `{% block title %}` instead of `{% block page_title %}`, which both hardcoded "EOS App" *and* silently broke per-organisation branding on that one page (it never got the org's brand suffix every other page gets). **All done, #102 (merged).**

### 6. Found in a full sweep against EOS Worldwide's current trademark list — new, not previously tracked
A pass through every file in the repo against [the live US trademark list](https://branding.eosworldwide.com/us-trademarks/) (not just the terms the original 2026-10-16 audit anticipated) turned up several items the area-by-area PRs never touched, because they aren't in `apps/` or `templates/` at all:

- ~~**`.braintree/brain.json` and `.claude/agents/*.md`**~~ — **done.** Both removed from the repo.
- ~~**`static/css/eos.css`**~~ — **done, #84 (merged).** Renamed to `app.css`.
- ~~**`LICENSE`**~~ — **done, #84 (merged).** Copyright line now reads "Empresadence Contributors."
- ~~**`apps/accounts/portability/export.py`**~~ — **done, #99 (merged).** The generated `README.txt`'s record-type sentence named "V/TO" directly (landed with #51, after the original audit) and, found in the same sentence while fixing it, also spelled out "Accountability Chart" and "Level 10 Meeting" — both separately registered. All three replaced with the app's own generic words.
- ~~**`templates/accountability/chart.html`, `node_form.html`**~~ — **done, #84 (merged).** The "typically Visionary and Integrator" example text and the form's placeholder attribute both reworded to CEO/COO.
- ~~**`docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example`**~~ — **done, #98 (merged).** Default DB name/user/password renamed from the `eos_` prefix to `epd_`; `config/settings/base.py`'s own fallback defaults and the README's env var table, found while fixing it, were also still on `eos_`.
- ~~**Internal docstrings, code comments, and one admin-visible `help_text`**~~ — **done, #108 (merged).** A final full-repo grep (not just templates and user-facing strings) turned up five more literal "EOS" spots missed by every earlier sweep: `Organization.terminology`'s `help_text`, `OrgTerminologyView`'s docstring, `apps/accounts/portability/export.py`'s module docstring, `Scorecard.count_ok`'s docstring, and a comment in `config/settings/base.py`. All reworded to generic phrasing.

### 7. Issue #134 — a fresh sweep against the live trademark list found more leftovers
Opened by @RCheesley on 2026-11-27, a read of `main` against [the current list](https://branding.eosworldwide.com/us-trademarks/) found terms the #100/#102/#108 sweeps didn't reach, because #106's structural-configurability work made the VTO/meeting structure *overridable* without changing what actually ships as the default. Four reached people using the app; the rest reached only the site administration or the page source.

| Term | Where | Fix |
|---|---|---|
| IDS® | `Issue.STATUS_IN_IDS`'s choice label, "In IDS" | Static label → "In Review"; the badge and CSV export now show the organisation's own `terms.ids` word instead (default "PRS"), via an override of `get_status_display()` |
| Core Focus™, 10-Year Target™, 3-Year Picture™ | `templates/home.html`'s vision card description | Reworded to "Purpose and Niche, Long-Range Target, ..., Mid-Range Picture, ..." |
| Core Focus™, 10-Year Target™, 3-Year Picture™ | `apps/vision/structure.py`'s shipped `DEFAULT_STRUCTURE` group labels | Labels (not the stored `key`s) renamed to "Purpose and Niche" / "Long-Range Target" / "Mid-Range Picture" |
| The Accountability Chart® | `apps/accountability/apps.py`'s `verbose_name` (shown in `/admin/`) | → "Org Chart" |
| V/TO® | `help_text` in `apps/rocks/models.py` and `apps/issues/models.py`; an HTML comment and a `{% comment %}` block in `templates/home.html` and `templates/issues/issue_form.html` (the latter not flagged by #134 itself, found while fixing the rest) | → "the vision document" / "Vision" |
| IDS® | A `{# #}` template comment in `templates/meetings/segments/ids.html` | Comment reworded to drop the acronym |
| (not a mark, stale vocabulary) | `apps/rocks/apps.py`, `apps/todos/apps.py`, `apps/scorecards/apps.py` verbose_names; `team_modules.py`'s tile labels; `team_list.html`'s empty-state copy | All now read from `terms`/generic wording instead of the hardcoded EOS-era English words |

Also added: `apps/accounts/tests/test_trademark_sweep.py`, a standing test that scans every template and the `help_text=`/`verbose_name=`/`label=`/choices-tuple surfaces of `apps/` (outside migrations and tests) for the marks above, plus the bare ®/™ symbols, so a later PR can't reintroduce one unnoticed. "Level 10 Meeting" is deliberately left off its term list until #121 lands — it already has unresolved instances tracked separately, below.

**Status: fixed on `close-out-trademark-remediation`, not yet merged.**

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
5. ~~Turn the V/TO's section list and the meeting's segment timings into admin-configurable structures instead of fixed copies~~ — **done, #104/#106/#107 (all merged).**
6. ~~Sweep README, CONTRIBUTING, repo description and GitHub topics~~ — **done, #100 (merged) plus the repo description, updated directly, plus #102 (merged) for a handful more literals found during unrelated PR review, plus #108 (merged) for the last of the internal docstrings/comments.** GitHub topics are still empty; adding some is purely additive (not a trademark fix), so left for whenever, not tracked here as a blocker.
7. ~~Fix the README's broken diff-block rendering and take the "on hold" banner down~~ — **done**, removed directly on `main` on 2026-11-01.

Items 1 through 7 are fully merged or otherwise done. **One item reopened this closed list: issue #134** (2026-11-27) found leftovers from a fresh sweep against the live trademark list — see item 7 under Status above. Fixed on `close-out-trademark-remediation`; not yet merged. The `deleted_at`-bin follow-up noted under item 4 above remains a product-quality gap against our own design doc, not a trademark-remediation gap. There is still a separate, already-open PR (#121) for the "Level 10 Meeting" instances #134 deliberately left out of scope.

## Open questions

- ~~Who picks the generic default words~~ — **resolved.** The `Terms` defaults themselves landed in #90. The renamed `apps/vto` package's name and the `vto` term's resulting default word were discussed on #91 with @RCheesley and decided there (see above). #91 was a discussion-only PR with no code; close it without merging once #96 is confirmed landed, since its draft text is now stale.
- ~~Does the structural-copy fix want its own design discussion before a PR~~ — **resolved.** [STRUCTURAL-CONFIGURABILITY.md](STRUCTURAL-CONFIGURABILITY.md), incorporating @RCheesley's actual review feedback on #104, not just a first draft.
- Is a trademark/non-affiliation statement wanted in the README now that everything above has landed, or is removal alone sufficient? **Still open — the one real decision left, and it's @drikusb's / the project's to make, not a code change.**
