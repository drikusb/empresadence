from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Organization, Team
from apps.accounts.terminology import Terms

from .segments import CONCLUDE, CUSTOM_NOTES, SEGMENT_TYPE_CHOICES, resolve_agenda


class MeetingSegmentDefinition(models.Model):
    """One slot in an organisation's own meeting agenda.

    An organisation with no rows uses :data:`apps.meetings.segments.DEFAULT_SEGMENTS`
    (see :func:`apps.meetings.segments.segments_for`). Changing these rows
    only affects meetings created afterwards — see ``Meeting.agenda``.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='segment_definitions'
    )
    order = models.PositiveSmallIntegerField(default=0)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    label = models.CharField(
        max_length=100, blank=True,
        help_text='Required for a custom segment. Optional for a built-in one — '
                   "leave blank to use the organisation's own word for it.",
    )
    duration_minutes = models.PositiveSmallIntegerField()
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.organization.name} — {self.label or self.get_segment_type_display()}'

    def clean(self):
        # Belt and suspenders: the admin form's `choices` already keeps
        # CONCLUDE off the dropdown, but this also refuses it if a row is
        # ever created another way (the shell, a fixture, a future API).
        if self.segment_type == CONCLUDE:
            raise ValidationError(
                {'segment_type': 'Conclude is always the final segment and cannot be configured.'}
            )
        if self.segment_type == CUSTOM_NOTES and not self.label.strip():
            raise ValidationError({'label': 'A custom segment needs a name.'})


class Meeting(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETE = 'complete'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETE, 'Complete'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='meetings')
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    current_segment = models.PositiveSmallIntegerField(default=0)
    # The organisation's agenda at the moment this meeting was created — see
    # apps.meetings.segments. Frozen here, not read live from the
    # organisation's current MeetingSegmentDefinition rows, so reordering or
    # disabling a segment later can never re-point an existing meeting's
    # current_segment or its notes' segment positions at the wrong thing.
    agenda = models.JSONField(default=list)
    cascading_messages = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_meetings'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_date', '-created_at']

    def __str__(self):
        return f'{self.team.name} — {self.scheduled_date}'

    def save(self, *args, **kwargs):
        if self.pk is None and not self.agenda:
            from .segments import segments_for
            self.agenda = segments_for(self.team.organization)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('meetings:detail', kwargs={'pk': self.pk})

    @property
    def segment_name(self):
        # No per-request terms here, so this resolves against the shipped
        # defaults — matching what the old global SEGMENT_NAMES constant
        # this replaced always returned. Views resolve the organisation's
        # own words via resolve_agenda(terms) instead; this property is kept
        # for callers (and tests) with no request to hand it a Terms from.
        return resolve_agenda(self.agenda, Terms())[self.current_segment]['name']

    @property
    def segment_duration(self):
        return self.agenda[self.current_segment]['duration_minutes']

    @property
    def is_last_segment(self):
        return self.current_segment == len(self.agenda) - 1

    @property
    def is_scheduled(self):
        return self.status == self.STATUS_SCHEDULED

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def is_complete(self):
        return self.status == self.STATUS_COMPLETE

    def start(self):
        self.status = self.STATUS_ACTIVE
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def advance(self):
        if self.current_segment < len(self.agenda) - 1:
            self.current_segment += 1
            self.save(update_fields=['current_segment'])

    def complete(self, cascading_messages=''):
        self.status = self.STATUS_COMPLETE
        self.ended_at = timezone.now()
        self.cascading_messages = cascading_messages
        self.save(update_fields=['status', 'ended_at', 'cascading_messages'])

    @property
    def average_rating(self):
        ratings = list(self.ratings.values_list('score', flat=True))
        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 1)

    @property
    def duration_minutes(self):
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return round(delta.total_seconds() / 60)
        return None


class MeetingNote(models.Model):
    """One editable notes block per segment per meeting."""
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='notes')
    segment = models.PositiveSmallIntegerField()
    text = models.TextField()
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='meeting_notes'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['meeting', 'segment']]
        ordering = ['segment']

    def __str__(self):
        return f'{self.meeting} — {self.segment_name} notes'

    @property
    def segment_name(self):
        # See Meeting.segment_name: no per-request terms to hand this, so it
        # resolves against the shipped defaults.
        return resolve_agenda(self.meeting.agenda, Terms())[self.segment]['name']


class SegueEntry(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='segue_entries')
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='segue_entries')
    personal_best = models.TextField(blank=True)
    business_best = models.TextField(blank=True)

    class Meta:
        unique_together = [['meeting', 'participant']]

    def __str__(self):
        return f'{self.participant} @ {self.meeting}'


class Headline(models.Model):
    TYPE_GOOD = 'good'
    TYPE_BAD = 'bad'
    TYPE_CHOICES = [
        (TYPE_GOOD, 'Good News'),
        (TYPE_BAD, 'Concern / Bad News'),
    ]

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='headlines')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='headlines')
    headline_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_GOOD)
    text = models.CharField(max_length=200)
    escalated_issue = models.ForeignKey(
        'issues.Issue', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='meeting_headlines'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.text


class MeetingRating(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='ratings')
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_ratings')
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    improvement_note = models.TextField(blank=True)

    class Meta:
        unique_together = [['meeting', 'participant']]

    def __str__(self):
        return f'{self.participant} rated {self.meeting}: {self.score}/10'
