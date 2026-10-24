from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Team


SEGMENT_NAMES = [
    'Segue',
    'Scorecard Review',
    'Rock Review',
    'Headlines',
    'To-Do Review',
    'IDS',
    'Conclude',
]

SEGMENT_DURATIONS = [5, 5, 5, 5, 5, 60, 5]  # minutes

SEGMENT_TEMPLATES = [
    'segue.html',
    'scorecard.html',
    'rocks.html',
    'headlines.html',
    'todos.html',
    'ids.html',
    'conclude.html',
]


def segment_names_for(terms):
    """SEGMENT_NAMES in one organisation's own words, for display.

    ``SEGMENT_NAMES`` stays the canonical list (and the default); views pass
    this per-request version to the templates.
    """
    return [
        terms.segue,
        f'{terms.scorecard} Review',
        f'{terms.rock} Review',
        terms.headlines,
        f'{terms.todo} Review',
        terms.ids,
        'Conclude',
    ]


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
    cascading_messages = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_meetings'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_date', '-created_at']

    def __str__(self):
        return f'{self.team.name} — {self.scheduled_date}'

    def get_absolute_url(self):
        return reverse('meetings:detail', kwargs={'pk': self.pk})

    @property
    def segment_name(self):
        return SEGMENT_NAMES[self.current_segment]

    @property
    def segment_duration(self):
        return SEGMENT_DURATIONS[self.current_segment]

    @property
    def is_last_segment(self):
        return self.current_segment == len(SEGMENT_NAMES) - 1

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
        if self.current_segment < len(SEGMENT_NAMES) - 1:
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
        return f'{self.meeting} — {SEGMENT_NAMES[self.segment]} notes'

    @property
    def segment_name(self):
        return SEGMENT_NAMES[self.segment]


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
