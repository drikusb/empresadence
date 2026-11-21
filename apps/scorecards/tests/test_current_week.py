from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.scorecards.models import Scorecard, ScorecardEntry, ScorecardMetric, _current_week_start

CURRENT_WEEK_BORDER = 'style="border-left:2px solid #0d6efd"'


class CurrentWeekColumnTest(TestCase):
    """The body rows mark the current week's column, as the header does."""

    def setUp(self):
        org = Organization.objects.create(name='Week Org')
        team = Team.objects.create(organization=org, name='Week Team')
        self.user = User.objects.create_user(username='weekuser', password='pw')
        Membership.objects.create(user=self.user, organization=org, role=Membership.ROLE_ADMIN)
        self.user.profile.teams.add(team)
        self.scorecard = Scorecard.objects.create(name='Weekly numbers', team=team)
        self.client.force_login(self.user)

    def metric(self, name):
        return ScorecardMetric.objects.create(
            scorecard=self.scorecard, name=name, owner=self.user,
            metric_type=ScorecardMetric.TYPE_INTEGER, goal_value=10,
            goal_direction=ScorecardMetric.DIR_ABOVE, frequency=ScorecardMetric.FREQ_WEEKLY,
        )

    def page(self):
        resp = self.client.get(f'/scorecards/{self.scorecard.pk}/')
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_each_metric_row_marks_exactly_one_cell(self):
        entered = self.metric('Entered this week')
        self.metric('Not entered yet')
        ScorecardEntry.objects.create(
            metric=entered, period_start=_current_week_start(), value=12, on_track=True,
            entered_by=self.user,
        )
        self.assertContains(self.page(), CURRENT_WEEK_BORDER, count=2)

    def test_marked_cell_is_the_current_weeks(self):
        self.metric('Only metric')
        resp = self.page()
        for row in resp.context['table']:
            marked = [period for period, _ in row['period_cells'] if period == resp.context['current_week']]
            self.assertEqual(marked, [_current_week_start()])
            self.assertEqual(row['period_cells'][-1][0], _current_week_start())

    def test_no_metrics_means_no_marked_cells(self):
        self.assertNotContains(self.page(), CURRENT_WEEK_BORDER)
