from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Organization


# ── Section key constants ────────────────────────────────────────────────────

class SectionKey:
    CORE_FOCUS_PURPOSE = 'core_focus_purpose'
    CORE_FOCUS_NICHE   = 'core_focus_niche'
    TEN_YEAR_TARGET    = 'ten_year_target'
    TARGET_MARKET      = 'target_market'
    THREE_UNIQUES_1    = 'three_uniques_1'
    THREE_UNIQUES_2    = 'three_uniques_2'
    THREE_UNIQUES_3    = 'three_uniques_3'
    PROVEN_PROCESS     = 'proven_process'
    GUARANTEE          = 'guarantee'
    THREE_YEAR_PICTURE = 'three_year_picture'
    THREE_YEAR_GOALS   = 'three_year_goals'
    ONE_YEAR_REVENUE   = 'one_year_revenue'
    ONE_YEAR_PROFIT    = 'one_year_profit'
    ONE_YEAR_GOALS     = 'one_year_goals'

    CHOICES = [
        (CORE_FOCUS_PURPOSE, 'Core Focus — Purpose/Passion/Cause'),
        (CORE_FOCUS_NICHE,   'Core Focus — Niche'),
        (TEN_YEAR_TARGET,    '10-Year Target'),
        (TARGET_MARKET,      'Marketing — Target Market'),
        (THREE_UNIQUES_1,    'Marketing — Three Uniques — 1'),
        (THREE_UNIQUES_2,    'Marketing — Three Uniques — 2'),
        (THREE_UNIQUES_3,    'Marketing — Three Uniques — 3'),
        (PROVEN_PROCESS,     'Marketing — Proven Process'),
        (GUARANTEE,          'Marketing — Guarantee'),
        (THREE_YEAR_PICTURE, '3-Year Picture'),
        (THREE_YEAR_GOALS,   '3-Year Goals'),
        (ONE_YEAR_REVENUE,   '1-Year Plan — Revenue Target'),
        (ONE_YEAR_PROFIT,    '1-Year Plan — Profit Target'),
        (ONE_YEAR_GOALS,     '1-Year Plan — Critical Goals'),
    ]

    # Legacy key kept so existing DB rows and the data migration remain valid.
    THREE_UNIQUES = 'three_uniques'

    ALL = [k for k, _ in CHOICES] + [THREE_UNIQUES]

    LABELS = dict(CHOICES)
    LABELS[THREE_UNIQUES] = 'Marketing — Three Uniques (legacy)'

    # Which sections render as single-line vs. multi-line
    SINGLE_LINE = {ONE_YEAR_REVENUE, ONE_YEAR_PROFIT, TEN_YEAR_TARGET,
                   CORE_FOCUS_PURPOSE, CORE_FOCUS_NICHE}


class VTO(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='vto'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Vision — {self.organization.name}'

    def get_absolute_url(self):
        return reverse('vision:detail')

    def get_section(self, key):
        """Return the VTOSection for this key, or None."""
        return self.sections.filter(key=key).first()

    def get_content(self, key, default=''):
        s = self.get_section(key)
        return s.content if s else default

    @classmethod
    def for_org(cls, organization):
        """Get or create the VTO for an organization."""
        vto, _ = cls.objects.get_or_create(organization=organization)
        return vto


class VTOCoreValue(models.Model):
    vto = models.ForeignKey(VTO, on_delete=models.CASCADE, related_name='core_values')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class VTOSection(models.Model):
    vto = models.ForeignKey(VTO, on_delete=models.CASCADE, related_name='sections')
    key = models.CharField(max_length=40, choices=SectionKey.CHOICES)
    content = models.TextField(blank=True)
    last_edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='vto_edits'
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['vto', 'key']]

    def __str__(self):
        return f'{self.vto} — {self.get_key_display()}'

    def save_content(self, content, user):
        """Save content and snapshot history (keep last 5)."""
        if self.content:
            VTOSectionHistory.objects.create(
                section=self,
                content=self.content,
                edited_by=self.last_edited_by,
                edited_at=self.last_edited_at or timezone.now(),
            )
            # Trim to last 5
            old_ids = (
                self.history.order_by('-edited_at')
                .values_list('pk', flat=True)[5:]
            )
            if old_ids:
                VTOSectionHistory.objects.filter(pk__in=list(old_ids)).delete()

        self.content = content
        self.last_edited_by = user
        self.last_edited_at = timezone.now()
        self.save()


class VTOSectionHistory(models.Model):
    section = models.ForeignKey(
        VTOSection, on_delete=models.CASCADE, related_name='history'
    )
    content = models.TextField()
    edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='vto_history'
    )
    edited_at = models.DateTimeField()

    class Meta:
        ordering = ['-edited_at']
