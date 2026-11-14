"""The shape of the vision document: pages, the cards on them, and their sections.

The shipped default below is the structure every organisation starts with. An
organisation that wants a different one stores its own ``VisionPage`` /
``VisionSectionGroup`` / ``VisionSectionDefinition`` rows, and
:func:`structure_for` returns those instead — the same default-with-override
pattern ``apps.accounts.terminology`` uses for wording, so no rows exist for
an organisation that never customises anything.

Both templates render whatever :func:`structure_for` returns, so a custom
structure and the default go through exactly the same markup.
"""
from dataclasses import dataclass, replace

RENDER_TEXT = 'text'
RENDER_SINGLE_LINE = 'single_line'
RENDER_LIST = 'list'

RENDER_CHOICES = [
    (RENDER_TEXT, 'Paragraph'),
    (RENDER_SINGLE_LINE, 'Single line'),
    (RENDER_LIST, 'Bulleted list — one item per line'),
]


@dataclass(frozen=True)
class SectionSpec:
    """One editable free-text section, as the templates and forms see it."""

    key: str
    label: str
    render_as: str = RENDER_TEXT
    half_width: bool = False
    #: Filled in by :func:`section_specs_for`; the structure itself leaves it
    #: blank, since the templates already print the group's label above.
    group_label: str = ''

    @property
    def is_list(self):
        return self.render_as == RENDER_LIST

    @property
    def is_single_line(self):
        return self.render_as == RENDER_SINGLE_LINE

    @property
    def edit_label(self):
        """What to call this section on its own edit page.

        A section with no label of its own is the only one in its card, so the
        card's name is what identifies it — the raw key is the last resort.
        """
        return self.label or self.group_label or self.key


@dataclass(frozen=True)
class GroupSpec:
    """One card on a page, grouping related sections."""

    label: str
    sections: tuple
    hint: str = ''


@dataclass(frozen=True)
class PageSpec:
    """One page — a column on screen, a printed page in the print view."""

    label: str
    groups: tuple
    icon: str = ''


# ── The shipped default ──────────────────────────────────────────────────────
#
# Keys are the ones already stored on existing VTOSection rows, so an
# organisation on the default structure keeps every word it has written.

DEFAULT_STRUCTURE = (
    PageSpec(
        label='Vision',
        icon='bi-eye',
        groups=(
            GroupSpec(label='Core Focus', sections=(
                SectionSpec('core_focus_purpose', 'Purpose / Passion / Cause', RENDER_SINGLE_LINE),
                SectionSpec('core_focus_niche', 'Niche', RENDER_SINGLE_LINE),
            )),
            GroupSpec(label='10-Year Target', sections=(
                SectionSpec('ten_year_target', '', RENDER_SINGLE_LINE),
            )),
            GroupSpec(label='Marketing Strategy', sections=(
                SectionSpec('target_market', 'Target Market'),
                SectionSpec('three_uniques_1', 'Unique 1.'),
                SectionSpec('three_uniques_2', 'Unique 2.'),
                SectionSpec('three_uniques_3', 'Unique 3.'),
                SectionSpec('proven_process', 'Proven Process'),
                SectionSpec('guarantee', 'Guarantee'),
            )),
        ),
    ),
    PageSpec(
        label='Delivery',
        icon='bi-lightning',
        groups=(
            GroupSpec(label='3-Year Picture', hint='Vivid description + measurable goals', sections=(
                SectionSpec('three_year_picture', 'Description'),
                SectionSpec('three_year_goals', 'Measurable Goals (one per line)', RENDER_LIST),
            )),
            GroupSpec(label='1-Year Plan', sections=(
                SectionSpec('one_year_revenue', 'Revenue Target', RENDER_SINGLE_LINE, half_width=True),
                SectionSpec('one_year_profit', 'Profit Target', RENDER_SINGLE_LINE, half_width=True),
                SectionSpec('one_year_goals', 'Critical Goals — 3–7 (one per line)', RENDER_LIST),
            )),
        ),
    ),
)


def structure_for(organization):
    """The organisation's own page/group/section structure, or the shipped default.

    An organisation has customised its structure as soon as it has at least
    one ``VisionPage``; until then it gets :data:`DEFAULT_STRUCTURE`.
    """
    from .models import VisionPage

    if organization is None:
        return DEFAULT_STRUCTURE
    pages = (
        VisionPage.objects
        .filter(organization=organization)
        .prefetch_related('groups__sections')
    )
    if not pages:
        return DEFAULT_STRUCTURE
    return tuple(
        PageSpec(
            label=page.label,
            icon=page.icon,
            groups=tuple(
                GroupSpec(
                    label=group.label,
                    hint=group.hint,
                    sections=tuple(
                        SectionSpec(
                            key=section.key,
                            label=section.label,
                            render_as=section.render_as,
                            half_width=section.half_width,
                        )
                        for section in group.sections.all()
                    ),
                )
                for group in page.groups.all()
            ),
        )
        for page in pages
    )


def section_specs_for(organization):
    """``{key: SectionSpec}`` across the organisation's whole structure.

    The section edit view uses this to look up a section's label and input
    style, and to reject a key the organisation's structure does not contain.
    Each spec carries its card's label, which names an otherwise-unlabelled
    section on its own edit page.
    """
    return {
        section.key: replace(section, group_label=group.label)
        for page in structure_for(organization)
        for group in page.groups
        for section in group.sections
    }
