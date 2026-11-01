# Admin-Configurable Vision Sections & Meeting Segments — Proposal

> Addresses [TRADEMARK-REMEDIATION.md](TRADEMARK-REMEDIATION.md) item 5 — "the two structural copies" — and unblocks item 7, which is gated on it. No code in this PR; this is a design proposal for discussion before any lands, same as #91 was for the app rename.

## Background

The two remaining literal copies of EOS Worldwide's own tooling are not wording — those are already generic — but *structure*:

- **The V/TO's section list and two-page layout.** `SectionKey.CHOICES` in `apps/vision/models.py` is a fixed, hardcoded 14-entry list (Core Focus — Purpose/Niche, 10-Year Target, Target Market, Three Uniques ×3, Proven Process, Guarantee, 3-Year Picture, 3-Year Goals, 1-Year Plan ×3) that exactly mirrors the V/TO®'s own fixed template.
- **The Level 10 Meeting's segment timings.** `SEGMENT_NAMES`/`SEGMENT_DURATIONS`/`SEGMENT_TEMPLATES` in `apps/meetings/models.py` are a fixed 7-item, 90-minute agenda (`[5, 5, 5, 5, 5, 60, 5]`) that exactly mirrors the Level 10 Meeting®'s own fixed agenda.

Per the project's own direction (credit @RCheesley, issue #17): a weekly meeting, a scorecard, quarterly priorities, a vision document and a roles chart are shared by EOS, Scaling Up, 4DX, and others — the generic *concept* belongs to no one. What's specifically EOS's is the *exact* fixed shape of these two. Making both genuinely configurable, with a generic shape shipped as the default, resolves this the same way the terminology work resolved the wording.

The two have very different technical constraints, so this proposes different depths of configurability for each — grounded in what's actually feasible in the current codebase, not what would be ideal in the abstract.

## The V/TO's section structure

This one is close to a pure data problem. Every section already goes through identical, generic machinery: a `VTOSection` row with a `key` and free-text `content`, edited by one generic form (`VTOSectionForm`), with only a single-line/multi-line distinction (`SectionKey.SINGLE_LINE`) differentiating how any section renders. There's no per-section view logic. The only thing hardcoded is the *list itself*.

**Proposal:**

- A new org-scoped model, replacing `SectionKey` as the source of truth for an organisation's own structure:

  ```python
  class VisionSectionDefinition(models.Model):
      organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                         related_name='vision_section_definitions')
      key = models.SlugField(max_length=40)
      label = models.CharField(max_length=100)
      order = models.PositiveSmallIntegerField()
      single_line = models.BooleanField(default=False)

      class Meta:
          ordering = ['order']
          unique_together = [['organization', 'key']]
  ```

- `SectionKey.CHOICES` stops being the *only* structure and becomes the *shipped default* — exactly the same pattern `Terms`/`DEFAULTS` already uses for wording. A helper, `sections_for(org)`, returns the org's own `VisionSectionDefinition` rows if it has any, or the default list otherwise. Every existing organisation keeps today's structure with zero migration, because they simply have no custom rows yet.
- An org that wants to customize gets a "Customize sections" action (next to Organisation → Terminology) that clones the *current effective* list into editable rows for that org, then they rename, reorder, add, or remove sections from there — never starting from a blank slate.
- `VTOSection.key` stops being constrained to `SectionKey.CHOICES` and instead validates against the org's own `sections_for(org)` — existing content keeps working unchanged since the keys themselves don't move.

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
- `Meeting.current_segment` stays a plain integer index; it just indexes into `segments_for(org)` (DB-driven) instead of the global `SEGMENT_NAMES` list.

## Explicitly out of scope for v1

- No drag-and-drop UI — a simple ordered list with up/down controls, consistent with the rest of the admin UI's style.
- No way for an organisation to invent an entirely new segment *type* with its own bespoke logic — only the free-text `custom_notes` escape hatch above.
- No change to the underlying print layout mechanics beyond what naturally follows from the section list no longer being fixed-length.

## Open questions for @RCheesley

1. Is "custom segment = free text only" an acceptable scope for the meeting side, or is there a shape of "richer custom segment" worth designing for instead?
2. For V/TO sections: when an organisation removes a section that already has content, should that be a hard delete or an archive (recoverable, in case of a change of mind)?
3. Does this need its own generic-wording decision — e.g., what a "segment" or "section" is called generically — or is this purely structural, with no new vocabulary involved?
4. Any objection to the "clone-then-edit" bootstrap UX for customizing either structure, versus starting from an empty list?
