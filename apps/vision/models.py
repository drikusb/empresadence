from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Organization

from . import structure


# ── Section key constants ────────────────────────────────────────────────────

class SectionKey:
    """The keys the shipped default structure stores its content against.

    These are identifiers, not a fixed list of what a vision document may
    contain — an organisation's own structure can use any key it likes. The
    labels, ordering, grouping and render style all live in
    ``apps.vision.structure`` now.
    """

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

    # Legacy key kept so existing DB rows and the data migration remain valid.
    THREE_UNIQUES = 'three_uniques'


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
    # No choices: the valid keys are whatever the organisation's own structure
    # defines (see apps.vision.structure), which the views validate against.
    key = models.CharField(max_length=40)
    content = models.TextField(blank=True)
    last_edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='vto_edits'
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['vto', 'key']]

    def __str__(self):
        # The key, not a label: the field has no choices any more (labels come
        # from the organisation's own structure), and resolving one here would
        # mean a query per row when the export walks every section.
        return f'{self.vto} — {self.key}'

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


class VisionPage(models.Model):
    """One page of an organisation's vision document — a column on screen.

    An organisation with no pages uses the shipped default structure (see
    ``apps.vision.structure``); creating pages is what opts it into its own.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='vision_pages'
    )
    label = models.CharField(max_length=100)
    icon = models.CharField(
        max_length=40, blank=True,
        help_text='Bootstrap icon name, e.g. bi-eye. Optional.',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.organization.name} — {self.label}'


class VisionSectionGroup(models.Model):
    """One card on a page, grouping related sections."""

    page = models.ForeignKey(VisionPage, on_delete=models.CASCADE, related_name='groups')
    label = models.CharField(max_length=100)
    hint = models.CharField(
        max_length=200, blank=True,
        help_text='Optional one-line hint shown under the card heading.',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.page.label} — {self.label}'


class VisionSectionDefinition(models.Model):
    """One editable free-text section inside a group.

    ``key`` is what ``VTOSection.content`` is stored against, so renaming a
    section's label keeps its content and changing its key moves to a fresh,
    empty one — the old content stays in the database, reachable again if the
    key comes back.
    """

    group = models.ForeignKey(
        VisionSectionGroup, on_delete=models.CASCADE, related_name='sections'
    )
    key = models.SlugField(max_length=40)
    label = models.CharField(
        max_length=100, blank=True,
        help_text="Leave blank when the card's own heading is label enough.",
    )
    order = models.PositiveSmallIntegerField(default=0)
    render_as = models.CharField(
        max_length=20, choices=structure.RENDER_CHOICES, default=structure.RENDER_TEXT,
    )
    half_width = models.BooleanField(
        default=False,
        help_text='Show two of these side by side, as the revenue and profit targets are.',
    )

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.group.label} — {self.label or self.key}'

    def clean(self):
        """No two sections in one organisation may share a key.

        They are stored against the same ``VTOSection`` rows, so duplicates
        would silently show and edit the same content in two places.
        """
        if not self.group_id or not self.key:
            return
        clash = (
            VisionSectionDefinition.objects
            .filter(group__page__organization_id=self.group.page.organization_id, key=self.key)
            .exclude(pk=self.pk)
            .exists()
        )
        if clash:
            raise ValidationError(
                {'key': f'Another section in this organisation already uses the key "{self.key}".'}
            )


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
