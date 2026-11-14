# Admin-Configurable Vision Sections & Meeting Segments — Proposal

> Addresses [TRADEMARK-REMEDIATION.md](TRADEMARK-REMEDIATION.md) item 5 — "the two structural copies" — and unblocks item 7, which is gated on it. No code in this PR; this is a design proposal for discussion before any lands, same as #91 was for the app rename.

## Background

The two remaining literal copies of EOS Worldwide's own tooling are not wording — those are already generic — but *structure*:

- **The V/TO's section list and two-page layout.** `SectionKey.CHOICES` in `apps/vision/models.py` is a fixed, hardcoded 14-entry list (Core Focus — Purpose/Niche, 10-Year Target, Target Market, Three Uniques ×3, Proven Process, Guarantee, 3-Year Picture, 3-Year Goals, 1-Year Plan ×3) that exactly mirrors the V/TO®'s own fixed template.
- **The Level 10 Meeting's segment timings.** `SEGMENT_NAMES`/`SEGMENT_DURATIONS`/`SEGMENT_TEMPLATES` in `apps/meetings/models.py` are a fixed 7-item, 90-minute agenda (`[5, 5, 5, 5, 5, 60, 5]`) that exactly mirrors the Level 10 Meeting®'s own fixed agenda.

Per the project's own direction (credit @RCheesley, issue #17): a weekly meeting, a scorecard, quarterly priorities, a vision document and a roles chart are shared by EOS, Scaling Up, 4DX, and others — the generic *concept* belongs to no one. What's specifically EOS's is the *exact* fixed shape of these two. Making both genuinely configurable, with a generic shape shipped as the default, resolves this the same way the terminology work resolved the wording.

The two have very different technical constraints, so this proposes different depths of configurability for each — grounded in what's actually feasible in the current codebase, not what would be ideal in the abstract.

## The V/TO's section structure

**Correction (2026-11-13):** the first draft of this proposal claimed this was "close to a pure data problem — there's no per-section view logic; the only thing hardcoded is the list itself." That was wrong, and checking the templates before writing any code is what caught it. The *model and form* layer is indeed generic (a `VTOSection` row with a `key` and free-text `content`, edited by one generic `VTOSectionForm`). But **the two templates are entirely bespoke per section.** `vision_detail.html` (312 lines) and `vision_print.html` (249 lines) hardcode all 14 sections individually, and in particular they hardcode two things the first draft missed:

- **Sections are grouped into named cards**, not rendered as a flat list: "Core Focus" (purpose + niche), "10-Year Target", "Marketing Strategy" (target market, three uniques ×3, proven process, guarantee), "3-Year Picture", "1-Year Plan" (revenue + profit side by side, then goals) — spread across the two pages, with the page break driven by a `.page-traction` CSS class.
- **Three different render styles** are baked into the markup, not the model: plain paragraph, single line (prominent, for the targets), and bulleted-list-via-`splitlines` (for the two "Goals" sections, which split their free text into `<li>` items).

That grouping and page split *is* part of what the V/TO® template prescribes, so it has to become configurable too — it isn't incidental presentation. Which means the data model needs a **group** level and a **render style** per section, and both templates need rewriting to loop generically.

**Revised proposal:** three small org-scoped models mirroring exactly what's on screen — a page has ordered groups, a group has ordered sections:

```python
class VisionPage(models.Model):          # "Vision", "Delivery"
    organization, label, order

class VisionSectionGroup(models.Model):  # "Core Focus", "Marketing Strategy", ...
    page (FK), label, order

class VisionSectionDefinition(models.Model):
    group (FK), key, label, order
    render_as = ('text' | 'single_line' | 'list')
```

- Today's hardcoded layout becomes a code-level `DEFAULT_STRUCTURE` constant, and a `structure_for(org)` helper returns the org's own rows when it has any, or that default otherwise — **the same default-with-override pattern `Terms`/`DEFAULTS` already uses for wording.** No data migration, and no rows created for organisations that never customize. Both templates loop over whatever `structure_for()` returns, so they render identically either way.
- `VTOSection.key` drops its `choices=SectionKey.CHOICES` constraint (an `AlterField` migration, no data change) so a custom section's key validates against the org's own structure instead. Existing content is untouched — the keys themselves don't move.
- `SectionKey` survives as the default structure's key vocabulary and for the legacy `three_uniques` key that migration `0002` still depends on.

**Scoped out of v1:** the bespoke org-facing editing UI. Registering these three models in the Django admin makes the structure editable immediately and for free, which is what actually resolves the trademark concern (the shape is no longer a code-level copy). A friendlier "Customize sections" screen alongside Organisation → Terminology is worth doing, but as a follow-up — it's UX polish on top of a resolved problem, and bundling it would make this PR much harder to review.

## The Level 10 Meeting's segment timings

This one is genuinely more constrained, and the proposal is scoped to that reality rather than overselling it. Each of the 7 segments isn't just a name and a duration — `SEGMENT_TEMPLATES` ties each to its own bespoke view logic (`rocks.html` renders the live Priorities-review queue pulled from the Rocks app, `ids.html` renders the issue-solving queue, etc.). An organisation can't "add a new segment" the way it can a V/TO section, because a new segment needs *something real* to show, and that only exists for the 7 built-in types today.

**Proposal:**

