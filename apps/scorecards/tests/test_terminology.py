from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.scorecards.models import Scorecard, ScorecardEntry, ScorecardMetric, _current_week_start

METRICS_HOST = 'metrics.example.test'
PLAIN_HOST = 'plain.example.test'

# 'scorecard' is distinct from the shipped default ('Metrics Board') so the
# default-host test below can tell "customised" apart from "just happens to
# match the default."
METRICS_WORDS = {
    'scorecard': 'Scoreboard', 'scorecards': 'Scoreboards',
    'core_value': 'Value', 'core_values': 'Values',
    'rock': 'Priority', 'rocks': 'Priorities',
    'issue': 'Blocker', 'issues': 'Blockers',
    'vto': 'Vision Plan',
}


@override_settings(ALLOWED_HOSTS=['testserver', METRICS_HOST, PLAIN_HOST])
class ScorecardTerminologyTest(TestCase):
    """Scorecard pages and messages use the organisation's own words."""

    def setUp(self):
        self.metrics_org = Organization.objects.create(name='Metrics Org', terminology=METRICS_WORDS)
        self.plain_org = Organization.objects.create(name='Plain Org')
        OrganizationDomain.objects.create(organization=self.metrics_org, hostname=METRICS_HOST)
        OrganizationDomain.objects.create(organization=self.plain_org, hostname=PLAIN_HOST)

        self.metrics_team = Team.objects.create(organization=self.metrics_org, name='Leadership')
        self.plain_team = Team.objects.create(organization=self.plain_org, name='Leadership')

        self.user = User.objects.create_user(username='scterms', password='pw')
        Membership.objects.create(user=self.user, organization=self.metrics_org)
        Membership.objects.create(user=self.user, organization=self.plain_org)
        self.user.profile.teams.add(self.metrics_team, self.plain_team)

        self.metrics_board = Scorecard.objects.create(name='Weekly Numbers', team=self.metrics_team)
        self.plain_scorecard = Scorecard.objects.create(name='Weekly Numbers', team=self.plain_team)
        self.client.force_login(self.user)

    def add_off_track_entry(self, scorecard):
        metric = ScorecardMetric.objects.create(
            scorecard=scorecard, name='Revenue', owner=self.user,
            goal_value=Decimal('10'), goal_direction=ScorecardMetric.DIR_ABOVE,
        )
        return ScorecardEntry.objects.create(
            metric=metric, period_start=_current_week_start(), value=Decimal('5'),
            entered_by=self.user,
        )

    def test_list_uses_the_organisation_words(self):
        resp = self.client.get('/scorecards/', HTTP_HOST=METRICS_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Scoreboards — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Scoreboards</h1>')
        self.assertContains(resp, 'New Scoreboard')
        self.assertContains(resp, 'metrics per scoreboard.')
        self.assertContains(resp, 'Edit scoreboard')
        self.assertNotContains(resp, 'New Scorecard')
        self.assertNotContains(resp, 'Edit scorecard')

    def test_empty_list_uses_the_organisation_words(self):
        self.metrics_board.delete()
        resp = self.client.get('/scorecards/', HTTP_HOST=METRICS_HOST)
        self.assertContains(resp, 'No Scoreboards yet')
        self.assertContains(resp, 'Create first Scoreboard')

    def test_detail_uses_the_organisation_words(self):
        self.add_off_track_entry(self.metrics_board)
        resp = self.client.get(f'/scorecards/{self.metrics_board.pk}/', HTTP_HOST=METRICS_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Weekly Numbers — Scoreboard — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Edit scoreboard')
        self.assertContains(resp, 'title="Escalate to Blocker"')
        self.assertContains(resp, 'to escalate to Blockers')
        self.assertNotContains(resp, 'Escalate to Issue')

    def test_form_and_delete_pages_use_the_organisation_words(self):
        resp = self.client.get('/scorecards/new/', HTTP_HOST=METRICS_HOST)
        self.assertContains(resp, '<title>Create Scoreboard — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Create Scoreboard</h1>')
        self.assertContains(resp, 'placeholder="e.g. Leadership Team Scoreboard"')
        self.assertContains(resp, 'placeholder="What does this scoreboard measure?"')

        resp = self.client.get(f'/scorecards/{self.metrics_board.pk}/delete/', HTTP_HOST=METRICS_HOST)
        self.assertContains(resp, '<title>Delete Scoreboard — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Delete Scoreboard?')

    def test_create_message_uses_the_organisation_word(self):
        resp = self.client.post(
            '/scorecards/new/',
            {'name': 'Sales Numbers', 'team': self.metrics_team.pk, 'is_active': 'on'},
            HTTP_HOST=METRICS_HOST, follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Scoreboard &quot;Sales Numbers&quot; created.')
        self.assertTrue(Scorecard.objects.filter(name='Sales Numbers', team=self.metrics_team).exists())

    def test_update_and_delete_messages_use_the_organisation_word(self):
        resp = self.client.post(
            f'/scorecards/{self.metrics_board.pk}/edit/',
            {'name': 'Renamed', 'team': self.metrics_team.pk, 'is_active': 'on'},
            HTTP_HOST=METRICS_HOST, follow=True,
        )
        self.assertContains(resp, 'Scoreboard &quot;Renamed&quot; updated.')

        resp = self.client.post(
            f'/scorecards/{self.metrics_board.pk}/delete/', HTTP_HOST=METRICS_HOST, follow=True
        )
        self.assertContains(resp, 'Scoreboard &quot;Renamed&quot; deleted.')

    def test_escalate_message_uses_the_organisation_word(self):
        entry = self.add_off_track_entry(self.metrics_board)
        resp = self.client.post(
            f'/scorecards/entry/{entry.pk}/escalate/', HTTP_HOST=METRICS_HOST, follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Blocker created for off-track metric &quot;Revenue&quot;.')

    def test_default_host_shows_the_generic_words(self):
        resp = self.client.get('/scorecards/', HTTP_HOST=PLAIN_HOST)
        self.assertContains(resp, '<title>Metrics Boards — Plain Org</title>', html=True)
        self.assertContains(resp, 'Metrics Boards</h1>')
        self.assertContains(resp, 'New Metrics Board')
        self.assertContains(resp, 'Edit metrics board')
        self.assertNotContains(resp, 'Scoreboard')

        resp = self.client.post(
            '/scorecards/new/',
            {'name': 'Sales Numbers', 'team': self.plain_team.pk, 'is_active': 'on'},
            HTTP_HOST=PLAIN_HOST, follow=True,
        )
        self.assertContains(resp, 'Metrics Board &quot;Sales Numbers&quot; created.')
