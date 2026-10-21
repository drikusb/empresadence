from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.rocks.models import Rock

INVALID_CHOICE = 'Select a valid choice. That choice is not one of the available choices.'


class RockTeamPickerTest(TestCase):
    """The Team select on the Rock form is a real picker (#12)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Picker Org')
        self.alpha = Team.objects.create(organization=self.org, name='Alpha')
        self.beta = Team.objects.create(organization=self.org, name='Beta')
        self.gamma = Team.objects.create(organization=self.org, name='Gamma')
        other_org = Organization.objects.create(name='Other Org')
        self.elsewhere = Team.objects.create(organization=other_org, name='Elsewhere')

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

    def _rock(self, team, title='Existing Rock', **extra):
        return Rock.objects.create(
            title=title, owner=self.member, team=team,
            quarter=1, year=2026, due_date=date(2026, 3, 31), **extra,
        )

    def _post_data(self, **overrides):
        data = {
            'title': 'Moved Rock',
            'description': '',
            'owner': self.member.pk,
            'team': self.alpha.pk,
            'quarter': 1,
            'year': 2026,
            'due_date': '2026-03-31',
            'parent_rock': '',
        }
        data.update(overrides)
        return data

    def _team_choices(self, resp):
        return list(resp.context['form'].fields['team'].queryset)

    # -- choices --------------------------------------------------------------

    def test_member_chooses_from_their_own_teams_in_the_organisation(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/rocks/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta])

    def test_admin_chooses_from_every_team_in_the_organisation(self):
        self._activate(self.admin, self.alpha)
        resp = self.client.get('/rocks/new/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta, self.gamma])

    def test_select_has_no_placeholder_option(self):
        self._activate(self.member, self.alpha)
        resp = self.client.get('/rocks/new/')
        self.assertNotContains(resp, '— Select team —')
        self.assertIsNone(resp.context['form'].fields['team'].empty_label)

    def test_editing_keeps_a_team_the_editor_is_not_on_in_the_choices(self):
        rock = self._rock(self.gamma)
        self._activate(self.member, self.alpha)
        resp = self.client.get(f'/rocks/{rock.pk}/edit/')
        self.assertEqual(self._team_choices(resp), [self.alpha, self.beta, self.gamma])

    # -- defaults -------------------------------------------------------------

    def test_create_defaults_to_the_active_team(self):
        self._activate(self.member, self.beta)
        resp = self.client.get('/rocks/new/')
        self.assertEqual(resp.context['form']['team'].value(), self.beta.pk)

    def test_edit_defaults_to_the_rocks_current_team(self):
        rock = self._rock(self.beta)
        self._activate(self.member, self.alpha)
        resp = self.client.get(f'/rocks/{rock.pk}/edit/')
        self.assertEqual(resp.context['form']['team'].value(), self.beta.pk)

    # -- saving ---------------------------------------------------------------

    def test_creating_with_another_team_saves_to_that_team(self):
        self._activate(self.member, self.alpha)
        self.client.post('/rocks/new/', self._post_data(team=self.beta.pk))
        rock = Rock.objects.get(title='Moved Rock')
        self.assertEqual(rock.team, self.beta)
        self._activate(self.member, self.beta)
        resp = self.client.get('/rocks/?quarter=1&year=2026')
        self.assertContains(resp, 'Moved Rock')

    def test_editing_moves_the_rock_to_the_chosen_team(self):
        rock = self._rock(self.alpha, title='Moved Rock')
        self._activate(self.member, self.alpha)
        self.client.post(f'/rocks/{rock.pk}/edit/', self._post_data(team=self.beta.pk))
        rock.refresh_from_db()
        self.assertEqual(rock.team, self.beta)
        resp = self.client.get('/rocks/?quarter=1&year=2026')
        self.assertNotIn(rock, resp.context['rocks'])
        self._activate(self.member, self.beta)
        resp = self.client.get('/rocks/?quarter=1&year=2026')
        self.assertContains(resp, 'Moved Rock')

    # -- validation -----------------------------------------------------------

    def test_team_outside_the_allowed_set_is_rejected(self):
        self._activate(self.member, self.alpha)
        resp = self.client.post('/rocks/new/', self._post_data(team=self.gamma.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'team', INVALID_CHOICE)
        self.assertFalse(Rock.objects.filter(title='Moved Rock').exists())

    def test_team_in_another_organisation_is_rejected_even_for_an_admin(self):
        self._activate(self.admin, self.alpha)
        resp = self.client.post('/rocks/new/', self._post_data(
            owner=self.admin.pk, team=self.elsewhere.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'team', INVALID_CHOICE)
        self.assertFalse(Rock.objects.filter(title='Moved Rock').exists())

    def test_owner_not_on_the_chosen_team_gives_a_field_error(self):
        self._activate(self.member, self.alpha)
        resp = self.client.post('/rocks/new/', self._post_data(
            owner=self.admin.pk, team=self.beta.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'owner', 'That person is not a member of Beta.'
        )
        # The owner choices now follow the chosen team, so the user can pick again.
        self.assertEqual(
            list(resp.context['form'].fields['owner'].queryset), [self.member]
        )

    def test_parent_rock_on_the_old_team_gives_a_field_error(self):
        parent = self._rock(self.alpha, title='Alpha Parent')
        rock = self._rock(self.alpha, title='Moved Rock', parent_rock=parent)
        self._activate(self.member, self.alpha)
        resp = self.client.post(f'/rocks/{rock.pk}/edit/', self._post_data(
            team=self.beta.pk, parent_rock=parent.pk,
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'], 'parent_rock', 'The parent Rock must be on Beta.'
        )
        rock.refresh_from_db()
        self.assertEqual(rock.team, self.alpha)
