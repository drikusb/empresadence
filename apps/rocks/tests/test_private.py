"""Private Rocks are seen only by their owner, their creator and the people on them (#77).

Every surface a Rock appears on is checked twice: a team-mate who is not on the
Rock sees nothing, not even a count, and one who has been added sees it.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.accounts.terminology import Terms
from apps.issues.forms import IssueForm
from apps.issues.models import Issue
from apps.meetings.models import Meeting
from apps.meetings.views import _build_runner_context
from apps.rocks.forms import RockForm
from apps.rocks.models import Rock, RockDependency, RockMilestone
from apps.todos.forms import ToDoForm
from apps.todos.models import ToDo

SECRET = 'Hire a new chief executive'


class PrivateRockTestBase(TestCase):
    """One team: the owner of a private Rock, a colleague it is shared with, a
    team-mate it is not shared with, and an organisation admin who is not on it."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Private Org')
        cls.team = Team.objects.create(organization=cls.org, name='Leadership')

        def user(name, role=Membership.ROLE_MEMBER):
            u = User.objects.create_user(username=name, password='pw')
            Membership.objects.create(user=u, organization=cls.org, role=role)
            u.profile.teams.add(cls.team)
            return u

        cls.owner = user('owner')
        cls.colleague = user('colleague')
        cls.teammate = user('teammate')
        cls.admin = user('admin', Membership.ROLE_ADMIN)

        cls.quarter, cls.year = Rock.current_quarter(), Rock.current_year()
        cls.rock = Rock.objects.create(
            title=SECRET, description='Shortlist by June', owner=cls.owner, team=cls.team,
            created_by=cls.owner, quarter=cls.quarter, year=cls.year,
            due_date=Rock.quarter_end_date(cls.quarter, cls.year),
            status=Rock.STATUS_OFF_TRACK, is_private=True,
        )
        cls.rock.shared_with.add(cls.colleague)
        cls.public = Rock.objects.create(
            title='Open a second office', owner=cls.teammate, team=cls.team,
            quarter=cls.quarter, year=cls.year,
            due_date=Rock.quarter_end_date(cls.quarter, cls.year),
        )

    def assertHidden(self, resp):
        self.assertNotContains(resp, SECRET)

    def assertShown(self, resp):
        self.assertContains(resp, SECRET)


class VisibleToTest(PrivateRockTestBase):
    def test_owner_creator_and_shared_with_see_it(self):
        for user in (self.owner, self.colleague):
            self.assertIn(self.rock, Rock.objects.visible_to(user))
            self.assertTrue(self.rock.is_visible_to(user))

    def test_creator_who_is_not_the_owner_sees_it(self):
        self.rock.created_by = self.teammate
        self.rock.save()
        self.assertIn(self.rock, Rock.objects.visible_to(self.teammate))

    def test_teammate_and_admin_do_not(self):
        for user in (self.teammate, self.admin):
            self.assertNotIn(self.rock, Rock.objects.visible_to(user))
            self.assertFalse(self.rock.is_visible_to(user))
            self.assertIn(self.public, Rock.objects.visible_to(user))

    def test_no_duplicates_when_shared_with_several_people(self):
        self.rock.shared_with.add(self.teammate, self.admin)
        self.assertEqual(
            list(Rock.objects.visible_to(self.owner).filter(pk=self.rock.pk)), [self.rock]
        )


