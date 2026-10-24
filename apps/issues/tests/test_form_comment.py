from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Membership, Organization, Team, UserProfile


class IssueFormCommentTest(TestCase):
    """A template comment written across two lines rendered as page text."""

    def setUp(self):
        org = Organization.objects.create(name='Harbour')
        team = Team.objects.create(organization=org, name='Leadership')
        self.user = User.objects.create_user(username='admin', password='pw')
        Membership.objects.create(user=self.user, organization=org, role=Membership.ROLE_ADMIN)
        UserProfile.objects.get_or_create(user=self.user)
        self.user.profile.teams.add(team)
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:team_switch', args=[team.pk]), {'next': '/'})

    def test_create_page_renders_no_template_comment_text(self):
        resp = self.client.get(reverse('issues:create'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Company-wide flag (admins only')
        self.assertNotContains(resp, '{#')
        self.assertNotContains(resp, '#}')
