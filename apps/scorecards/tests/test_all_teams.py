"""The Scorecards list can show every team the user may see, as the Rocks list can."""
from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.scorecards.models import Scorecard
from apps.scorecards.views import SCOPE_SESSION_KEY

LIST_URL = '/scorecards/'


class AllTeamsScopeTestBase(TestCase):
    """One organisation, four teams; Delta has no Scorecards.

    ``member`` is on Alpha and Beta; ``admin`` is an organisation admin on Alpha
    only; ``pair`` is on Alpha and Delta; ``solo`` is on Delta alone; ``loner``
    is a member of the organisation but on no team. Alpha is the active team
    for everyone on it because it sorts first by name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Scope Org')
        cls.alpha = Team.objects.create(organization=cls.org, name='Alpha')
        cls.beta = Team.objects.create(organization=cls.org, name='Beta')
        cls.gamma = Team.objects.create(organization=cls.org, name='Gamma')
        cls.delta = Team.objects.create(organization=cls.org, name='Delta')

        cls.member = cls.make_user('scopemember', cls.alpha, cls.beta)
        cls.admin = cls.make_user('scopeadmin', cls.alpha, role=Membership.ROLE_ADMIN)
        cls.pair = cls.make_user('scopepair', cls.alpha, cls.delta)
        cls.solo = cls.make_user('scopesolo', cls.delta)
        cls.loner = cls.make_user('scopeloner')

        cls.alpha_numbers = Scorecard.objects.create(name='Alpha numbers', team=cls.alpha)
        cls.alpha_sales = Scorecard.objects.create(name='Alpha sales', team=cls.alpha)
        cls.beta_numbers = Scorecard.objects.create(name='Beta numbers', team=cls.beta)
        cls.gamma_numbers = Scorecard.objects.create(name='Gamma numbers', team=cls.gamma)
        # An inactive Scorecard is neither listed nor counted in the hint.
        Scorecard.objects.create(name='Beta retired', team=cls.beta, is_active=False)

    @classmethod
    def make_user(cls, username, *teams, role=Membership.ROLE_MEMBER):
        user = User.objects.create_user(username=username, password='pw')
        Membership.objects.create(user=user, organization=cls.org, role=role)
        user.profile.teams.add(*teams)
        return user

    @staticmethod
    def team_names(resp):
        return [team.name for team, _ in resp.context['teams_summaries']]

    @staticmethod
    def scorecard_names(resp):
        return [sc.name for sc in resp.context['scorecards']]


class DefaultScopeTest(AllTeamsScopeTestBase):
    def test_default_shows_only_the_active_team(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['scope'], 'team')
        self.assertEqual(self.team_names(resp), ['Alpha'])
        self.assertEqual(self.scorecard_names(resp), ['Alpha numbers', 'Alpha sales'])
        self.assertNotContains(resp, 'Beta numbers')
        self.assertNotContains(resp, 'Gamma numbers')
        # A single team gets no heading; each card already names its team.
        self.assertNotContains(resp, '<h5 class="mb-0 me-2">Alpha</h5>')

    def test_unknown_scope_value_is_ignored(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL, {'scope': 'bogus'})
        self.assertEqual(resp.context['scope'], 'team')
        self.assertNotIn(SCOPE_SESSION_KEY, self.client.session)

    def test_toggle_is_offered_to_a_user_on_several_teams(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL)
        self.assertContains(resp, 'This team')
        self.assertContains(resp, 'All teams')
        self.assertContains(resp, 'href="?scope=all"')

    def test_toggle_is_absent_for_a_user_on_one_team(self):
        self.client.force_login(self.solo)
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([t.name for t in resp.context['visible_teams']], ['Delta'])
        self.assertNotContains(resp, 'This team')
        self.assertNotContains(resp, 'All teams')


class AllScopeTest(AllTeamsScopeTestBase):
    def test_all_scope_groups_the_users_teams_and_skips_others(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['scope'], 'all')
        self.assertEqual(self.team_names(resp), ['Alpha', 'Beta'])
        self.assertEqual(
            self.scorecard_names(resp), ['Alpha numbers', 'Alpha sales', 'Beta numbers']
        )
        self.assertContains(resp, '<h5 class="mb-0 me-2">Alpha</h5>')
        self.assertContains(resp, '<h5 class="mb-0 me-2">Beta</h5>')
        self.assertNotContains(resp, 'Gamma numbers')
        self.assertEqual(
            [t.name for t in resp.context['scoped_teams']], ['Alpha', 'Beta']
        )

    def test_org_admin_sees_every_team_in_the_organisation(self):
        self.client.force_login(self.admin)
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertEqual(self.team_names(resp), ['Alpha', 'Beta', 'Gamma'])
        self.assertContains(resp, '<h5 class="mb-0 me-2">Gamma</h5>')
        self.assertContains(resp, 'Gamma numbers')

    def test_inactive_scorecards_are_never_listed(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertNotIn('Beta retired', self.scorecard_names(resp))
        self.assertNotContains(resp, 'Beta retired')

    def test_scope_persists_in_the_session(self):
        self.client.force_login(self.member)
        self.client.get(LIST_URL, {'scope': 'all'})
        self.assertEqual(self.client.session[SCOPE_SESSION_KEY], 'all')
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.context['scope'], 'all')
        self.assertEqual(self.team_names(resp), ['Alpha', 'Beta'])

    def test_scope_is_kept_apart_from_the_rocks_list(self):
        """Widening the Scorecards list leaves the Rocks list's scope alone."""
        self.assertEqual(SCOPE_SESSION_KEY, 'scorecards_scope')
        self.client.force_login(self.member)
        self.client.get(LIST_URL, {'scope': 'all'})
        self.assertNotIn('rocks_scope', self.client.session)

    def test_scope_team_returns_to_the_active_team(self):
        self.client.force_login(self.member)
        self.client.get(LIST_URL, {'scope': 'all'})
        resp = self.client.get(LIST_URL, {'scope': 'team'})
        self.assertEqual(resp.context['scope'], 'team')
        self.assertEqual(self.client.session[SCOPE_SESSION_KEY], 'team')
        self.assertEqual(self.team_names(resp), ['Alpha'])
        resp = self.client.get(LIST_URL)
        self.assertEqual(self.team_names(resp), ['Alpha'])

    def test_empty_state_names_all_teams(self):
        self.client.force_login(self.solo)
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertEqual(resp.context['teams_summaries'], [])
        self.assertContains(resp, 'No Metrics Boards on any of your teams yet.')
        self.assertNotContains(resp, 'No Metrics Boards yet')

    def test_single_team_empty_state_is_unchanged(self):
        self.client.force_login(self.solo)
        resp = self.client.get(LIST_URL)
        self.assertContains(resp, 'No Metrics Boards yet')
        self.assertNotContains(resp, 'on any of your teams')

    def test_user_with_no_teams_gets_an_empty_list(self):
        self.client.force_login(self.loner)
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['teams_summaries'], [])
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['teams_summaries'], [])
        self.assertEqual(resp.context['scoped_teams'], [])
        self.assertNotContains(resp, 'All teams')