class PrivateRockPagesTest(PrivateRockTestBase):
    def test_list(self):
        self.client.force_login(self.teammate)
        self.assertHidden(self.client.get('/rocks/'))
        self.assertHidden(self.client.get('/rocks/', {'scope': 'all'}))
        self.client.force_login(self.colleague)
        resp = self.client.get('/rocks/')
        self.assertShown(resp)
        self.assertContains(resp, 'bi-lock')

    def test_archive_and_csv(self):
        params = {'quarter': self.quarter, 'year': self.year}
        self.client.force_login(self.admin)
        self.assertHidden(self.client.get('/rocks/archive/', params))
        self.assertHidden(self.client.get('/rocks/export/', params))
        self.client.force_login(self.colleague)
        self.assertShown(self.client.get('/rocks/archive/', params))
        self.assertShown(self.client.get('/rocks/export/', params))

    def test_detail_edit_and_delete_are_404_not_403(self):
        self.client.force_login(self.admin)
        for url in (f'/rocks/{self.rock.pk}/', f'/rocks/{self.rock.pk}/edit/',
                    f'/rocks/{self.rock.pk}/delete/'):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.client.force_login(self.colleague)
        resp = self.client.get(f'/rocks/{self.rock.pk}/')
        self.assertShown(resp)
        self.assertContains(resp, 'shared with colleague')

    def test_actions_on_the_rock_are_404(self):
        milestone = RockMilestone.objects.create(rock=self.rock, title='Brief the board')
        dependency = RockDependency.objects.create(rock=self.rock, depends_on_rock=self.public)
        issue = Issue.objects.create(title='Budget', originating_team=self.team)
        pk = self.rock.pk
        posts = [
            (f'/rocks/{pk}/status/', {'status': Rock.STATUS_ON_TRACK}),
            (f'/rocks/{pk}/checkins/add/', {'confidence': Rock.STATUS_ON_TRACK}),
            (f'/rocks/{pk}/milestones/add/', {'title': 'x'}),
            (f'/rocks/{pk}/dependency/add/', {'depends_on_rock': self.public.pk}),
            (f'/rocks/{pk}/issues/link/', {'issue_id': issue.pk}),
            (f'/rocks/{pk}/issues/unlink/', {'issue_id': issue.pk}),
            (f'/rocks/milestones/{milestone.pk}/toggle/', {}),
            (f'/rocks/milestones/{milestone.pk}/delete/', {}),
            (f'/rocks/dependency/{dependency.pk}/remove/', {}),
        ]
        self.client.force_login(self.admin)
        for url, data in posts:
            self.assertEqual(self.client.post(url, data).status_code, 404, url)
        self.assertEqual(self.client.get(f'/rocks/milestones/{milestone.pk}/edit/').status_code, 404)
        self.rock.refresh_from_db()
        self.assertEqual(self.rock.status, Rock.STATUS_OFF_TRACK)
        self.assertTrue(RockMilestone.objects.filter(pk=milestone.pk).exists())

    def test_dashboard_counts(self):
        self.client.force_login(self.teammate)
        resp = self.client.get('/')
        self.assertEqual(resp.context['active_rocks'], 1)
        self.assertEqual(resp.context['off_track_rocks'], 0)
        self.client.force_login(self.owner)
        resp = self.client.get('/')
        self.assertEqual(resp.context['active_rocks'], 2)
        self.assertEqual(resp.context['off_track_rocks'], 1)

    def test_search(self):
        self.client.force_login(self.teammate)
        self.assertHidden(self.client.get('/search/', {'q': 'chief executive'}))
        self.client.force_login(self.colleague)
        self.assertShown(self.client.get('/search/', {'q': 'chief executive'}))

    def test_team_page_tile_count(self):
        self.client.force_login(self.admin)
        tiles = self.client.get(f'/teams/{self.team.pk}/').context['tiles']
        self.assertEqual(tiles[0]['count'], 1)

    def test_other_team_hint_does_not_count_it(self):
        other = Team.objects.create(organization=self.org, name='Operations')
        for user in (self.owner, self.teammate):
            user.profile.teams.add(other)
        self.rock.team = other
        self.rock.save()
        self.client.force_login(self.teammate)
        self.client.post(f'/teams/{self.team.pk}/switch/', {'next': '/rocks/'})
        resp = self.client.get('/rocks/')
        self.assertEqual(resp.context['other_rocks_total'], 0)
        self.client.force_login(self.owner)
        self.client.post(f'/teams/{self.team.pk}/switch/', {'next': '/rocks/'})
        self.assertEqual(self.client.get('/rocks/').context['other_rocks_total'], 1)

    def test_child_rocks_and_dependencies_on_another_rocks_page(self):
        child = self.rock
        child.parent_rock = self.public
        child.save()
        RockDependency.objects.create(rock=child, depends_on_rock=self.public)
        self.client.force_login(self.teammate)
        resp = self.client.get(f'/rocks/{self.public.pk}/')
        self.assertHidden(resp)
        self.assertEqual(list(resp.context['child_rocks']), [])
        self.assertEqual(list(resp.context['dependents']), [])

    def test_private_parent_is_not_named(self):
        Rock.objects.filter(pk=self.public.pk).update(parent_rock=self.rock)
        self.client.force_login(self.teammate)
        resp = self.client.get(f'/rocks/{self.public.pk}/')
        self.assertHidden(resp)
        self.client.force_login(self.owner)
        self.assertShown(self.client.get(f'/rocks/{self.public.pk}/'))

    def test_linked_todo_and_issue(self):
        todo = ToDo.objects.create(title='Call the agency', owner=self.teammate, team=self.team,
                                   linked_rock=self.rock)
        issue = Issue.objects.create(title='Budget', originating_team=self.team)
        issue.linked_rocks.add(self.rock)
        self.client.force_login(self.teammate)
        resp = self.client.get('/todos/')
        self.assertContains(resp, todo.title)
        self.assertHidden(resp)
        self.assertHidden(self.client.get(f'/todos/{todo.pk}/delete/'))
        self.assertHidden(self.client.get(f'/issues/{issue.pk}/'))
        self.client.force_login(self.colleague)
        self.assertShown(self.client.get(f'/issues/{issue.pk}/'))

    def test_meeting_runner(self):
        meeting = Meeting.objects.create(team=self.team, scheduled_date=date.today(),
                                         created_by=self.admin)
        terms = Terms()
        rocks = _build_runner_context(meeting, self.teammate, terms)['rocks']
        self.assertNotIn(self.rock, rocks)
        self.assertIn(self.public, rocks)
        self.assertIn(self.rock, _build_runner_context(meeting, self.owner, terms)['rocks'])


