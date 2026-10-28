from datetime import date

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.accounts.terminology import Terms, get_terms
from apps.issues.models import IssueActivity
from apps.meetings.forms import CascadingMessagesForm, HeadlineForm, MeetingRatingForm
from apps.meetings.models import (
    SEGMENT_NAMES, Headline, Meeting, MeetingNote, MeetingRating, segment_names_for,
)
from apps.meetings.views import _build_runner_context
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
RENAMED_SEGMENTS = [
    'Check-in', 'Metrics Board Review', 'Objective Review', 'Updates', 'Action Review', 'PRS', 'Conclude',
]


class SegmentNamesTest(TestCase):
    def test_defaults_match_the_segment_constant(self):
        self.assertEqual(segment_names_for(Terms()), SEGMENT_NAMES)

    def test_uses_the_organisations_words(self):
        self.assertEqual(segment_names_for(Terms(RENAMED)), RENAMED_SEGMENTS)


class HeadlineFormTest(TestCase):
    def test_placeholder_names_the_headline_in_the_organisations_word(self):
        placeholder = HeadlineForm(terms=Terms(RENAMED)).fields['text'].widget.attrs['placeholder']
        self.assertEqual(placeholder, 'Short update — good news or concern')

    def test_placeholder_defaults_without_terms(self):
        placeholder = HeadlineForm().fields['text'].widget.attrs['placeholder']
        self.assertEqual(placeholder, 'Short headline — good news or concern')


class ConcludeFormsTest(TestCase):
    def test_placeholders_name_the_meeting_in_the_organisations_word(self):
        rating = MeetingRatingForm(terms=Terms(RENAMED))
        self.assertEqual(
            rating.fields['improvement_note'].widget.attrs['placeholder'],
            "What would make next week's weekly meeting better?",
        )
        cascading = CascadingMessagesForm(terms=Terms(RENAMED))
        self.assertEqual(
            cascading.fields['cascading_messages'].widget.attrs['placeholder'],
            'What does the rest of the organisation need to know from this weekly meeting?',
        )

    def test_placeholders_default_without_terms(self):
        self.assertEqual(
            MeetingRatingForm().fields['improvement_note'].widget.attrs['placeholder'],
            "What would make next week's meeting better?",
        )
        self.assertEqual(
            CascadingMessagesForm().fields['cascading_messages'].widget.attrs['placeholder'],
            'What does the rest of the organisation need to know from this meeting?',
        )