class ScopeHintTest(AllTeamsScopeTestBase):
    def test_team_scope_hints_at_scorecards_on_other_teams(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL)
        self.assertContains(resp, 'Showing Alpha')
        self.assertContains(resp, '1 more on other teams')
        self.assertEqual(resp.context['other_scorecards_total'], 1)
        self.assertEqual(
            [(t.name, n) for t, n in resp.context['other_team_counts']], [('Beta', 1)]
        )
        self.assertContains(resp, 'href="?scope=all" title="Beta: 1"')

    def test_hint_counts_only_teams_the_user_may_see(self):
        """Gamma's Scorecard counts for the admin but not for the member."""
        self.client.force_login(self.admin)
        resp = self.client.get(LIST_URL)
        self.assertContains(resp, '2 more on other teams')
        self.assertEqual(
            [(t.name, n) for t, n in resp.context['other_team_counts']],
            [('Beta', 1), ('Gamma', 1)],
        )
        self.assertContains(resp, 'title="Beta: 1, Gamma: 1"')

    def test_hint_ignores_inactive_scorecards(self):
        Scorecard.objects.filter(pk=self.beta_numbers.pk).update(is_active=False)
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.context['other_scorecards_total'], 0)
        self.assertNotContains(resp, 'more on other teams')

    def test_hint_is_absent_when_other_teams_have_nothing(self):
        self.client.force_login(self.pair)
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.context['other_scorecards_total'], 0)
        self.assertNotContains(resp, 'more on other teams')
        self.assertNotContains(resp, 'Showing Alpha')
        # The toggle still offers the other team.
        self.assertContains(resp, 'All teams')

    def test_all_scope_hint_links_back_to_the_team(self):
        self.client.force_login(self.member)
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertContains(resp, 'Showing all your teams (2)')
        self.assertContains(resp, 'Back to Alpha')
        self.assertContains(resp, 'href="?scope=team"')
        self.assertNotContains(resp, 'more on other teams')


class ScopeTerminologyTest(TestCase):
    """The new wording follows the organisation's own word for Scorecards."""

    def setUp(self):
        self.org = Organization.objects.create(
            name='Words Org',
            terminology={'scorecard': 'Metrics Board', 'scorecards': 'Metrics Boards'},
        )
        self.ops = Team.objects.create(organization=self.org, name='Ops')
        self.sales = Team.objects.create(organization=self.org, name='Sales')
        self.user = User.objects.create_user(username='scopewords', password='pw')
        Membership.objects.create(user=self.user, organization=self.org)
        self.user.profile.teams.add(self.ops, self.sales)
        self.client.force_login(self.user)

    def test_all_scope_empty_state_uses_the_organisation_word(self):
        resp = self.client.get(LIST_URL, {'scope': 'all'})
        self.assertContains(resp, 'No Metrics Boards on any of your teams yet.')
        self.assertContains(resp, 'Create first Metrics Board')

    def test_team_heading_badge_uses_the_organisation_word(self):
        Scorecard.objects.create(name='Ops numbers', team=self.ops)
        Scorecard.objects.create(name='Sales one', team=self.sales)
        Scorecard.objects.create(name='Sales two', team=self.sales)
        body = self.client.get(LIST_URL, {'scope': 'all'}).content.decode()
        self.assertRegex(body, r'1\s+Metrics Board\s*</span>')
        self.assertRegex(body, r'2\s+Metrics Boards\s*</span>')