class PrivateRockFormsTest(PrivateRockTestBase):
    def rock_data(self, **overrides):
        data = {
            'title': 'A Rock', 'description': '', 'owner': self.owner.pk,
            'quarter': self.quarter, 'year': self.year,
            'due_date': Rock.quarter_end_date(self.quarter, self.year).isoformat(),
            'parent_rock': '',
        }
        data.update(overrides)
        return data

    def test_create_a_private_rock_shared_with_someone(self):
        self.client.force_login(self.owner)
        self.client.post('/rocks/new/', self.rock_data(
            title='Restructure', is_private='on', shared_with=[self.colleague.pk],
        ))
        rock = Rock.objects.get(title='Restructure')
        self.assertTrue(rock.is_private)
        self.assertEqual(list(rock.shared_with.all()), [self.colleague])

    def test_private_and_company_wide_together_are_refused(self):
        form = RockForm(self.rock_data(is_private='on', is_company_rock='on'),
                        team=self.team, user=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('is_private', form.errors)

    def test_an_existing_company_rock_cannot_be_made_private_by_a_member(self):
        self.public.is_company_rock = True
        self.public.save()
        form = RockForm(self.rock_data(is_private='on'), instance=self.public,
                        team=self.team, user=self.teammate)
        self.assertFalse(form.is_valid())

    def test_choice_lists_leave_it_out(self):
        rock_form = RockForm(team=self.team, user=self.teammate)
        todo_form = ToDoForm(team=self.team, user=self.teammate)
        issue_form = IssueForm(team=self.team, user=self.teammate)
        for field in (rock_form.fields['parent_rock'], todo_form.fields['linked_rock'],
                      issue_form.fields['linked_rocks']):
            self.assertNotIn(self.rock, field.queryset)
        self.assertIn(self.rock, ToDoForm(team=self.team, user=self.colleague).fields['linked_rock'].queryset)

    def test_dependency_choices_leave_it_out(self):
        self.client.force_login(self.teammate)
        form = self.client.get(f'/rocks/{self.public.pk}/').context['dependency_form']
        self.assertNotIn(self.rock, form.fields['depends_on_rock'].queryset)

    def test_editing_keeps_a_link_the_editor_cannot_see(self):
        todo = ToDo.objects.create(title='Call the agency', owner=self.teammate, team=self.team,
                                   linked_rock=self.rock)
        form = ToDoForm(instance=todo, team=self.team, user=self.teammate)
        labels = dict(form.fields['linked_rock'].choices)
        self.assertNotIn(SECRET, labels.values())
        self.assertIn('A private Priority', labels.values())

        self.client.force_login(self.teammate)
        self.client.post(f'/todos/{todo.pk}/edit/', {
            'title': 'Call the agency again', 'description': '', 'owner': self.teammate.pk,
            'due_date': date.today().isoformat(), 'linked_rock': self.rock.pk, 'linked_issue': '',
        })
        todo.refresh_from_db()
        self.assertEqual(todo.title, 'Call the agency again')
        self.assertEqual(todo.linked_rock, self.rock)

    def test_issue_edit_keeps_a_link_the_editor_cannot_see(self):
        issue = Issue.objects.create(title='Budget', originating_team=self.team)
        issue.linked_rocks.add(self.rock)
        self.client.force_login(self.teammate)
        resp = self.client.get(f'/issues/{issue.pk}/edit/')
        self.assertHidden(resp)
        self.assertContains(resp, 'A private Priority')


class PrivateRockElsewhereTest(PrivateRockTestBase):
    def test_vision_page_never_shows_a_private_rock(self):
        Rock.objects.filter(pk=self.rock.pk).update(is_company_rock=True)
        self.client.force_login(self.owner)
        self.assertHidden(self.client.get('/vision/'))

    def test_off_track_alert_goes_only_to_the_owner(self):
        from django.core import mail
        for user in (self.owner, self.colleague, self.teammate, self.admin):
            user.email = f'{user.username}@example.com'
            user.save()
        self.rock.status = Rock.STATUS_ON_TRACK
        self.rock.save()
        self.client.force_login(self.owner)
        self.client.post(f'/rocks/{self.rock.pk}/status/', {'status': Rock.STATUS_OFF_TRACK})
        self.assertEqual([m.to for m in mail.outbox], [['owner@example.com']])
