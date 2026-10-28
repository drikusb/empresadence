from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, Team
from apps.meetings.models import Meeting
from apps.notifications.emails import (
    send_meeting_reminder,
    send_overdue_todo_digest,
    send_rock_off_track_alert,
    send_user_invite_email,
)
from apps.rocks.models import Rock
from apps.todos.models import ToDo


@override_settings(DEFAULT_FROM_EMAIL='EOS App <noreply@example.com>', DEFAULT_BRAND_NAME='EOS App')
class BrandedEmailTest(TestCase):
    """Emails for an organisation carry its display name as sender, sign-off and subject."""

    def setUp(self):
        self.user = User.objects.create_user(username='mailee', email='mailee@example.com', password='pw')
        self.org = Organization.objects.create(name='Mercury Org', display_name='Mercury Consortium')
        self.team = Team.objects.create(organization=self.org, name='Mercury Team')
        Membership.objects.create(user=self.user, organization=self.org)
        self.todo = ToDo.objects.create(
            title='Late thing', owner=self.user, team=self.team,
            due_date=date.today() - timedelta(days=1),
        )

    def test_sender_is_the_display_name_on_the_configured_address(self):
        send_overdue_todo_digest(self.user, [self.todo], organization=self.org)
        self.assertEqual(mail.outbox[0].from_email, 'Mercury Consortium <noreply@example.com>')

    def test_sender_uses_email_from_name_when_set(self):
        self.org.email_from_name = 'Mercury Ops Desk'
        self.org.save()
        send_overdue_todo_digest(self.user, [self.todo], organization=self.org)
        self.assertEqual(mail.outbox[0].from_email, 'Mercury Ops Desk <noreply@example.com>')

    def test_body_signs_off_with_the_display_name(self):
        send_overdue_todo_digest(self.user, [self.todo], organization=self.org)
        body = mail.outbox[0].body.rstrip()
        self.assertTrue(body.endswith('— Mercury Consortium'), body[-60:])
        self.assertNotIn('EOS App', body)

    def test_digest_subject_uses_the_display_name(self):
        send_overdue_todo_digest(self.user, [self.todo], organization=self.org)
        self.assertEqual(mail.outbox[0].subject, '1 overdue Action — Mercury Consortium')

    def test_invite_uses_the_display_name_and_still_names_the_organisation(self):
        send_user_invite_email(self.user, self.org, 'https://example.com/reset/a/b/')
        message = mail.outbox[0]
        self.assertEqual(message.subject, "You've been invited to Mercury Consortium")
        self.assertEqual(message.from_email, 'Mercury Consortium <noreply@example.com>')
        self.assertIn('join Mercury Consortium (Mercury Org)', message.body)
        self.assertTrue(message.body.rstrip().endswith('— Mercury Consortium'))

    def test_invite_without_a_display_name_names_the_organisation_once(self):
        self.org.display_name = ''
        self.org.save()
        send_user_invite_email(self.user, self.org, 'https://example.com/reset/a/b/')
        message = mail.outbox[0]
        self.assertEqual(message.subject, "You've been invited to Mercury Org")
        self.assertIn('join Mercury Org.', message.body)
        self.assertNotIn('(Mercury Org)', message.body)

    def test_meeting_reminder_and_rock_alert_are_branded_by_the_teams_organisation(self):
        meeting = Meeting.objects.create(team=self.team, scheduled_date=date.today())
        send_meeting_reminder(self.user, meeting)
        rock = Rock.objects.create(
            title='Mercury Rock', owner=self.user, team=self.team,
            quarter=1, year=2026, due_date=date(2026, 3, 31), status=Rock.STATUS_OFF_TRACK,
        )
        send_rock_off_track_alert(rock)
        for message in mail.outbox:
            with self.subTest(subject=message.subject):
                self.assertEqual(message.from_email, 'Mercury Consortium <noreply@example.com>')
                self.assertTrue(message.body.rstrip().endswith('— Mercury Consortium'))

    def test_default_brand_when_no_organisation_is_given(self):
        send_overdue_todo_digest(self.user, [self.todo])
        message = mail.outbox[0]
        self.assertEqual(message.from_email, 'EOS App <noreply@example.com>')
        self.assertEqual(message.subject, '1 overdue Action — EOS App')
        self.assertTrue(message.body.rstrip().endswith('— EOS App'))
        self.assertNotIn('Mercury Consortium', message.body)

    @override_settings(DEFAULT_FROM_EMAIL='noreply@example.com')
    def test_bare_sender_address_still_gets_the_display_name(self):
        send_overdue_todo_digest(self.user, [self.todo], organization=self.org)
        self.assertEqual(mail.outbox[0].from_email, 'Mercury Consortium <noreply@example.com>')
