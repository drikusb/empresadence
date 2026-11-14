"""The meeting's agenda: which segments, in what order, for how long.

The shipped default below is the agenda every organisation starts with. An
organisation that wants a different one stores its own
``MeetingSegmentDefinition`` rows, and :func:`segments_for` returns the
effective, ordered, enabled-only list instead — the same default-with-
override pattern ``apps.accounts.terminology`` and ``apps.vision.structure``
use.

A running meeting's own agenda is frozen onto it at creation time (see
``Meeting.agenda``), never read live from here again. ``MeetingNote.segment``
and ``Meeting.current_segment`` are positions into that specific list, so
reordering or disabling an organisation's segments after a meeting exists
must never change what that meeting's own notes point at — only new
meetings pick up a changed agenda.
"""
CHECK_IN = 'check_in'
METRICS_REVIEW = 'metrics_review'
PRIORITY_REVIEW = 'priority_review'
UPDATES = 'updates'
ACTION_REVIEW = 'action_review'
IDS = 'ids'
CONCLUDE = 'conclude'
CUSTOM_NOTES = 'custom_notes'

#: What an organisation may configure as one of its own rows. CONCLUDE is
#: deliberately not offered here — see segments_for() and the comment on
#: CONCLUDE_SEGMENT below. Six built-ins each pull live data from another
#: app via their own template; CUSTOM_NOTES is the one generic, free-text
#: escape hatch — see STRUCTURAL-CONFIGURABILITY.md's decision on why it
#: stops there.
SEGMENT_TYPE_CHOICES = [
    (CHECK_IN, 'Check-in'),
    (METRICS_REVIEW, 'Metrics Board Review'),
    (PRIORITY_REVIEW, 'Priority Review'),
    (UPDATES, 'Updates'),
    (ACTION_REVIEW, 'Action Review'),
    (IDS, 'PRS'),
    (CUSTOM_NOTES, 'Custom (free text)'),
]

_TEMPLATES = {
    CHECK_IN: 'segue.html',
    METRICS_REVIEW: 'scorecard.html',
    PRIORITY_REVIEW: 'rocks.html',
    UPDATES: 'headlines.html',
    ACTION_REVIEW: 'todos.html',
    IDS: 'ids.html',
    CONCLUDE: 'conclude.html',
    CUSTOM_NOTES: 'custom.html',
}

# The fixed 90-minute agenda every organisation shipped with before this
# became configurable — now the default rather than the only option.
# CONCLUDE is not part of this list; see CONCLUDE_SEGMENT.
DEFAULT_SEGMENTS = [
    {'segment_type': CHECK_IN, 'duration_minutes': 5, 'label': ''},
    {'segment_type': METRICS_REVIEW, 'duration_minutes': 5, 'label': ''},
    {'segment_type': PRIORITY_REVIEW, 'duration_minutes': 5, 'label': ''},
    {'segment_type': UPDATES, 'duration_minutes': 5, 'label': ''},
    {'segment_type': ACTION_REVIEW, 'duration_minutes': 5, 'label': ''},
    {'segment_type': IDS, 'duration_minutes': 60, 'label': ''},
]

# Where a meeting is rated and completed (see templates/meetings/segments/
# conclude.html) — always the agenda's final segment, for every organisation,
# so there is always exactly one way to finish a meeting. Not something an
# organisation's own rows can disable, reorder or duplicate; segments_for()
# appends it after whatever the organisation has configured, and
# MeetingSegmentDefinition.clean() refuses CONCLUDE as a row's segment_type.
CONCLUDE_SEGMENT = {'segment_type': CONCLUDE, 'duration_minutes': 5, 'label': ''}


def _default_name(segment_type, terms):
    return {
        CHECK_IN: terms.segue,
        METRICS_REVIEW: f'{terms.scorecard} Review',
        PRIORITY_REVIEW: f'{terms.rock} Review',
        UPDATES: terms.headlines,
        ACTION_REVIEW: f'{terms.todo} Review',
        IDS: terms.ids,
        CONCLUDE: 'Conclude',
    }.get(segment_type, segment_type)


def segments_for(organization):
    """The organisation's own agenda (ordered, enabled only), or the shipped default.

    Always ends with :data:`CONCLUDE_SEGMENT`. This is what a new
    :class:`~apps.meetings.models.Meeting` snapshots onto itself at creation
    time — see ``Meeting.agenda`` — not something a meeting already in
    progress ever re-reads.

    An organisation that has customised at all — even down to disabling
    every one of its own rows — gets exactly what that leaves, not a silent
    fall back to the shipped default; the default only applies to an
    organisation that has never created a row in the first place.
    """
    from .models import MeetingSegmentDefinition

    if organization is None:
        return [dict(segment) for segment in DEFAULT_SEGMENTS] + [dict(CONCLUDE_SEGMENT)]

    all_rows = MeetingSegmentDefinition.objects.filter(organization=organization)
    if not all_rows.exists():
        return [dict(segment) for segment in DEFAULT_SEGMENTS] + [dict(CONCLUDE_SEGMENT)]

    enabled_rows = all_rows.filter(enabled=True).order_by('order', 'pk')
    body = [
        {'segment_type': row.segment_type, 'duration_minutes': row.duration_minutes, 'label': row.label}
        for row in enabled_rows
    ]
    return body + [dict(CONCLUDE_SEGMENT)]


def resolve_agenda(agenda, terms):
    """One meeting's frozen ``agenda`` resolved to display names and templates.

    Returns ``[{'segment_type', 'name', 'duration_minutes', 'template'}, ...]``
    in the agenda's own order. ``terms`` names a built-in segment from the
    organisation's current vocabulary; an explicit ``label`` — always set on
    a custom segment, optionally set to override a built-in's name — wins
    over that.
    """
    return [
        {
            'segment_type': entry['segment_type'],
            'name': entry.get('label') or _default_name(entry['segment_type'], terms),
            'duration_minutes': entry['duration_minutes'],
            'template': _TEMPLATES.get(entry['segment_type'], 'custom.html'),
        }
        for entry in agenda
    ]