- A new org-scoped model:

  ```python
  class MeetingSegmentDefinition(models.Model):
      organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                         related_name='segment_definitions')
      order = models.PositiveSmallIntegerField()
      segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
      label = models.CharField(max_length=100, blank=True)  # blank = derive from terms, as today
      duration_minutes = models.PositiveSmallIntegerField()
      enabled = models.BooleanField(default=True)
  ```

  `SEGMENT_TYPE_CHOICES` covers the 7 existing built-ins (`check_in`, `metrics_review`, `priority_review`, `updates`, `action_review`, `ids`, `conclude`) plus one new type, `custom_notes`.
- **Durations become fully configurable**, same default-with-override pattern as above — trivial, since it's just numbers.
- **Each built-in segment can be reordered or disabled.** An organisation that doesn't want a Headlines-style check-in just turns it off; the runner skips it.
- **`custom_notes` is a genuinely new, generic segment type**: a plain free-text block with its own label and duration, reusing the existing `MeetingNote` mechanism (which already stores arbitrary per-segment notes) rather than inventing new storage. This is the one place an organisation gets to add something *beyond* the 7 built-ins — without the "live queue" richness those have, since that richness is inherently tied to real application data (Priorities, Issues, etc.) that a made-up segment type has no way to pull from.
**Correction (2026-11-13): positional segment indices are a data-integrity hazard here, and the first draft missed it.** That draft said "`Meeting.current_segment` stays a plain integer index; it just indexes into `segments_for(org)` instead of the global list." That is not safe. Both `Meeting.current_segment` *and* `MeetingNote.segment` are stored as bare `PositiveSmallIntegerField` positions into the global `SEGMENT_NAMES` list. The moment that list becomes per-organisation and *mutable*, every historical meeting's notes silently re-point to the wrong segment as soon as someone reorders or removes one — a completed meeting's PRS notes would start displaying under "Check-in", with no error and no way to tell from the data that it happened.

So this piece additionally needs one of:

- **an agenda snapshot per meeting** — copy the effective segment list onto the `Meeting` row when it is created, so a meeting always renders against the agenda it was actually run with (also the historically honest answer: the agenda *did* change afterwards); or
- **an FK from `MeetingNote` to the segment definition** instead of a position, with definitions soft-deleted rather than removed.

The snapshot is the better fit — it keeps completed meetings immutable and avoids soft-delete bookkeeping on definitions — but either way this is a migration with real data implications, which is why this piece is sequenced **after** the vision sections work rather than bundled with it.

## Explicitly out of scope for v1

- No drag-and-drop UI, and for vision sections no bespoke org-facing editor at all in v1 — Django admin registration is enough to make the structure genuinely configurable, which is what resolves the trademark concern. A friendlier editing screen is a follow-up.
- No way for an organisation to invent an entirely new segment *type* with its own bespoke logic — only the free-text `custom_notes` escape hatch above.

## Decisions

**Correction (2026-11-14):** an earlier revision of this section said @RCheesley had gone quiet and settled these unilaterally. That was wrong — she'd already left five inline review comments answering exactly these four questions, on 2026-11-13; the check for "is she still active" only looked at issues she'd *created*, missed PR review comments entirely, and ran after her comments landed but before anyone had read them. Below are her actual answers, with two refinements her comments raised that the first pass hadn't addressed.

1. **Custom segments stay free-text-only — confirmed by @RCheesley.** "I think having the custom notes segment in meetings makes sense here... Custom segment would be sufficient for the time being, but I can see the power of being able to bring in specific feeds." Pulling a configurable live data stream into a custom segment is real, but it's its own feature — tracked as a roadmap item, not part of this change.
2. **Removing a vision section goes into a time-limited bin, not an immediate archive, and the bin is scoped to the section, not the whole document.** Her comment: "Assuming that users do stupid things, I would suggest having a 'bin' that it is sent to for xx days after which it deletes" — and she asked whether that should allow a full-document rollback or just the one section.
   - **Scope: just the section.** A whole-document rollback needs a snapshot of the *entire* structure (every page, group and section) at every edit, not just the one being removed — a materially bigger feature (closer to what `VTOSectionHistory` already does for content edits, but for structure). Worth a future proposal of its own if it turns out to be wanted; not needed to resolve the trademark concern.
   - **Mechanism:** `VisionSectionDefinition` gets a nullable `deleted_at`. Removing a section sets it rather than deleting the row, and `structure_for(org)` filters it out of the active structure. An admin "Recently removed" list (filtered on `deleted_at` set) lets it be restored — clearing the field — within the window. A scheduled command purges anything past the window (default 30 days, configurable), at which point the orphaned `VTOSection` content is deleted too — mirroring `VTOSectionHistory.save_content()`'s own "keep the last 5, trim the rest" precedent, just on a time window instead of a count.
3. **No new vocabulary needed — and @RCheesley's distinction is the one to keep.** Her comment: "I think it's fine to call them what they are because it's not model-specific. All meetings have sections, and segments... refers to the bits you're bringing in from the application." So: **"section"** for an editable block (used by both the vision document and, potentially, a meeting's own notes), **"segment"** specifically for one of the meeting's seven timed agenda slots, several of which pull in live data from other apps. Neither word is on EOS Worldwide's mark list, and neither needs a `Terms` entry.
4. **Bootstrapping offers both clone-then-edit and start-from-scratch, not clone-then-edit only.** Her comment: "I think clone then edit makes more sense for a user, but power users might want to start from scratch. Are both possible?" Yes — clone-then-edit stays the primary, default action (nobody should have to rebuild a working vision document from nothing just to rename one card), with a secondary "Start from scratch" action next to it for the organisation that wants a blank structure.
