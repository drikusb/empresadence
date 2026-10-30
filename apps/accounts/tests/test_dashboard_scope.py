"""The dashboard counts every team the user may see by default, or the active team alone."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Membership, Organization, Team
from apps.accounts.views import HomeView
from apps.issues.models import Issue
from apps.meetings.models import Meeting
from apps.rocks.models import Rock
from apps.scorecards.models import Scorecard, ScorecardEntry, ScorecardMetric, _current_week_start
from apps.todos.models import ToDo

SESSION_KEY = HomeView.scope_session_key
TOGGLE = 'aria-label="Which teams to show"'


class DashboardScopeTestBase(TestCase):
    """One organisation, three teams, each with one Rock, Issue and scheduled meeting.

    ``member`` is on Alpha and Beta; ``admin`` is an organisation admin on Alpha
    only; ``solo`` is on Alpha alone; ``loner`` is a member of the organisation
    but on no team. Alpha is everyone's active team because it sorts first by
    name. Beta's Rock is off track, Beta and Gamma each have an open To-Do owned
    by ``admin``, and Alpha and Beta each have one Scorecard entry this week,
    Beta's off track. Gamma's meeting is the soonest, then Beta's, then Alpha's.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Dash Org')
        cls.alpha = Team.objects.create(organization=cls.org, name='Alpha')
        cls.beta = Team.objects.create(organization=cls.org, name='Beta')
        cls.gamma = Team.objects.create(organization=cls.org, name='Gamma')

        cls.member = cls.make_user('dashmember', cls.alpha, cls.beta)
        cls.admin = cls.make_user('dashadmin', cls.alpha, role=Membership.ROLE_ADMIN)
        cls.solo = cls.make_user('dashsolo', cls.alpha)
        cls.loner = cls.make_user('dashloner')

        today = date.today()
        for days, team, status in (
            (7, cls.alpha, Rock.STATUS_ON_TRACK),
            (3, cls.beta, Rock.STATUS_OFF_TRACK),
            (1, cls.gamma, Rock.STATUS_ON_TRACK),
        ):
            Rock.objects.create(
                title=f'{team.name} rock', owner=cls.admin, team=team, status=status,
                quarter=Rock.current_quarter(), year=Rock.current_year(),
                due_date=today + timedelta(days=90),
            )
            Issue.objects.create(title=f'{team.name} issue', originating_team=team)
            Meeting.objects.create(team=team, scheduled_date=today + timedelta(days=days))
        # A resolved Issue and a completed Rock are never counted.
        Issue.objects.create(
            title='Beta solved', originating_team=cls.beta, status=Issue.STATUS_RESOLVED
        )
        Rock.objects.create(
            title='Beta done', owner=cls.admin, team=cls.beta, status=Rock.STATUS_COMPLETE,
            quarter=Rock.current_quarter(), year=Rock.current_year(),
            due_date=today + timedelta(days=90),
        )
        ToDo.objects.create(title='Beta todo', owner=cls.admin, team=cls.beta)
        ToDo.objects.create(title='Gamma todo', owner=cls.admin, team=cls.gamma)

        week = _current_week_start()
        for team, on_track in ((cls.alpha, True), (cls.beta, False)):
            scorecard = Scorecard.objects.create(name=f'{team.name} numbers', team=team)
            metric = ScorecardMetric.objects.create(
                scorecard=scorecard, name=f'{team.name} metric', owner=cls.admin, goal_value=10
            )
            ScorecardEntry.objects.create(
                metric=metric, period_start=week, value=10 if on_track else 1, on_track=on_track
            )

    @classmethod
    def make_user(cls, username, *teams, role=Membership.ROLE_MEMBER):
        user = User.objects.create_user(username=username, password='pw')
        Membership.objects.create(user=user, organization=cls.org, role=role)
        user.profile.teams.add(*teams)
        return user

    def get_home(self, **params):
        resp = self.client.get(reverse('home'), params)
        self.assertEqual(resp.status_code, 200)
        return resp

    @staticmethod
    def counts(resp):
        ctx = resp.context
        return {
            'active_rocks': ctx['active_rocks'],
            'off_track_rocks': ctx['off_track_rocks'],
            'open_issues': ctx['open_issues'],
            'open_todos': ctx['open_todos'],
            'next_meeting': ctx['next_meeting'].team.name,
            'scorecard_total': ctx['scorecard_total'],
            'scorecard_off_track': ctx['scorecard_off_track'],
        }


