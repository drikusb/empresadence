from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.meetings.models import Meeting
from apps.notifications.emails import (
    send_meeting_reminder,
    send_overdue_todo_digest,
    send_rock_off_track_alert,
)
from apps.rocks.models import Rock
from apps.todos.models import ToDo

RENAMED = {
    'meeting': 'Weekly Meeting', 'meetings': 'Weekly Meetings',
    'todo': 'Action', 'todos': 'Actions',
    'rock': 'Priority', 'rocks': 'Priorities',
}


@override_settings(DEFAULT_BRAND_NAME='EOS App')
class TerminologyEmailTest(TestCase):
    """Email subjects and bodies use the organisation's own words for the modules."""

    def setUp(self):
        self.user = User.objects.create_user(username='mailee', email='mailee@example.com', password='pw')
        self.mercury = Organization.objects.create(
            name='Mercury Org', display_name='Mercury Consortium', terminology=RENAMED,
        )
        OrganizationDomain.objects.create(organization=self.mercury, hostname='mercury.example.test')
        self.mercury_team = Team.objects.create(organization=self.mercury, name='Mercury Team')
        self.plain = Organization.objects.create(name='Plain Org')
        self.plain_team = Team.objects.create(organization=self.plain, name='Plain Team')
        for org in (self.mercury, self.plain):
            Membership.objects.create(user=self.user, organization=org)

    def todo(self, team, title):
        return ToDo.objects.create(
            title=title, owner=self.user, team=team, due_date=date.today() - timedelta(days=1),
        )

    def rock(self, team, title):
        return Rock.objects.create(
            title=title, owner=self.user, team=team,
            quarter=1, year=2026, due_date=date(2026, 3, 31), status=Rock.STATUS_OFF_TRACK,
        )

    def test_overdue_digest_uses_the_organisations_todo_word(self):
        send_overdue_todo_digest(self.user, [self.todo(self.mercury_team, 'Late')], organization=self.mercury)
        message = mail.outbox[0]
        self.assertEqual(message.subject, '1 overdue Action — Mercury Consortium')
        self.assertIn('You have 1 overdue Action:', message.body)
        self.assertIn('View your Actions:', message.body)
        self.assertNotIn('To-Do', message.body)

    def test_overdue_digest_pluralises_the_organisations_word(self):
        todos = [self.todo(self.mercury_team, 'Late one'), self.todo(self.mercury_team, 'Late two')]
        send_overdue_todo_digest(self.user, todos, organization=self.mercury)
        message = mail.outbox[0]
        self.assertEqual(message.subject, '2 overdue Actions — Mercury Consortium')
        self.assertIn('You have 2 overdue Actions:', message.body)

    def test_meeting_reminder_uses_the_organisations_meeting_word(self):
        meeting = Meeting.objects.create(team=self.mercury_team, scheduled_date=date.today())
        send_meeting_reminder(self.user, meeting)
        message = mail.outbox[0]
        self.assertEqual(message.subject, 'Weekly Meeting today — Mercury Team')
        self.assertIn('has a Weekly Meeting scheduled for today', message.body)
        self.assertIn('View the Weekly Meeting:', message.body)
        self.assertNotIn('Level 10', message.body)
        self.assertNotIn('View the meeting:', message.body)

    def test_rock_alert_uses_the_organisations_rock_word(self):
        send_rock_off_track_alert(self.rock(self.mercury_team, 'Launch'))
        message = mail.outbox[0]
        self.assertEqual(message.subject, 'Priority marked off track: Launch')
        self.assertIn('Your Priority "Launch"', message.body)
        self.assertIn('View the Priority:', message.body)
        self.assertNotIn('Rock', message.body)

    def test_organisation_without_overrides_uses_the_generic_words(self):
        send_overdue_todo_digest(self.user, [self.todo(self.plain_team, 'Late')], organization=self.plain)
        meeting = Meeting.objects.create(team=self.plain_team, scheduled_date=date.today())
        send_meeting_reminder(self.user, meeting)
        send_rock_off_track_alert(self.rock(self.plain_team, 'Launch'))
        digest, reminder, alert = mail.outbox
        self.assertEqual(digest.subject, '1 overdue Action — Plain Org')
        self.assertIn('You have 1 overdue Action:', digest.body)
        self.assertIn('View your Actions:', digest.body)
        self.assertEqual(reminder.subject, 'Weekly Meeting today — Plain Team')
        self.assertIn('has a Weekly Meeting scheduled', reminder.body)
        self.assertIn('View the Weekly Meeting:', reminder.body)
        self.assertEqual(alert.subject, 'Priority marked off track: Launch')
        self.assertIn('Your Priority "Launch"', alert.body)

    def test_digest_without_an_organisation_uses_the_generic_words(self):
        todos = [self.todo(self.plain_team, 'Late one'), self.todo(self.plain_team, 'Late two')]
        send_overdue_todo_digest(self.user, todos)
        message = mail.outbox[0]
        self.assertEqual(message.subject, '2 overdue Actions — EOS App')
        self.assertIn('You have 2 overdue Actions:', message.body)

    @override_settings(ALLOWED_HOSTS=['testserver', 'mercury.example.test'])
    def test_preferences_page_labels_use_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.client.get('/notifications/preferences/', HTTP_HOST='mercury.example.test')
        self.assertContains(resp, 'Overdue Action digest')
        self.assertContains(resp, 'Weekly Meeting day reminders')
        self.assertContains(resp, 'Priority off-track alerts')
        self.assertNotContains(resp, 'Overdue To-Do digest')
        self.assertNotContains(resp, 'Rock off-track alerts')

    @override_settings(ALLOWED_HOSTS=['testserver', 'plain.example.test'])
    def test_preferences_page_on_a_default_host_shows_the_generic_words(self):
        OrganizationDomain.objects.create(organization=self.plain, hostname='plain.example.test')
        self.client.force_login(self.user)
        resp = self.client.get('/notifications/preferences/', HTTP_HOST='plain.example.test')
        self.assertContains(resp, 'Overdue Action digest')
        self.assertContains(resp, 'Weekly Meeting day reminders')
        self.assertContains(resp, 'Priority off-track alerts')
