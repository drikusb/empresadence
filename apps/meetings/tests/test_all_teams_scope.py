from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.meetings.models import Meeting


class MeetingListAllTeamsScopeTest(TestCase):
    """A meeting scheduled for another team is now reachable, not just invisible (#131)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Multi-team Org')
        self.leadership = Team.objects.create(organization=self.org, name='Leadership')
        self.operations = Team.objects.create(organization=self.org, name='Operations')
        self.admin = User.objects.create_user(username='orgadmin', password='pw')
        Membership.objects.create(user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN)
        self.admin.profile.teams.add(self.leadership)

        self.single_team_member = User.objects.create_user(username='onlyleader', password='pw')
        Membership.objects.create(user=self.single_team_member, organization=self.org)
        self.single_team_member.profile.teams.add(self.leadership)

        self.leadership_meeting = Meeting.objects.create(
            team=self.leadership, scheduled_date=date.today(), created_by=self.admin,
        )
        self.operations_meeting = Meeting.objects.create(
            team=self.operations, scheduled_date=date.today(), created_by=self.admin,
        )

    def test_default_scope_shows_only_the_active_team(self):
        self.client.force_login(self.admin)
        resp = self.client.get('/meetings/')
        self.assertContains(resp, 'Leadership')
        self.assertEqual([t for t, _ in resp.context['teams_meetings']], [self.leadership])
        self.assertEqual(resp.context['other_meetings_total'], 1)

    def test_all_teams_scope_shows_every_visible_team_s_meetings(self):
        self.client.force_login(self.admin)
        resp = self.client.get('/meetings/?scope=all')
        self.assertEqual(resp.context['scope'], 'all')
        self.assertContains(resp, 'Leadership')
        self.assertContains(resp, 'Operations')

    def test_scope_choice_persists_across_requests_without_the_query_param(self):
        self.client.force_login(self.admin)
        self.client.get('/meetings/?scope=all')
        resp = self.client.get('/meetings/')
        self.assertEqual(resp.context['scope'], 'all')
        self.assertContains(resp, 'Operations')

    def test_a_member_of_one_team_sees_no_toggle_and_no_other_teams(self):
        self.client.force_login(self.single_team_member)
        resp = self.client.get('/meetings/')
        self.assertEqual(list(resp.context['visible_teams']), [self.leadership])
        self.assertNotContains(resp, 'Operations')
