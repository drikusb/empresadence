from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.text import slugify
from django.db.models.signals import post_save
from django.dispatch import receiver


class Organization(models.Model):
    NAVBAR_DARK = 'dark'
    NAVBAR_LIGHT = 'light'
    NAVBAR_PRIMARY = 'primary'
    NAVBAR_CHOICES = [
        (NAVBAR_DARK, 'Dark'),
        (NAVBAR_LIGHT, 'Light'),
        (NAVBAR_PRIMARY, 'Primary colour'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    display_name = models.CharField(
        max_length=100, blank=True,
        help_text='Shown in the navbar, page titles and emails. Defaults to the organisation name.',
    )
    tagline = models.CharField(max_length=200, blank=True)
    favicon = models.FileField(
        upload_to='org_favicons/', blank=True, null=True,
        validators=[FileExtensionValidator(['ico', 'png', 'svg'])],
    )
    primary_color = models.CharField(
        max_length=7, blank=True,
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Use a hex colour like #0d6efd.')],
    )
    navbar_style = models.CharField(max_length=10, choices=NAVBAR_CHOICES, default=NAVBAR_DARK)
    email_from_name = models.CharField(max_length=100, blank=True)
    support_email = models.EmailField(blank=True)
    terminology = models.JSONField(
        default=dict, blank=True,
        help_text='Words this organisation uses instead of the shipped defaults, '
                  'e.g. {"rock": "Priority", "rocks": "Priorities"}. Only overrides are stored.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_display_name(self):
        return self.display_name or self.name

    def get_absolute_url(self):
        return reverse('accounts:org_detail')

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first() or self.domains.first()

    @property
    def site_url(self):
        """Absolute base URL for this organisation, or '' when it has no domain."""
        domain = self.primary_domain
        if domain is None:
            return ''
        scheme = urlsplit(settings.SITE_URL).scheme or 'https'
        return f'{scheme}://{domain.hostname}'


class OrganizationDomain(models.Model):
    """A hostname that resolves to one organisation. Requests on it are pinned to that org."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='domains'
    )
    hostname = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'hostname']
        constraints = [
            models.UniqueConstraint(
                fields=['organization'],
                condition=Q(is_primary=True),
                name='one_primary_domain_per_organization',
            ),
        ]
        verbose_name = 'Organization domain'
        verbose_name_plural = 'Organization domains'

    def __str__(self):
        return self.hostname

    @staticmethod
    def normalize(hostname):
        return (hostname or '').strip().lower().rstrip('.')

    def clean(self):
        self.hostname = self.normalize(self.hostname)
        if not self.hostname:
            raise ValidationError({'hostname': 'Enter a hostname.'})
        if any(ch in self.hostname for ch in '/:') or any(ch.isspace() for ch in self.hostname):
            raise ValidationError({
                'hostname': 'Enter a bare hostname such as acme.example.com — no scheme, port or path.',
            })

    def save(self, *args, **kwargs):
        self.hostname = self.normalize(self.hostname)
        super().save(*args, **kwargs)


class Team(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='teams'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['organization', 'name']]
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts:team_detail', kwargs={'pk': self.pk})

    def member_count(self):
        return self.members.count()


class Membership(models.Model):
    """A user's place in one organisation. A user may belong to several."""

    ROLE_ADMIN = 'admin'
    ROLE_LEADER = 'leader'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_LEADER, 'Team Leader'),
        (ROLE_MEMBER, 'Team Member'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name']
        unique_together = [['user', 'organization']]
        verbose_name = 'Membership'
        verbose_name_plural = 'Memberships'

    def __str__(self):
        return f'{self.user} — {self.organization} ({self.get_role_display()})'

    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class OrganizationInvitation(models.Model):
    """An invitation for someone who already has an account to join an organisation.

    Membership starts only when the invited person accepts, so an admin cannot
    attach somebody's account to their organisation without that person agreeing.
    """

    TOKEN_SALT = 'accounts.organization_invitation'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invitations'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='organization_invitations'
    )
    role = models.CharField(
        max_length=20, choices=Membership.ROLE_CHOICES, default=Membership.ROLE_MEMBER
    )
    teams = models.ManyToManyField(Team, blank=True, related_name='invitations')
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'user'],
                condition=Q(accepted_at=None, declined_at=None, withdrawn_at=None),
                name='one_open_invitation_per_user_and_org',
            ),
        ]
        verbose_name = 'Organisation invitation'
        verbose_name_plural = 'Organisation invitations'

    def __str__(self):
        return f'{self.user} — {self.organization}'

    def save(self, *args, **kwargs):
        if self.expires_at is None:
            self.expires_at = self.new_expiry()
        super().save(*args, **kwargs)

    @staticmethod
    def new_expiry():
        return timezone.now() + timedelta(days=settings.INVITATION_EXPIRY_DAYS)

    @classmethod
    def open_q(cls):
        """Invitations nobody has answered or withdrawn, expired or not."""
        return Q(accepted_at=None, declined_at=None, withdrawn_at=None)

    @property
    def is_open(self):
        return not (self.accepted_at or self.declined_at or self.withdrawn_at)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def can_be_answered(self):
        return self.is_open and not self.is_expired

    @property
    def token(self):
        """Ties the link to this invitation and this account; unguessable from the id."""
        return salted_hmac(self.TOKEN_SALT, f'{self.pk}:{self.user_id}').hexdigest()[:32]

    def check_token(self, token):
        return constant_time_compare(self.token, token or '')

    def get_absolute_url(self):
        return reverse('accounts:invitation_respond', kwargs={'pk': self.pk, 'token': self.token})

    def accept(self):
        """Create the membership and add the teams. Returns the membership."""
        membership, _ = Membership.objects.get_or_create(
            user=self.user, organization=self.organization, defaults={'role': self.role},
        )
        self.user.profile.teams.add(*self.teams.filter(organization=self.organization))
        self.accepted_at = timezone.now()
        self.save(update_fields=['accepted_at'])
        return membership


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    teams = models.ManyToManyField(Team, blank=True, related_name='members')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return self.display_name()

    def get_absolute_url(self):
        return reverse('accounts:profile')

    def display_name(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
