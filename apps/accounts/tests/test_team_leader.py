from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team, UserProfile
from apps.accounts.scoping import is_team_leader


class TeamLeaderCanManageOwnTeamTest(TestCase):
    """A Leader may change membership of a team they are on, but no other (#137)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Harbour')
        self.team = Team.objects.create(organization=self.org, name='Leadership')
        self.other_team = Team.objects.create(organization=self.org, name='Operations')
        self.leader = User.objects.create_user(username='leader', password='pw')
        self.member = User.objects.create_user(username='member', password='pw')
        Membership.objects.create(user=self.leader, organization=self.org, role=Membership.ROLE_LEADER)
        Membership.objects.create(user=self.member, organization=self.org, role=Membership.ROLE_MEMBER)
        UserProfile.objects.get_or_create(user=self.leader)
        UserProfile.objects.get_or_create(user=self.member)
        self.leader.profile.teams.add(self.team)

    def test_is_team_leader_true_only_on_own_team(self):
        self.assertTrue(is_team_leader(self.leader, self.team))
        self.assertFalse(is_team_leader(self.leader, self.other_team))

    def test_member_is_never_a_team_leader(self):
        self.assertFalse(is_team_leader(self.member, self.team))

    def test_leader_can_update_members_of_own_team(self):
        self.client.force_login(self.leader)
        resp = self.client.post(
            f'/teams/{self.team.pk}/members/', {'users': [self.leader.pk, self.member.pk]}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.team, self.member.profile.teams.all())

    def test_leader_cannot_update_members_of_a_different_team(self):
        self.client.force_login(self.leader)
        resp = self.client.post(f'/teams/{self.other_team.pk}/members/', {'users': [self.leader.pk]})
        self.assertEqual(resp.status_code, 403)

    def test_plain_member_cannot_update_team_members(self):
        self.client.force_login(self.member)
        resp = self.client.post(f'/teams/{self.team.pk}/members/', {'users': [self.member.pk]})
        self.assertEqual(resp.status_code, 403)

    def test_leader_sees_the_manage_members_control_on_own_team_page(self):
        self.client.force_login(self.leader)
        resp = self.client.get(f'/teams/{self.team.pk}/')
        self.assertTrue(resp.context['can_manage_members'])
        self.assertContains(resp, 'Save members')

    def test_leader_does_not_see_the_manage_members_control_on_another_team_page(self):
        self.client.force_login(self.leader)
        resp = self.client.get(f'/teams/{self.other_team.pk}/')
        self.assertFalse(resp.context['can_manage_members'])
