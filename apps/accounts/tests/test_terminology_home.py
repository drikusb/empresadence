from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.meetings.models import Meeting
from apps.rocks.models import Rock
from apps.todos.models import ToDo

HOSTS = ['testserver', 'mercury.example.test', 'silavapi.example.test']
MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

RENAMED = {
    'meeting': 'Weekly Meeting', 'meetings': 'Weekly Meetings',
    'headline': 'Update', 'headlines': 'Updates',
    'seat': 'Role', 'seats': 'Roles',
    'todo': 'Action', 'todos': 'Actions',
    # Distinct from the shipped default ('Priority') so the default-host test
    # below can tell "customised" apart from "just happens to match the default."
    'rock': 'Objective', 'rocks': 'Objectives',
}


@override_settings(ALLOWED_HOSTS=HOSTS)
class HomeAndSearchTerminologyTest(TestCase):
    """The dashboard cards and search page use the organisation's words for the modules."""

    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', terminology=RENAMED)
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        self.silavapi = Organization.objects.create(name='Silavapi Org')
        OrganizationDomain.objects.create(organization=self.silavapi, hostname=SILAVAPI)
        self.user = User.objects.create_user(username='homeuser', password='pw')
        self.mercury_team = Team.objects.create(organization=self.mercury, name='Mercury Team')
        self.silavapi_team = Team.objects.create(organization=self.silavapi, name='Silavapi Team')
        for org, team in ((self.mercury, self.mercury_team), (self.silavapi, self.silavapi_team)):
            Membership.objects.create(user=self.user, organization=org)
            self.user.profile.teams.add(team)
        self.client.force_login(self.user)

    def test_dashboard_cards_use_the_organisations_words(self):
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        for label in [
            'Weekly Meetings</h5>', 'Objectives</h5>', 'Actions</h5>',
            'View Objectives', 'View Actions', 'Open actions',
            '1-Year Plan, Objectives, and Blockers List.',
        ]:
            with self.subTest(label=label):
                self.assertContains(resp, label)
        for label in [
            'Level 10 Meetings</h5>', 'Rocks</h5>', 'To-Dos</h5>', 'View Rocks', 'View To-Dos',
            'Plan, Rocks, and Issues List.',
        ]:
            with self.subTest(label=label):
                self.assertNotContains(resp, label)

    def test_meeting_card_without_a_meeting_uses_the_organisations_words(self):
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'No upcoming weekly meetings scheduled.')
        self.assertContains(resp, 'bi-plus me-1"></i>Schedule Weekly Meeting')
        self.assertNotContains(resp, 'No upcoming meetings scheduled.')
        self.assertNotContains(resp, 'Schedule Meeting')

    def test_meeting_card_with_a_scheduled_meeting_uses_the_organisations_words(self):
        Meeting.objects.create(team=self.mercury_team, scheduled_date=date.today())
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Next weekly meeting')
        self.assertContains(resp, 'bi-calendar-check me-1"></i>View Weekly Meeting')
        self.assertNotContains(resp, 'Next meeting')
        self.assertNotContains(resp, 'View Meeting')

    def test_dashboard_keeps_the_descriptive_subtitles(self):
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        for text in [
            'Quarterly priorities', 'Weekly 90-minute rhythm', 'Problem, Solve, Resolve',
            'Weekly action items', 'Right people, right seats', 'Long-term vision and plan',
        ]:
            with self.subTest(text=text):
                self.assertContains(resp, text)

    def test_dashboard_shows_the_renamed_segment_of_an_active_meeting(self):
        meeting = Meeting.objects.create(team=self.mercury_team, scheduled_date=date.today())
        meeting.start()
        meeting.current_segment = 2
        meeting.save(update_fields=['current_segment'])
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Segment: Objective Review')
        self.assertContains(resp, 'bi-play-fill me-1"></i>Rejoin Weekly Meeting')
        self.assertNotContains(resp, 'Rock Review')
        self.assertNotContains(resp, 'Rejoin Meeting')

    def test_search_placeholder_and_headings_use_the_organisations_words(self):
        Rock.objects.create(
            title='Mercury launch', owner=self.user, team=self.mercury_team,
            quarter=1, year=2026, due_date=date(2026, 3, 31),
        )
        ToDo.objects.create(title='Mercury follow-up', owner=self.user, team=self.mercury_team)
        resp = self.client.get('/search/?q=Mercury', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'placeholder="Search objectives, blockers, actions…"')
        self.assertContains(resp, 'Objectives (1)')
        self.assertContains(resp, 'Actions (1)')
        self.assertNotContains(resp, 'Rocks (')
        self.assertNotContains(resp, 'To-Dos (')

    def test_default_host_shows_the_generic_words(self):
        resp = self.client.get('/', HTTP_HOST=SILAVAPI)
        for label in [
            'Weekly Meetings</h5>', 'Priorities</h5>', 'Actions</h5>',
            'View Priorities', 'View Actions',
            'No upcoming weekly meetings scheduled.', 'Schedule Weekly Meeting',
            '1-Year Plan, Priorities, and Blockers List.',
        ]:
            with self.subTest(label=label):
                self.assertContains(resp, label)
        self.assertNotContains(resp, 'Objective')

        Rock.objects.create(
            title='Silavapi launch', owner=self.user, team=self.silavapi_team,
            quarter=1, year=2026, due_date=date(2026, 3, 31),
        )
        resp = self.client.get('/search/?q=Silavapi', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'placeholder="Search priorities, blockers, actions…"')
        self.assertContains(resp, 'Priorities (1)')
