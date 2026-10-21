from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.issues.models import Issue
from apps.rocks.models import Rock
from apps.todos.models import ToDo

INVALID_CHOICE = 'Select a valid choice. That choice is not one of the available choices.'


class ToDoTeamPickerTest(TestCase):
    """The Team select on the To-Do form is a real picker (#12)."""

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

        self.due = (date.today() + timedelta(days=7)).isoformat()

    def _activate(self, user, team):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.pk
        session['active_team_id'] = team.pk
        session.save()

    def _todo(self, team, title='Existing To-Do', **extra):
        return ToDo.objects.create(
            title=title, owner=self.member, team=team, due_date=date.today(), **extra,
        )

    def _post_data(self, **overrides):
        data = {
            'title': 'Moved To-Do',
            'description': '',
            'owner': self.member.pk,
            'team': self.alpha.pk,
            'due_date': self.due,
            'linked_rock': '',
            'linked_issue': '',
        }
        data.update(overrides)
        return data

    def _team_choices(self, resp):
        return list(resp.context['form'].fields['team'].queryset)

    # -- choices --------------------------------------------------------------

    def test_member_chooses_from_their_own_teams_in_the_organisation(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/todos/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta])

    def test_admin_chooses_from_every_team_in_the_organisation(self):
        self._activate(self.admin, self.alpha)
        resp = self.client.get('/todos/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta, self.gamma])

    def test_select_has_no_placeholder_option(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/todos/new/')
        self.assertNotContains(resp, '— Select team —')
        self.assertIsNone(resp.context['form'].fields['team'].empty_label)

    # -- defaults -------------------------------------------------------------

    def test_create_defaults_to_the_active_team(self):
        self._activate(self.member, self.beta)
        resp = self.client.get('/todos/new/')
        self.assertEqual(resp.context['form']['team'].value(), self.beta.pk)

    def test_edit_defaults_to_the_todos_current_team(self):
        todo = self._todo(self.beta)
        self._activate(self.member, self.alpha)
        resp = self.client.get(f'/todos/{todo.pk}/edit/')
        self.assertEqual(resp.context['form']['team'].value(), self.beta.pk)

    # -- saving ---------------------------------------------------------------

    def test_creating_with_another_team_saves_to_that_team(self):
        self._activate(self.member, self.alpha)
        self.client.post('/todos/new/', self._post_data(team=self.beta.pk))
        todo = ToDo.objects.get(title='Moved To-Do')
        self.assertEqual(todo.team, self.beta)
        self._activate(self.member, self.beta)
        self.assertContains(self.client.get('/todos/'), 'Moved To-Do')

    def test_editing_moves_the_todo_to_the_chosen_team(self):
        todo = self._todo(self.alpha, title='Moved To-Do')
        self._activate(self.member, self.alpha)
        self.client.post(f'/todos/{todo.pk}/edit/', self._post_data(team=self.beta.pk))
        todo.refresh_from_db()
        self.assertEqual(todo.team, self.beta)
        self.assertNotIn(todo, self.client.get('/todos/').context['todos'])
        self._activate(self.member, self.beta)
        self.assertContains(self.client.get('/todos/'), 'Moved To-Do')

    # -- validation -----------------------------------------------------------

    def test_team_outside_the_allowed_set_is_rejected(self):
        self._activate(self.member, self.alpha)
        resp = self.client.post('/todos/new/', self._post_data(team=self.gamma.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'team', INVALID_CHOICE)
        self.assertFalse(ToDo.objects.filter(title='Moved To-Do').exists())

    def test_owner_not_on_the_chosen_team_gives_a_field_error(self):
        self._activate(self.member, self.alpha)
        resp = self.client.post('/todos/new/', self._post_data(
            owner=self.admin.pk, team=self.beta.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'owner', 'That person is not a member of Beta.'
        )

    def test_linked_rock_on_the_old_team_gives_a_field_error(self):
        rock = Rock.objects.create(
            title='Alpha Rock', owner=self.member, team=self.alpha,
            quarter=1, year=2026, due_date=date(2026, 3, 31),
        )
        todo = self._todo(self.alpha, title='Moved To-Do', linked_rock=rock)
        self._activate(self.member, self.alpha)
        resp = self.client.post(f'/todos/{todo.pk}/edit/', self._post_data(
            team=self.beta.pk, linked_rock=rock.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'linked_rock', 'The linked Rock must be on Beta.'
        )
        todo.refresh_from_db()
        self.assertEqual(todo.team, self.alpha)

    def test_linked_issue_on_the_old_team_gives_a_field_error(self):
        issue = Issue.objects.create(
            title='Alpha Issue', originating_team=self.alpha, created_by=self.member,
        )
        todo = self._todo(self.alpha, title='Moved To-Do', linked_issue=issue)
        self._activate(self.member, self.alpha)
        resp = self.client.post(f'/todos/{todo.pk}/edit/', self._post_data(
            team=self.beta.pk, linked_issue=issue.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'linked_issue',
            'The linked Issue must have been raised by Beta.',
        )
        todo.refresh_from_db()
        self.assertEqual(todo.team, self.alpha)
