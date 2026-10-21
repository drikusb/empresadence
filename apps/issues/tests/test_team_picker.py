from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.issues.models import Issue, IssueActivity
from apps.rocks.models import Rock

INVALID_CHOICE = 'Select a valid choice. That choice is not one of the available choices.'


class IssueTeamPickerTest(TestCase):
    """The Originating Team select on the Issue form is a real picker (#12)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Picker Org')
        self.alpha = Team.objects.create(organization=self.org, name='Alpha')
        self.beta = Team.objects.create(organization=self.org, name='Beta')
        self.gamma = Team.objects.create(organization=self.org, name='Gamma')

        self.member = User.objects.create_user(username='pickmember', password='pw')
        Membership.objects.create(user=self.member, organization=self.org)
        self.member.profile.teams.add(self.alpha, self.beta)

        self.admin = User.objects.create_user(username='pickadmin', password='pw')
        Membership.objects.create(
            user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN
        )
        self.admin.profile.teams.add(self.alpha)

    def _activate(self, user, team):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.pk
        session['active_team_id'] = team.pk
        session.save()

    def _issue(self, team, title='Existing Issue'):
        return Issue.objects.create(title=title, originating_team=team, created_by=self.member)

    def _post_data(self, **overrides):
        data = {
            'title': 'Moved Issue',
            'description': '',
            'issue_type': Issue.TYPE_SHORT_TERM,
            'originating_team': self.alpha.pk,
            'delegated_to_team': '',
            'linked_rocks': [],
            'target_quarter': '',
            'target_year': '',
        }
        data.update(overrides)
        return data

    def _team_choices(self, resp):
        return list(resp.context['form'].fields['originating_team'].queryset)

    # -- choices --------------------------------------------------------------

    def test_member_chooses_from_their_own_teams_in_the_organisation(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/issues/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta])

    def test_admin_chooses_from_every_team_in_the_organisation(self):
        self._activate(self.admin, self.alpha)
        resp = self.client.get('/issues/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta, self.gamma])

    def test_select_has_no_placeholder_option(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/issues/new/')
        self.assertNotContains(resp, '— Select team —')
        self.assertNotContains(resp, 'Cannot be changed later')
        self.assertIsNone(resp.context['form'].fields['originating_team'].empty_label)

    # -- defaults -------------------------------------------------------------

    def test_create_defaults_to_the_active_team(self):
        self._activate(self.member, self.beta)
        resp = self.client.get('/issues/new/')
        self.assertEqual(resp.context['form']['originating_team'].value(), self.beta.pk)

    def test_edit_defaults_to_the_issues_current_team(self):
        issue = self._issue(self.beta)
        self._activate(self.member, self.alpha)
        resp = self.client.get(f'/issues/{issue.pk}/edit/')
        self.assertEqual(resp.context['form']['originating_team'].value(), self.beta.pk)

    # -- saving ---------------------------------------------------------------

    def test_creating_with_another_team_saves_to_that_team(self):
        self._activate(self.member, self.alpha)
        self.client.post('/issues/new/', self._post_data(originating_team=self.beta.pk))
        issue = Issue.objects.get(title='Moved Issue')
        self.assertEqual(issue.originating_team, self.beta)
        self._activate(self.member, self.beta)
        self.assertContains(self.client.get('/issues/'), 'Moved Issue')

    def test_editing_moves_the_issue_and_records_the_move(self):
        issue = self._issue(self.alpha, title='Moved Issue')
        self._activate(self.member, self.alpha)
        self.client.post(
            f'/issues/{issue.pk}/edit/', self._post_data(originating_team=self.beta.pk)
        )
        issue.refresh_from_db()
        self.assertEqual(issue.originating_team, self.beta)
        activity = IssueActivity.objects.get(issue=issue)
        self.assertEqual(activity.action, IssueActivity.ACTION_STATUS_CHANGED)
        self.assertEqual(activity.actor, self.member)
        self.assertEqual(activity.notes, 'Moved from Alpha to Beta.')
        self.assertNotIn(issue, self.client.get('/issues/').context['issues'])
        self._activate(self.member, self.beta)
        self.assertContains(self.client.get('/issues/'), 'Moved Issue')

    def test_editing_without_changing_team_records_nothing(self):
        issue = self._issue(self.alpha, title='Moved Issue')
        self._activate(self.member, self.alpha)
        self.client.post(f'/issues/{issue.pk}/edit/', self._post_data(title='Renamed Issue'))
        issue.refresh_from_db()
        self.assertEqual(issue.title, 'Renamed Issue')
        self.assertFalse(IssueActivity.objects.filter(issue=issue).exists())

    # -- validation -----------------------------------------------------------

    def test_team_outside_the_allowed_set_is_rejected(self):
        self._activate(self.member, self.alpha)
        resp = self.client.post(
            '/issues/new/', self._post_data(originating_team=self.gamma.pk)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'originating_team', INVALID_CHOICE)
        self.assertFalse(Issue.objects.filter(title='Moved Issue').exists())

    def test_linked_rock_on_the_old_team_gives_a_field_error(self):
        rock = Rock.objects.create(
            title='Alpha Rock', owner=self.member, team=self.alpha,
            quarter=1, year=2026, due_date=date(2026, 3, 31),
        )
        issue = self._issue(self.alpha, title='Moved Issue')
        issue.linked_rocks.add(rock)
        self._activate(self.member, self.alpha)
        resp = self.client.post(f'/issues/{issue.pk}/edit/', self._post_data(
            originating_team=self.beta.pk, linked_rocks=[rock.pk],
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'linked_rocks', 'Linked Rocks must be on Beta.'
        )
        issue.refresh_from_db()
        self.assertEqual(issue.originating_team, self.alpha)
