from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Membership, Organization, Team, UserProfile
from apps.scorecards.models import Scorecard, ScorecardEntry, ScorecardMetric


class NumberFormattingTest(TestCase):
    """Money and large counts carry thousands separators wherever the scorecard shows them."""

    def setUp(self):
        org = Organization.objects.create(name='Harbour')
        team = Team.objects.create(organization=org, name='Business Development')
        self.user = User.objects.create_user(username='u', password='pw', first_name='Ada')
        Membership.objects.create(user=self.user, organization=org, role=Membership.ROLE_ADMIN)
        UserProfile.objects.get_or_create(user=self.user)
        self.user.profile.teams.add(team)
        self.scorecard = Scorecard.objects.create(name='BD', team=team)
        self.money = ScorecardMetric.objects.create(
            scorecard=self.scorecard, name='New ARR closed', owner=self.user,
            metric_type=ScorecardMetric.TYPE_FLOAT, goal_value=Decimal('50000'),
            goal_direction=ScorecardMetric.DIR_ABOVE, frequency=ScorecardMetric.FREQ_WEEKLY,
        )
        self.count = ScorecardMetric.objects.create(
            scorecard=self.scorecard, name='Devices', owner=self.user,
            metric_type=ScorecardMetric.TYPE_INTEGER, goal_value=Decimal('1200'),
            goal_direction=ScorecardMetric.DIR_ABOVE, frequency=ScorecardMetric.FREQ_WEEKLY,
        )
        monday = date.today()
        monday = monday.fromordinal(monday.toordinal() - monday.weekday())
        ScorecardEntry.objects.create(
            metric=self.money, period_start=monday, value=Decimal('10000'), entered_by=self.user
        )
        ScorecardEntry.objects.create(
            metric=self.count, period_start=monday, value=Decimal('2500'), entered_by=self.user
        )
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:team_switch', args=[team.pk]), {'next': '/'})

    def test_goal_and_value_formatting(self):
        self.assertEqual(self.money.format_goal(), '≥ 50,000.00')
        self.assertEqual(self.money.format_value(Decimal('10000')), '10,000.00')
        self.assertEqual(self.count.format_value(Decimal('2500')), '2,500')
        self.assertEqual(self.count.format_value(Decimal('7')), '7')

    def test_grid_shows_separators(self):
        resp = self.client.get(reverse('scorecards:detail', args=[self.scorecard.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '10,000.00')
        self.assertContains(resp, '2,500')
        self.assertNotContains(resp, '10000.00')

    def test_entry_page_shows_separators(self):
        resp = self.client.get(reverse('scorecards:enter', args=[self.scorecard.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '10,000.00')