@override_settings(ALLOWED_HOSTS=HOSTS)
class MeetingTerminologyTest(TestCase):
    """Meeting pages on an organisation's host use that organisation's words."""

    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', terminology=RENAMED)
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        self.silavapi = Organization.objects.create(name='Silavapi Org')
        OrganizationDomain.objects.create(organization=self.silavapi, hostname=SILAVAPI)
        self.user = User.objects.create_user(username='meetinguser', password='pw')
        self.mercury_team = Team.objects.create(organization=self.mercury, name='Mercury Team')
        self.silavapi_team = Team.objects.create(organization=self.silavapi, name='Silavapi Team')
        for org, team in ((self.mercury, self.mercury_team), (self.silavapi, self.silavapi_team)):
            Membership.objects.create(user=self.user, organization=org)
            self.user.profile.teams.add(team)
        self.meeting = Meeting.objects.create(
            team=self.mercury_team, scheduled_date=date(2026, 1, 5), created_by=self.user,
        )
        self.client.force_login(self.user)

    def start_at_segment(self, meeting, segment):
        meeting.start()
        meeting.current_segment = segment
        meeting.save(update_fields=['current_segment'])

    def test_list_uses_the_organisations_meeting_name(self):
        resp = self.client.get('/meetings/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Weekly Meetings — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Weekly Meetings</h1>')
        self.assertNotContains(resp, 'Level 10')

    def test_empty_list_names_the_first_meeting_in_the_organisations_word(self):
        self.meeting.delete()
        resp = self.client.get('/meetings/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Schedule your first Weekly Meeting to get started.')
        self.assertContains(resp, 'No weekly meetings yet')
        self.assertContains(resp, 'bi-plus-lg me-1"></i>Schedule Weekly Meeting')
        self.assertNotContains(resp, 'No meetings yet')
        self.assertNotContains(resp, 'Schedule Meeting')

    def test_list_schedule_button_uses_the_organisations_word(self):
        resp = self.client.get('/meetings/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'bi-plus-lg me-1"></i>Schedule Weekly Meeting')
        self.assertNotContains(resp, 'Schedule Meeting')

    def test_list_shows_the_renamed_current_segment(self):
        self.start_at_segment(self.meeting, 2)
        resp = self.client.get('/meetings/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Objective Review')
        self.assertNotContains(resp, 'Rock Review')

    def test_create_page_and_message_use_the_organisations_meeting_name(self):
        resp = self.client.get('/meetings/create/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Schedule Weekly Meeting — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Schedule Weekly Meeting</h1>')
        self.assertContains(resp, 'A Weekly Meeting runs 90 minutes')
        self.assertContains(resp, 'bi-calendar-plus me-1"></i>Schedule Weekly Meeting')
        self.assertNotContains(resp, 'Schedule Meeting<')
        resp = self.client.post(
            '/meetings/create/', {'team': self.mercury_team.pk, 'scheduled_date': '2026-02-02'},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Weekly Meeting scheduled for 2026-02-02.')

    def test_scheduled_detail_shows_the_renamed_agenda(self):
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'bi-play-fill me-1"></i>Start Weekly Meeting')
        self.assertNotContains(resp, 'Start Meeting')
        self.assertEqual(resp.context['segment_names'], RENAMED_SEGMENTS)
        for name in ['Objective Review', 'Updates', 'Action Review']:
            with self.subTest(name=name):
                self.assertContains(resp, name)
        for name in ['Rock Review', 'Headlines', 'To-Do Review', 'Level 10']:
            with self.subTest(name=name):
                self.assertNotContains(resp, name)

    def test_starting_reports_in_the_organisations_word(self):
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/start/', HTTP_HOST=MERCURY, follow=True,
        )
        self.assertEqual(
            [str(m) for m in resp.context['messages']],
            ["Weekly Meeting started! Good luck — you've got 90 minutes."],
        )

    def test_print_before_completion_warns_in_the_organisations_word(self):
        resp = self.client.get(
            f'/meetings/{self.meeting.pk}/print/', HTTP_HOST=MERCURY, follow=True,
        )
        self.assertEqual(
            [str(m) for m in resp.context['messages']],
            ['Finish the weekly meeting before exporting its notes.'],
        )

    def test_conclude_segment_uses_the_organisations_words(self):
        self.start_at_segment(self.meeting, 6)
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        for text in [
            'then rate the weekly meeting 1-10.',
            'Rate This Weekly Meeting',
            "confirm('Complete this weekly meeting? This cannot be undone.')",
            'bi-flag-fill me-1"></i>Complete Weekly Meeting',
            'What would make next week&#x27;s weekly meeting better?',
            'need to know from this weekly meeting?',
        ]:
            with self.subTest(text=text):
                self.assertContains(resp, text)
        for text in [
            'rate the meeting 1-10', 'Rate This Meeting', 'Complete this meeting?',
            'Complete Meeting<',
        ]:
            with self.subTest(text=text):
                self.assertNotContains(resp, text)

    def test_completing_reports_in_the_organisations_word(self):
        self.start_at_segment(self.meeting, 6)
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/complete/', {'cascading_messages': 'Tell everyone.'},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertEqual(
            [str(m) for m in resp.context['messages']], ['Weekly Meeting completed! Great work.'],
        )

    def test_runner_uses_the_renamed_segment_and_placeholder(self):
        self.start_at_segment(self.meeting, 3)
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        self.assertEqual(resp.context['segment_name'], 'Updates')
        self.assertContains(resp, 'Updates Notes')
        self.assertContains(resp, 'Short update — good news or concern')
        self.assertContains(resp, 'No updates yet. Add one above.')
        self.assertContains(resp, 'Next: Action Review')

    def test_rock_segment_uses_the_organisations_words(self):
        self.start_at_segment(self.meeting, 2)
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Each Objective owner')
        self.assertContains(resp, 'No active Objectives for')

    def test_todo_segment_uses_the_organisations_words(self):
        self.start_at_segment(self.meeting, 4)
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Review open Actions for team members')
        self.assertContains(resp, 'No open Actions for the team')
        self.assertContains(resp, 'Add Action')

    def test_adding_a_headline_uses_the_organisations_word(self):
        self.start_at_segment(self.meeting, 3)
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/headlines/add/',
            {'headline_type': Headline.TYPE_GOOD, 'text': 'Closed the Acme deal'},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Update added.')
        self.assertEqual(self.meeting.headlines.count(), 1)

    def test_escalating_a_headline_renames_the_message_but_not_the_stored_note(self):
        self.start_at_segment(self.meeting, 3)
        headline = Headline.objects.create(
            meeting=self.meeting, author=self.user, headline_type=Headline.TYPE_BAD, text='Server down',
        )
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/headlines/{headline.pk}/escalate/',
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Update escalated to Blockers.')
        activity = IssueActivity.objects.get()
        self.assertIn('Escalated from Level 10 Meeting headline', activity.notes)

    def test_segue_message_uses_the_organisations_word(self):
        self.meeting.start()
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/segue/',
            {'personal_best': 'Ran a 5K', 'business_best': 'Shipped it'},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Check-in entry saved.')

    def test_completed_meeting_and_print_use_the_organisations_words(self):
        self.meeting.start()
        MeetingNote.objects.create(meeting=self.meeting, segment=2, text='Two off track.')
        ToDo.objects.create(title='Follow up', owner=self.user, team=self.mercury_team)
        self.meeting.complete(cascading_messages='Tell everyone.')

        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Objective Review')
        self.assertContains(resp, 'Actions Created This Meeting')
        self.assertContains(resp, 'bi-journal-text me-1"></i>Weekly Meeting Notes')
        self.assertNotContains(resp, 'Rock Review')
        self.assertNotContains(resp, '>Meeting Notes<')

    def test_print_view_uses_the_organisations_words(self):
        # Rendered through the runner context rather than the view: the view's
        # organisation lookup is fixed separately (fix/meeting-print-view-org).
        self.meeting.start()
        MeetingNote.objects.create(meeting=self.meeting, segment=2, text='Two off track.')
        ToDo.objects.create(title='Follow up', owner=self.user, team=self.mercury_team)
        MeetingRating.objects.create(meeting=self.meeting, participant=self.user, score=9)
        self.meeting.complete(cascading_messages='Tell everyone.')
        request = RequestFactory().get(f'/meetings/{self.meeting.pk}/print/', HTTP_HOST=MERCURY)
        request.user = self.user
        request.host_org = self.mercury
        request.session = {}
        ctx = _build_runner_context(self.meeting, self.user, get_terms(request))

        html = render_to_string('meetings/meeting_print.html', ctx, request=request)
        self.assertIn('<title>Mercury Team — 2026-01-05 — Weekly Meeting Notes — Print</title>', html)
        self.assertIn('Weekly Meeting Notes —', html)
        self.assertIn('<span class="fw-semibold small">Weekly Meeting Notes</span>', html)
        self.assertIn('average weekly meeting rating', html)
        self.assertNotIn('>Meeting Notes<', html)
        self.assertIn('Objective Review', html)
        self.assertIn('Actions Created This Meeting', html)
        self.assertNotIn('Level 10', html)

    def test_default_host_shows_the_generic_words(self):
        meeting = Meeting.objects.create(
            team=self.silavapi_team, scheduled_date=date(2026, 1, 5), created_by=self.user,
        )
        resp = self.client.get('/meetings/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, '<title>Weekly Meetings — Silavapi Org</title>', html=True)
        self.assertContains(resp, 'Weekly Meetings</h1>')
        self.assertContains(resp, 'bi-plus-lg me-1"></i>Schedule Weekly Meeting')

        resp = self.client.get(f'/meetings/{meeting.pk}/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'bi-play-fill me-1"></i>Start Weekly Meeting')
        self.assertEqual(resp.context['segment_names'], SEGMENT_NAMES)
        for name in ['Priority Review', 'Updates', 'Action Review']:
            with self.subTest(name=name):
                self.assertContains(resp, name)
        self.assertNotContains(resp, 'Objective')

        resp = self.client.post(f'/meetings/{meeting.pk}/start/', HTTP_HOST=SILAVAPI, follow=True)
        self.assertEqual(
            [str(m) for m in resp.context['messages']],
            ["Weekly Meeting started! Good luck — you've got 90 minutes."],
        )
        self.start_at_segment(meeting, 6)
        resp = self.client.get(f'/meetings/{meeting.pk}/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'Rate This Weekly Meeting')
        self.assertContains(resp, 'bi-flag-fill me-1"></i>Complete Weekly Meeting')