ALPHA_ONLY = {
    'active_rocks': 1, 'off_track_rocks': 0, 'open_issues': 1, 'open_todos': 0,
    'next_meeting': 'Alpha', 'scorecard_total': 1, 'scorecard_off_track': 0,
}
ALPHA_AND_BETA = {
    'active_rocks': 2, 'off_track_rocks': 1, 'open_issues': 2, 'open_todos': 1,
    'next_meeting': 'Beta', 'scorecard_total': 2, 'scorecard_off_track': 1,
}


class DefaultScopeTest(DashboardScopeTestBase):
    def test_default_counts_every_team_the_user_is_on(self):
        self.client.force_login(self.member)
        resp = self.get_home()
        self.assertEqual(resp.context['scope'], 'all')
        self.assertEqual(self.counts(resp), ALPHA_AND_BETA)
        self.assertEqual(
            [t.name for t in resp.context['scoped_teams']], ['Alpha', 'Beta']
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_a_non_admin_never_sees_teams_they_are_not_on(self):
        self.client.force_login(self.member)
        resp = self.get_home(scope='all')
        self.assertEqual(resp.context['active_rocks'], 2)
        self.assertEqual(resp.context['open_issues'], 2)
        self.assertEqual(resp.context['open_todos'], 1)
        self.assertNotEqual(resp.context['next_meeting'].team, self.gamma)
        self.assertNotIn(self.gamma, resp.context['visible_teams'])
        self.assertNotIn(self.gamma, resp.context['scoped_teams'])

    def test_an_org_admin_sees_every_team(self):
        self.client.force_login(self.admin)
        resp = self.get_home()
        self.assertEqual(self.counts(resp), {
            'active_rocks': 3, 'off_track_rocks': 1, 'open_issues': 3, 'open_todos': 2,
            'next_meeting': 'Gamma', 'scorecard_total': 2, 'scorecard_off_track': 1,
        })
        self.assertContains(resp, 'Showing all your teams (3)')

    def test_unknown_scope_value_is_ignored(self):
        self.client.force_login(self.member)
        resp = self.get_home(scope='bogus')
        self.assertEqual(resp.context['scope'], 'all')
        self.assertEqual(self.counts(resp), ALPHA_AND_BETA)
        self.assertNotIn(SESSION_KEY, self.client.session)


class TeamScopeTest(DashboardScopeTestBase):
    def test_team_scope_narrows_to_the_active_team(self):
        self.client.force_login(self.member)
        resp = self.get_home(scope='team')
        self.assertEqual(resp.context['scope'], 'team')
        self.assertEqual(resp.context['active_team'], self.alpha)
        self.assertEqual(self.counts(resp), ALPHA_ONLY)
        self.assertEqual([t.name for t in resp.context['scoped_teams']], ['Alpha'])

    def test_team_scope_persists_under_its_own_session_key(self):
        self.client.force_login(self.member)
        self.get_home(scope='team')
        self.assertEqual(SESSION_KEY, 'dashboard_scope')
        self.assertEqual(self.client.session[SESSION_KEY], 'team')
        self.assertNotIn('rocks_scope', self.client.session)
        self.assertNotIn('scorecards_scope', self.client.session)
        resp = self.get_home()
        self.assertEqual(resp.context['scope'], 'team')
        self.assertEqual(self.counts(resp), ALPHA_ONLY)

    def test_the_lists_keep_their_own_scope(self):
        """Narrowing the dashboard leaves the Rocks and Scorecards lists on their defaults."""
        self.client.force_login(self.member)
        self.get_home(scope='team')
        self.assertEqual(self.client.get('/rocks/').context['scope'], 'team')
        self.assertEqual(self.client.get('/scorecards/').context['scope'], 'team')
        self.client.get('/rocks/', {'scope': 'all'})
        self.client.get('/scorecards/', {'scope': 'all'})
        self.assertEqual(self.get_home().context['scope'], 'team')

    def test_scope_all_widens_again(self):
        self.client.force_login(self.member)
        self.get_home(scope='team')
        resp = self.get_home(scope='all')
        self.assertEqual(resp.context['scope'], 'all')
        self.assertEqual(self.client.session[SESSION_KEY], 'all')
        self.assertEqual(self.counts(resp), ALPHA_AND_BETA)


class ScopeMarkupTest(DashboardScopeTestBase):
    def test_narrowed_banner_names_the_team_and_links_to_all(self):
        self.client.force_login(self.member)
        resp = self.get_home(scope='team')
        self.assertContains(resp, 'alert alert-info')
        self.assertContains(resp, 'Showing <strong>Alpha</strong> only')
        self.assertContains(resp, 'href="?scope=all"')
        self.assertContains(resp, 'Show all teams')
        self.assertNotContains(resp, 'Showing all your teams')
        self.assertNotContains(resp, TOGGLE)

    def test_all_scope_shows_the_line_and_toggle_for_several_teams(self):
        self.client.force_login(self.member)
        resp = self.get_home()
        self.assertNotContains(resp, 'alert alert-info')
        self.assertContains(resp, 'Showing all your teams (2)')
        self.assertContains(resp, TOGGLE)
        self.assertContains(resp, 'This team')
        self.assertContains(resp, 'All teams')
        self.assertContains(resp, 'href="?scope=team"')

    def test_all_scope_line_without_toggle_for_one_team(self):
        self.client.force_login(self.solo)
        resp = self.get_home()
        self.assertEqual(self.counts(resp), ALPHA_ONLY)
        self.assertContains(resp, 'Showing all your teams (1)')
        self.assertNotContains(resp, TOGGLE)
        self.assertNotContains(resp, 'This team')
        self.assertNotContains(resp, 'href="?scope=team"')

    def test_dashboard_heading_is_unchanged(self):
        self.client.force_login(self.member)
        self.assertContains(self.get_home(), 'EOS Dashboard')


class NoTeamTest(DashboardScopeTestBase):
    def test_user_with_no_teams_gets_an_empty_dashboard(self):
        self.client.force_login(self.loner)
        for params in ({}, {'scope': 'all'}, {'scope': 'team'}):
            resp = self.get_home(**params)
            self.assertIsNone(resp.context['active_team'])
            self.assertEqual(resp.context['scoped_teams'], [])
            self.assertNotIn('active_rocks', resp.context)
            self.assertNotIn('next_meeting', resp.context)
            self.assertNotContains(resp, 'Showing all your teams')
            self.assertNotContains(resp, TOGGLE)

    def test_narrowed_with_no_active_team_still_offers_all_teams(self):
        """An org admin on no team may have chosen the team scope; the banner leads back."""
        self.admin.profile.teams.clear()
        self.client.force_login(self.admin)
        resp = self.get_home(scope='team')
        self.assertIsNone(resp.context['active_team'])
        self.assertNotIn('active_rocks', resp.context)
        self.assertContains(resp, 'alert alert-info')
        self.assertContains(resp, 'href="?scope=all"')
        resp = self.get_home(scope='all')
        self.assertEqual(resp.context['active_rocks'], 3)
        self.assertContains(resp, 'Showing all your teams (3)')
        # No active team to narrow to, so the toggle is left out.
        self.assertNotContains(resp, TOGGLE)
