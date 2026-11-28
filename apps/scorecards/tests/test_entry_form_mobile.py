from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.scorecards.models import Scorecard, ScorecardEntry, ScorecardMetric, _current_week_start


class EntryFormStackedLayoutTest(TestCase):
    """The weekly entry table stacks into one card per metric on a phone (#122)."""

    def setUp(self):
        org = Organization.objects.create(name='Entry Org')
        team = Team.objects.create(organization=org, name='Entry Team')
        self.user = User.objects.create_user(
            username='entryuser', password='pw', first_name='Priya', last_name='Owner',
        )
        Membership.objects.create(user=self.user, organization=org, role=Membership.ROLE_ADMIN)
        self.user.profile.teams.add(team)
        self.scorecard = Scorecard.objects.create(name='Weekly numbers', team=team)
        self.metric = ScorecardMetric.objects.create(
            scorecard=self.scorecard, name='Berths occupied', owner=self.user,
            metric_type=ScorecardMetric.TYPE_PERCENTAGE, goal_value=Decimal('85'),
            goal_direction=ScorecardMetric.DIR_ABOVE, frequency=ScorecardMetric.FREQ_WEEKLY,
        )
        self.client.force_login(self.user)
        self.url = f'/scorecards/{self.scorecard.pk}/enter/'

    def test_table_opts_into_the_stacked_layout(self):
        self.assertContains(self.client.get(self.url), 'table-stack-md')

    def test_each_input_has_a_label_for_the_stacked_layout(self):
        resp = self.client.get(self.url)
        pk = self.metric.pk
        for field, text in (('value', 'Value'), ('notes', 'Note')):
            with self.subTest(field=field):
                self.assertContains(resp, f'id="id_{field}_{pk}"', count=1)
                self.assertContains(
                    resp,
                    f'<label for="id_{field}_{pk}" class="form-label small text-muted mb-1 d-md-none">{text}</label>',
                    html=True,
                )

    def test_cells_without_a_heading_carry_their_own_label(self):
        resp = self.client.get(self.url)
        for label in ('Goal', 'Owner', 'Current'):
            with self.subTest(label=label):
                self.assertContains(resp, f'data-label="{label}"', count=1)

    def test_owner_name_is_printed_not_only_a_tooltip(self):
        self.assertContains(
            self.client.get(self.url),
            '<span class="d-md-none text-muted small">Priya Owner</span>', html=True,
        )

    def test_stacked_layout_rules_are_in_the_stylesheet(self):
        css = Path(settings.BASE_DIR, 'static', 'css', 'app.css').read_text()
        self.assertIn('.table-stack-md thead { display: none; }', css)
        self.assertIn('@media (max-width: 767.98px)', css)

    def test_row_states_are_painted_on_the_row_not_in_patches_on_each_cell(self):
        css = Path(settings.BASE_DIR, 'static', 'css', 'app.css').read_text()
        self.assertIn(
            '.table-stack-md > tbody > tr > td { background-color: transparent; box-shadow: none; }', css,
        )
        self.assertIn(
            '.table-stack-md > tbody > tr.table-danger { background-color: var(--bs-danger-bg-subtle); }', css,
        )

    def test_invalid_value_marks_the_row(self):
        resp = self.client.post(self.url, {f'value_{self.metric.pk}': 'abc'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<tr class="table-danger">')
        self.assertContains(resp, 'Invalid number.')

    def test_saving_still_works_with_the_same_field_names(self):
        resp = self.client.post(self.url, {
            f'value_{self.metric.pk}': '88.5', f'notes_{self.metric.pk}': 'Busy week',
        })
        self.assertEqual(resp.status_code, 302)
        entry = ScorecardEntry.objects.get(metric=self.metric, period_start=_current_week_start())
        self.assertEqual(entry.value, Decimal('88.5'))
        self.assertEqual(entry.notes, 'Busy week')
