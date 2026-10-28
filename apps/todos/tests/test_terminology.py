from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.issues.models import Issue
from apps.rocks.models import Rock
from apps.todos.models import ToDo

ACME = 'acme.example.test'
GLOBEX = 'globex.example.test'
HOSTS = ['testserver', ACME, GLOBEX]

# Distinct from the shipped default ('Action') so the default-host test below
# can tell "customised" apart from "just happens to match the default."
ACTIONS = {'todo': 'Task', 'todos': 'Tasks'}


@override_settings(ALLOWED_HOSTS=HOSTS)
class ToDoTerminologyTest(TestCase):
    """The To-Dos pages use the organisation's own word for a To-Do.

    Acme calls them Tasks and is reached on its own hostname; Globex keeps
    the shipped defaults on another hostname. One user belongs to both.
    """

    def setUp(self):
        self.acme = Organization.objects.create(name='Acme', terminology=dict(ACTIONS))
        self.globex = Organization.objects.create(name='Globex')
        OrganizationDomain.objects.create(organization=self.acme, hostname=ACME)
        OrganizationDomain.objects.create(organization=self.globex, hostname=GLOBEX)
        self.acme_team = Team.objects.create(organization=self.acme, name='Leadership')
        self.globex_team = Team.objects.create(organization=self.globex, name='Leadership')
        self.user = User.objects.create_user(username='termsuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.acme)
        Membership.objects.create(user=self.user, organization=self.globex)
        self.user.profile.teams.add(self.acme_team, self.globex_team)
        self.client.force_login(self.user)

    def make_todo(self, title='Send proposal', team=None):
        return ToDo.objects.create(title=title, owner=self.user, team=team or self.acme_team)

    @staticmethod
    def message_texts(resp):
        return [str(message) for message in resp.context['messages']]

    # ── List page ────────────────────────────────────────────────────────────

    def test_list_page_uses_the_organisations_word(self):
        resp = self.client.get('/todos/', HTTP_HOST=ACME)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Tasks — Acme</title>', html=True)
        self.assertContains(resp, 'New Task')
        self.assertContains(resp, 'My Tasks')
        self.assertContains(resp, 'Team Tasks')
        self.assertContains(resp, 'No open Tasks')
        self.assertContains(resp, 'Create first Task')
        self.assertNotContains(resp, 'To-Do')

    def test_empty_states_use_the_organisations_word(self):
        resp = self.client.get('/todos/?status=complete', HTTP_HOST=ACME)
        self.assertContains(resp, 'No completed Tasks')
        self.assertContains(resp, 'Completed Tasks will appear here.')
        resp = self.client.get('/todos/?status=overdue', HTTP_HOST=ACME)
        self.assertContains(resp, 'No overdue Tasks')

    def test_escalate_menu_uses_the_organisations_word_for_an_issue(self):
        self.acme.terminology = {**ACTIONS, 'issue': 'Problem'}
        self.acme.save()
        todo = self.make_todo()
        ToDo.objects.filter(pk=todo.pk).update(created_at=timezone.now() - timedelta(days=20))
        resp = self.client.get('/todos/', HTTP_HOST=ACME)
        self.assertContains(resp, 'Escalate to Problem')
        self.assertNotContains(resp, 'Escalate to Issue')

    # ── Create ───────────────────────────────────────────────────────────────

    def test_create_page_uses_the_organisations_word(self):
        resp = self.client.get('/todos/new/', HTTP_HOST=ACME)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Create Task — Acme</title>', html=True)
        self.assertContains(resp, 'Create Task')
        self.assertNotContains(resp, 'To-Do')

    def test_create_page_labels_linked_rock_and_issue_with_the_organisations_words(self):
        self.acme.terminology = {
            **ACTIONS, 'rock': 'Priority', 'rocks': 'Priorities', 'issue': 'Problem',
        }
        self.acme.save()
        Rock.objects.create(
            title='Launch', owner=self.user, team=self.acme_team, quarter=1, year=2026,
            due_date=date.today(),
        )
        Issue.objects.create(
            title='Slow builds', originating_team=self.acme_team, created_by=self.user,
        )
        resp = self.client.get('/todos/new/', HTTP_HOST=ACME)
        self.assertContains(resp, 'Linked Priority')
        self.assertContains(resp, 'Linked Problem')
        self.assertNotContains(resp, 'Linked Rock')
        self.assertNotContains(resp, 'Linked Issue')

    def test_creating_one_reports_it_with_the_organisations_word(self):
        resp = self.client.post('/todos/new/', {
            'title': 'Send proposal',
            'description': '',
            'owner': self.user.pk,
            'due_date': (date.today() + timedelta(days=7)).isoformat(),
            'linked_rock': '',
            'linked_issue': '',
        }, HTTP_HOST=ACME, follow=True)
        self.assertRedirects(resp, '/todos/')
        self.assertIn('Task "Send proposal" created.', self.message_texts(resp))
        self.assertEqual(ToDo.objects.get(title='Send proposal').team, self.acme_team)

    # ── Update and delete ────────────────────────────────────────────────────

    def test_edit_page_and_update_message_use_the_organisations_word(self):
        todo = self.make_todo()
        resp = self.client.get(f'/todos/{todo.pk}/edit/', HTTP_HOST=ACME)
        self.assertContains(resp, '<title>Edit Task — Acme</title>', html=True)
        self.assertContains(resp, 'Edit Task')
        self.assertNotContains(resp, 'To-Do')

        resp = self.client.post(f'/todos/{todo.pk}/edit/', {
            'title': 'Send revised proposal',
            'description': '',
            'owner': self.user.pk,
            'due_date': todo.due_date.isoformat(),
            'linked_rock': '',
            'linked_issue': '',
        }, HTTP_HOST=ACME, follow=True)
        self.assertIn('Task "Send revised proposal" updated.', self.message_texts(resp))

    def test_delete_page_and_delete_message_use_the_organisations_word(self):
        self.acme.terminology = {**ACTIONS, 'rock': 'Priority', 'rocks': 'Priorities'}
        self.acme.save()
        rock = Rock.objects.create(
            title='Launch', owner=self.user, team=self.acme_team, quarter=1, year=2026,
            due_date=date.today(),
        )
        todo = self.make_todo()
        todo.linked_rock = rock
        todo.save()

        resp = self.client.get(f'/todos/{todo.pk}/delete/', HTTP_HOST=ACME)
        self.assertContains(resp, '<title>Delete Task — Acme</title>', html=True)
        self.assertContains(resp, 'Delete Task?')
        self.assertContains(resp, 'This Task is linked to Priority')
        self.assertContains(resp, 'The Priority will not be affected.')
        self.assertNotContains(resp, 'To-Do')
        self.assertNotContains(resp, 'Rock')

        resp = self.client.post(f'/todos/{todo.pk}/delete/', HTTP_HOST=ACME, follow=True)
        self.assertRedirects(resp, '/todos/')
        self.assertIn('Task "Send proposal" deleted.', self.message_texts(resp))
        self.assertFalse(ToDo.objects.filter(pk=todo.pk).exists())

    # ── Escalate ─────────────────────────────────────────────────────────────

    def test_escalating_reports_the_new_issue_with_the_organisations_word(self):
        self.acme.terminology = {**ACTIONS, 'issue': 'Problem', 'issues': 'Problems'}
        self.acme.save()
        todo = self.make_todo()

        resp = self.client.post(f'/todos/{todo.pk}/escalate/', HTTP_HOST=ACME, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Problem created from "Send proposal".', self.message_texts(resp))

        # What is stored on the Issue keeps the standard words: stored text is
        # not rewritten when an organisation renames things.
        todo.refresh_from_db()
        self.assertIn('overdue To-Do', todo.linked_issue.description)
        self.assertIn('overdue To-Do', todo.linked_issue.activity.first().notes)

    # ── Another organisation ─────────────────────────────────────────────────

    def test_other_organisations_host_keeps_the_default_words(self):
        resp = self.client.get('/todos/', HTTP_HOST=GLOBEX)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Actions — Globex</title>', html=True)
        self.assertContains(resp, 'New Action')
        self.assertContains(resp, 'My Actions')
        self.assertContains(resp, 'No open Actions')
        self.assertNotContains(resp, 'Tasks')
        self.assertNotContains(resp, 'New Task')

        resp = self.client.get('/todos/new/', HTTP_HOST=GLOBEX)
        self.assertContains(resp, 'Create Action')
        self.assertNotContains(resp, 'Create Task')
