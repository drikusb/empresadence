from datetime import date

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Team

CHECKIN_OVERDUE_DAYS = 7


class RockQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Rocks ``user`` may see: every Rock that is not private, and the private
        ones they own, created or have been added to.

        Organisation admins are not included: a private Rock is for the people on
        it, and the Django admin stays the audit path. Use this on every surface a
        Rock appears, so a private Rock never shows up, or gets counted, anywhere
        else.
        """
        return self.filter(Rock.visible_q(user))


class Rock(models.Model):
    STATUS_ON_TRACK = 'on_track'
    STATUS_OFF_TRACK = 'off_track'
    STATUS_COMPLETE = 'complete'
    STATUS_DROPPED = 'dropped'
    STATUS_CHOICES = [
        (STATUS_ON_TRACK, 'On Track'),
        (STATUS_OFF_TRACK, 'Off Track'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_DROPPED, 'Dropped'),
    ]

    QUARTER_CHOICES = [(1, 'Q1'), (2, 'Q2'), (3, 'Q3'), (4, 'Q4')]

    # Quarter end dates: last day of the final month in each quarter
    QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

    title = models.CharField(max_length=255)
    description = models.TextField(
        blank=True,
        help_text='What does "done" look like? Make it specific and measurable.',
    )
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='owned_rocks'
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='rocks'
    )
    is_company_rock = models.BooleanField(
        default=False,
        help_text='Company-wide Rocks appear on the vision document. Other Rocks stay on their team\'s own list.',
    )
    is_private = models.BooleanField(
        default=False,
        help_text='Private Rocks are seen only by their owner, their creator and the people they are shared with.',
    )
    shared_with = models.ManyToManyField(
        User, blank=True, related_name='shared_rocks',
        help_text='Who else may see this Rock while it is private.',
    )
    quarter = models.PositiveSmallIntegerField(choices=QUARTER_CHOICES)
    year = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ON_TRACK
    )
    parent_rock = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_rocks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rocks',
    )

    objects = RockQuerySet.as_manager()

    class Meta:
        ordering = ['team__name', 'owner__first_name', 'owner__username', 'title']
        verbose_name = 'Rock'
        verbose_name_plural = 'Rocks'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('rocks:detail', kwargs={'pk': self.pk})

    # --- Visibility ---

    @staticmethod
    def visible_q(user, prefix=''):
        """The filter behind ``visible_to``; ``prefix`` reaches a Rock through a
        relation, e.g. ``'rock__'`` from a milestone."""
        public = models.Q(**{f'{prefix}is_private': False})
        if not getattr(user, 'is_authenticated', False):
            return public
        shared = Rock.shared_with.through.objects.filter(user=user).values('rock_id')
        return (
            public
            | models.Q(**{f'{prefix}owner': user})
            | models.Q(**{f'{prefix}created_by': user})
            | models.Q(**{f'{prefix}pk__in': shared})
        )

    def is_visible_to(self, user):
        if not self.is_private:
            return True
        if not getattr(user, 'is_authenticated', False):
            return False
        return (
            user.pk in (self.owner_id, self.created_by_id)
            or self.shared_with.filter(pk=user.pk).exists()
        )

    # --- Status helpers ---

    def is_on_track(self):
        return self.status == self.STATUS_ON_TRACK

    def is_off_track(self):
        return self.status == self.STATUS_OFF_TRACK

    def is_complete(self):
        return self.status == self.STATUS_COMPLETE

    def is_dropped(self):
        return self.status == self.STATUS_DROPPED

    def is_active(self):
        return self.status in (self.STATUS_ON_TRACK, self.STATUS_OFF_TRACK)

    def toggle_track_status(self):
        """Flip between on_track and off_track. No-op if complete/dropped."""
        if self.status == self.STATUS_ON_TRACK:
            self.status = self.STATUS_OFF_TRACK
        elif self.status == self.STATUS_OFF_TRACK:
            self.status = self.STATUS_ON_TRACK
        self.save(update_fields=['status', 'updated_at'])

    # --- Quarter helpers ---

    @property
    def quarter_label(self):
        return f'Q{self.quarter} {self.year}'

    @property
    def status_badge_class(self):
        return {
            self.STATUS_ON_TRACK: 'success',
            self.STATUS_OFF_TRACK: 'danger',
            self.STATUS_COMPLETE: 'secondary',
            self.STATUS_DROPPED: 'light text-dark border',
        }.get(self.status, 'secondary')

    # --- Milestone helpers ---

    @property
    def milestone_count(self):
        return self.milestones.count()

    @property
    def milestones_complete(self):
        return self.milestones.filter(is_complete=True).count()

    @property
    def milestone_progress_pct(self):
        total = self.milestone_count
        return round(self.milestones_complete / total * 100) if total else 0

    # --- Check-in helpers ---

    @property
    def latest_checkin(self):
        return self.checkins.first()

    @property
    def is_checkin_overdue(self):
        """True if this Rock is active and hasn't had a check-in in CHECKIN_OVERDUE_DAYS."""
        if not self.is_active():
            return False
        latest = self.latest_checkin
        reference = latest.created_at if latest else self.created_at
        return (timezone.now() - reference).days >= CHECKIN_OVERDUE_DAYS

    @staticmethod
    def current_quarter():
        return (date.today().month - 1) // 3 + 1

    @staticmethod
    def current_year():
        return date.today().year

    @staticmethod
    def quarter_end_date(quarter, year):
        month, day = Rock.QUARTER_END[quarter]
        return date(year, month, day)

    @staticmethod
    def prev_quarter(quarter, year):
        if quarter == 1:
            return 4, year - 1
        return quarter - 1, year

    @staticmethod
    def next_quarter(quarter, year):
        if quarter == 4:
            return 1, year + 1
        return quarter + 1, year


class RockMilestone(models.Model):
    rock = models.ForeignKey(Rock, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Rock Milestone'
        verbose_name_plural = 'Rock Milestones'

    def __str__(self):
        return self.title

    def mark_complete(self):
        from django.utils import timezone
        self.is_complete = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_complete', 'completed_at'])

    def mark_open(self):
        self.is_complete = False
        self.completed_at = None
        self.save(update_fields=['is_complete', 'completed_at'])


class RockCheckin(models.Model):
    """A weekly progress update: a confidence read (on/off track) plus a note."""

    rock = models.ForeignKey(Rock, on_delete=models.CASCADE, related_name='checkins')
    confidence = models.CharField(
        max_length=20,
        choices=[
            (Rock.STATUS_ON_TRACK, 'On Track'),
            (Rock.STATUS_OFF_TRACK, 'Off Track'),
        ],
        default=Rock.STATUS_ON_TRACK,
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='rock_checkins'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Rock Check-in'
        verbose_name_plural = 'Rock Check-ins'

    def __str__(self):
        return f'{self.rock.title} — {self.get_confidence_display()} ({self.created_at:%Y-%m-%d})'

    @property
    def is_on_track(self):
        return self.confidence == Rock.STATUS_ON_TRACK


class RockDependency(models.Model):
    rock = models.ForeignKey(Rock, on_delete=models.CASCADE, related_name='dependencies')
    depends_on_rock = models.ForeignKey(
        Rock, on_delete=models.CASCADE, related_name='dependents'
    )
    description = models.TextField(blank=True, help_text='Why does this Rock depend on the other?')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['rock', 'depends_on_rock']]
        verbose_name = 'Rock Dependency'
        verbose_name_plural = 'Rock Dependencies'

    def __str__(self):
        return f'{self.rock.title} → {self.depends_on_rock.title}'
