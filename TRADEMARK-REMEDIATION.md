# Trademark Remediation — Tracking

> Part of the response agreed with EOS Worldwide on their [#17](https://github.com/drikusb/empresadence/issues/17) request.

## Background

EOS Worldwide asked us to either remove their trademarks, terminology, and the two tool copies they identified, or archive the repository. We've chosen to remove and generalize rather than archive. Their full findings and the agreed direction are in [#17](https://github.com/drikusb/empresadence/issues/17) — this document turns that discussion into a concrete, reviewable scope, and tracks what's actually landed against it. Checked against EOS Worldwide's own current list at [branding.eosworldwide.com/us-trademarks](https://branding.eosworldwide.com/us-trademarks/) each time this document is updated.

## Proposed direction (credit: @RCheesley, issue #17)

Rather than swap EOS's names for different-but-equivalent names, make the project genuinely vendor-agnostic: a weekly meeting with a scorecard, quarterly priorities, to-dos, issue-solving, a vision document and a roles chart are shared by EOS, Scaling Up, 4DX, and others — none of that structure belongs to anyone. We ship generic names and a generic default agenda; each organisation can relabel things in their own instance if they want their own vocabulary. That's user content at that point, not something we ship, and it also opens the project to teams who aren't running EOS at all.

## Status

### 1. Project identity — in progress
- The project name itself: **done**. Repo renamed from OpenEOS to **Empresadence** ("EPD" for short — see #58's discussion). Remaining literal "OpenEOS"/"openeos" strings in code and docs swept in #83.
- "EOS App" — still the sender name on every outgoing email (`DEFAULT_FROM_EMAIL` in `.env.example`) and the copyright holder in `LICENSE` ("EOS App Contributors").
- The "Open-source EOS framework" wording — still on the README and CONTRIBUTING.
- No statement of trademark ownership or non-affiliation yet.

### 2 & 3. Hardcoded trademarked and generic terms — infrastructure done, defaults not flipped
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

**The important catch, unchanged since last update: the shipped *defaults* in `Terms` are still EOS Worldwide's literal words** (Rock, Scorecard, Level 10 Meeting, VTO, IDS, Accountability Chart, Segue, Headlines, Cascading Messages, Seat, Core Value, Milestone). An organisation that never visits its Terminology settings sees the EOS vocabulary exactly as before — which is every organisation on a fresh install. **Flipping those defaults to generic words is the one step that actually satisfies EOS Worldwide's request, and it hasn't happened yet.**

The "EOS recommends ..." lines were swept for their noun but still say "EOS recommends" literally.

Two further hardcoded-term spots found in a full sweep against EOS Worldwide's current list, not caught by the original per-area PRs because they're not plain UI copy:
- `apps/accounts/terminology.py` — the `vto` term's own `description` field is the literal phrase `'Vision/Traction Organizer'`, which renders as UI hint text wherever that description is shown.
- `templates/vto/vto_detail.html` and `vto_print.html` — the VTO's second printed page is headed literally **"Page 2 — Traction"**. `Traction®` is its own standalone registered mark (the book), separate from `V/TO®` — this wasn't on the radar because the audit tracked "VTO" as one area, not realizing one of its own pages carries a second, different mark.

### 4. The two structural copies — not started
- The V/TO's fixed section structure and two-page print layout: still fixed. `VTOSection`'s `SectionKey` choices are unchanged.
- The Level 10 Meeting agenda's exact segment timings (`[5, 5, 5, 5, 5, 60, 5]`): still fixed. `SEGMENT_NAMES`/`SEGMENT_DURATIONS` in `apps/meetings/models.py` are unchanged; only the *display* name per segment is configurable now, not the segment list or durations.

### 5. README, docs, repo identity — not started
README.md's top-level framework description, the Features table, and CONTRIBUTING.md all still read "the full **Entrepreneurial Operating System® (EOS®)** framework," with every module's registered mark (V/TO®, Level 10 Meeting®, IDS®, The Accountability Chart®) spelled out. The README also currently has a rendering bug unrelated to this effort — the "on hold" banner was pasted in as a raw diff block and needs fixing regardless.

### 6. Found in a full sweep against EOS Worldwide's current trademark list — new, not previously tracked
A pass through every file in the repo against [the live US trademark list](https://branding.eosworldwide.com/us-trademarks/) (not just the terms the original 2026-10-16 audit anticipated) turned up several items the area-by-area PRs never touched, because they aren't in `apps/` or `templates/` at all:

- **`.braintree/brain.json` and `.claude/agents/*.md`** — AI development-tooling metadata, tracked in the repo by accident. One names "EOS One" and "Traction Tools" (both registered marks, owned by direct competitors) and states "we are an EOS implementation, not an EOS-inspired tool." Never read by the running app (already excluded from the Docker build via `.dockerignore`), but public on GitHub. **Being removed from tracking in a separate PR.**
- **`static/css/eos.css`** — the stylesheet's own filename, loaded in `base.html` and `base_minimal.html`.
- **`LICENSE`** — copyright line reads "EOS App Contributors."
- **`apps/accounts/portability/export.py`** — the generated `README.txt` inside every export archive names "V/TO" directly (this landed with #51, after the original audit).
- **`templates/accountability/chart.html`, `node_form.html`** — use "Visionary" and "Integrator" as the example seat-name placeholders; both are separately trademarked (`Integrator™`, `Visionary and Integrator™`), and the Accountability Chart's own trademark risk was only ever tracked for its own name, not its example content.
- **`docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example`** — default DB name/user/password all use an `eos_` prefix; lower risk (internal infra identifiers, not public-facing), but trivial to rename alongside everything else.

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

1. Pick generic default words for every `Terms` entry and flip `DEFAULTS` in `apps/accounts/terminology.py` — this is the step that makes a fresh install trademark-clean, and nothing else matters as much until it's done. Also flip the `vto` term's `description` field away from "Vision/Traction Organizer."
2. Reword the "EOS recommends" lines, and the "Page 2 — Traction" VTO print/detail heading.
3. Replace "Visionary" / "Integrator" in the Accountability Chart's example placeholder text with vendor-neutral examples.
4. Rename `apps/vto` (the Django app itself) and clear the remaining "EOS App" occurrences (email sender name, LICENSE copyright line) and the `eos_`-prefixed infra defaults.
5. Turn the V/TO's section list and the meeting's segment timings into admin-configurable structures instead of fixed copies.
6. Sweep README, CONTRIBUTING, repo description and GitHub topics.
7. Fix the README's broken diff-block rendering and take the "on hold" banner down once 1–6 land.

## Open questions

- Who picks the generic default words — a short naming pass here, or does each area's original PR author propose theirs?
- Does the structural-copy fix (step 5 above) want its own design discussion before a PR, given it's the one area that's still genuinely unscoped?
- Is a trademark/non-affiliation statement wanted in the README once the above lands, or is removal alone sufficient?
