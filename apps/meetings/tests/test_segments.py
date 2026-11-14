"""The meeting agenda: the shipped default, per-organisation overrides, and
the historical-safety guarantee that is the whole point of freezing it onto
each meeting (see STRUCTURAL-CONFIGURABILITY.md)."""
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.accounts.terminology import Terms
from apps.meetings.models import Meeting, MeetingNote, MeetingSegmentDefinition
from apps.meetings.segments import (
    CONCLUDE, CUSTOM_NOTES, DEFAULT_SEGMENTS, resolve_agenda, segments_for,
)

HOST = 'segments.example.test'


def build_org(name='Segments Org', hostname=HOST):
    org = Organization.objects.create(name=name)
    OrganizationDomain.objects.create(organization=org, hostname=hostname)
    team = Team.objects.create(organization=org, name=f'{name} Team')
    user = User.objects.create_user(username=f'{name.lower().replace(" ", "")}user', password='pw')
    Membership.objects.create(user=user, organization=org, role=Membership.ROLE_ADMIN)
    user.profile.teams.add(team)
    return org, team, user


def make_meeting(team, user):
    return Meeting.objects.create(team=team, scheduled_date=date.today(), created_by=user)


class SegmentsForTest(TestCase):
    def test_no_organisation_gets_the_shipped_default_plus_conclude(self):
        agenda = segments_for(None)
        self.assertEqual(len(agenda), len(DEFAULT_SEGMENTS) + 1)
        self.assertEqual(agenda[-1]['segment_type'], CONCLUDE)
        self.assertEqual(agenda[:-1], DEFAULT_SEGMENTS)

    def test_organisation_without_rows_gets_the_same_default(self):
        org = Organization.objects.create(name='Plain Org')
        self.assertEqual(segments_for(org), segments_for(None))

    def test_disabled_rows_are_left_out(self):
        org = Organization.objects.create(name='Disabling Org')
        MeetingSegmentDefinition.objects.create(
            organization=org, order=0, segment_type='check_in', duration_minutes=5,
        )
        MeetingSegmentDefinition.objects.create(
            organization=org, order=1, segment_type='ids', duration_minutes=60, enabled=False,
        )
        agenda = segments_for(org)
        self.assertEqual([s['segment_type'] for s in agenda], ['check_in', CONCLUDE])

    def test_rows_are_returned_in_order_not_creation_order(self):
        org = Organization.objects.create(name='Reordering Org')
        MeetingSegmentDefinition.objects.create(
            organization=org, order=1, segment_type='ids', duration_minutes=60,
        )
        MeetingSegmentDefinition.objects.create(
            organization=org, order=0, segment_type='check_in', duration_minutes=5,
        )
        agenda = segments_for(org)
        self.assertEqual([s['segment_type'] for s in agenda], ['check_in', 'ids', CONCLUDE])

    def test_a_custom_segment_carries_its_label_into_the_agenda(self):
        org = Organization.objects.create(name='Custom Org')
        MeetingSegmentDefinition.objects.create(
            organization=org, order=0, segment_type=CUSTOM_NOTES,
            label='Customer Shoutouts', duration_minutes=10,
        )
        agenda = segments_for(org)
        self.assertEqual(agenda[0], {
            'segment_type': CUSTOM_NOTES, 'duration_minutes': 10, 'label': 'Customer Shoutouts',
        })

    def test_conclude_is_always_last_even_with_zero_configured_rows(self):
        org = Organization.objects.create(name='Empty Org')
        MeetingSegmentDefinition.objects.create(
            organization=org, order=0, segment_type='check_in', duration_minutes=5, enabled=False,
        )
        self.assertEqual(segments_for(org), [dict(segment_type=CONCLUDE, duration_minutes=5, label='')])

    def test_one_organisations_rows_never_reach_another(self):
        a = Organization.objects.create(name='Org A')
        b = Organization.objects.create(name='Org B')
        MeetingSegmentDefinition.objects.create(
            organization=a, order=0, segment_type=CUSTOM_NOTES, label='A Only', duration_minutes=5,
        )
        self.assertEqual(segments_for(b), segments_for(None))
        self.assertNotIn('A Only', [s.get('label') for s in segments_for(b)])


class MeetingSegmentDefinitionValidationTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Validation Org')

    def test_custom_segment_requires_a_label(self):
        row = MeetingSegmentDefinition(
            organization=self.org, segment_type=CUSTOM_NOTES, duration_minutes=5,
        )
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_conclude_cannot_be_configured_as_a_row(self):
        """Defense in depth: the admin form's `choices` already keeps CONCLUDE
        off the dropdown; this covers a row created another way."""
        row = MeetingSegmentDefinition(
            organization=self.org, segment_type=CONCLUDE, duration_minutes=5,
        )
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_a_built_in_segment_does_not_require_a_label(self):
        MeetingSegmentDefinition(
            organization=self.org, segment_type='check_in', duration_minutes=5,
        ).full_clean()


class ResolveAgendaTest(TestCase):
    def test_built_ins_resolve_through_terms(self):
        renamed = Terms({'rock': 'Objective', 'rocks': 'Objectives'})
        resolved = resolve_agenda([{'segment_type': 'priority_review', 'duration_minutes': 5, 'label': ''}], renamed)
        self.assertEqual(resolved[0]['name'], 'Objective Review')
        self.assertEqual(resolved[0]['template'], 'rocks.html')

    def test_an_explicit_label_overrides_the_terms_derived_name(self):
        resolved = resolve_agenda(
            [{'segment_type': CUSTOM_NOTES, 'duration_minutes': 10, 'label': 'Wins of the Week'}],
            Terms(),
        )
        self.assertEqual(resolved[0]['name'], 'Wins of the Week')
        self.assertEqual(resolved[0]['template'], 'custom.html')


@override_settings(ALLOWED_HOSTS=['testserver', HOST])
class HistoricalSafetyTest(TestCase):
    """The scenario STRUCTURAL-CONFIGURABILITY.md flagged as the risky part of
    this whole feature: changing an organisation's agenda after a meeting
    already exists must never change what that meeting's own notes mean."""

    def setUp(self):
        self.org, self.team, self.user = build_org()
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=0, segment_type='check_in', duration_minutes=5,
        )
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=1, segment_type='ids', duration_minutes=60,
        )
        # Agenda at this point: [check_in, ids, conclude].
        self.old_meeting = make_meeting(self.team, self.user)
        MeetingNote.objects.create(meeting=self.old_meeting, segment=1, text='PRS notes from before the change')

    def test_an_existing_meetings_agenda_is_unaffected_by_a_later_reorder(self):
        self.old_meeting.refresh_from_db()
        before = list(self.old_meeting.agenda)

        # Reorder, disable one, and add a new custom segment -- a complete
        # rewrite of the organisation's live agenda.
        MeetingSegmentDefinition.objects.filter(organization=self.org, segment_type='ids').update(order=0)
        MeetingSegmentDefinition.objects.filter(organization=self.org, segment_type='check_in').update(
            order=1, enabled=False,
        )
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=2, segment_type=CUSTOM_NOTES, label='New Segment', duration_minutes=15,
        )

        self.old_meeting.refresh_from_db()
        self.assertEqual(self.old_meeting.agenda, before)
        self.assertEqual(
            [s['segment_type'] for s in self.old_meeting.agenda], ['check_in', 'ids', CONCLUDE]
        )

    def test_the_note_still_means_what_it_meant_when_it_was_written(self):
        """This is the failure mode from the proposal made concrete: without a
        snapshot, this note would start rendering under "Check-in" instead of
        "PRS" the moment the organisation's segment 1 changed."""
        MeetingSegmentDefinition.objects.filter(organization=self.org).update(enabled=False)
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=0, segment_type='check_in', duration_minutes=5,
        )
        note = MeetingNote.objects.get(meeting=self.old_meeting, segment=1)
        self.assertEqual(note.segment_name, 'PRS')

    def test_a_new_meeting_picks_up_the_changed_agenda(self):
        MeetingSegmentDefinition.objects.filter(organization=self.org, segment_type='ids').delete()
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=5, segment_type=CUSTOM_NOTES, label='Brand New', duration_minutes=15,
        )
        new_meeting = make_meeting(self.team, self.user)
        self.assertEqual(
            [s['segment_type'] for s in new_meeting.agenda], ['check_in', CUSTOM_NOTES, CONCLUDE]
        )
        # The old meeting is still exactly as it was.
        self.old_meeting.refresh_from_db()
        self.assertEqual(
            [s['segment_type'] for s in self.old_meeting.agenda], ['check_in', 'ids', CONCLUDE]
        )


@override_settings(ALLOWED_HOSTS=['testserver', HOST])
class CustomSegmentRunnerTest(TestCase):
    """A custom segment is runnable end to end: it starts, shows its own
    label, uses the generic notes box, and the meeting still completes."""

    def setUp(self):
        self.org, self.team, self.user = build_org('Custom Runner Org')
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=0, segment_type=CUSTOM_NOTES,
            label='Customer Shoutouts', duration_minutes=10,
        )
        self.meeting = make_meeting(self.team, self.user)
        self.client.force_login(self.user)

    def test_the_custom_segment_renders_its_own_label_and_the_notes_box(self):
        self.meeting.start()
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=HOST)
        self.assertContains(resp, 'Customer Shoutouts')
        self.assertContains(resp, 'notes box')

    def test_saving_a_note_on_the_custom_segment_works_like_any_other(self):
        self.meeting.start()
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/notes/', {'notes': 'Loved the new onboarding flow.'},
            HTTP_HOST=HOST, follow=True,
        )
        self.assertContains(resp, 'Loved the new onboarding flow.')

    def test_the_meeting_still_reaches_conclude_and_completes(self):
        self.meeting.start()
        self.meeting.current_segment = len(self.meeting.agenda) - 1
        self.meeting.save(update_fields=['current_segment'])
        resp = self.client.get(f'/meetings/{self.meeting.pk}/', HTTP_HOST=HOST)
        self.assertContains(resp, 'Complete')
        resp = self.client.post(
            f'/meetings/{self.meeting.pk}/complete/', {'cascading_messages': ''},
            HTTP_HOST=HOST, follow=True,
        )
        self.meeting.refresh_from_db()
        self.assertTrue(self.meeting.is_complete)


@override_settings(ALLOWED_HOSTS=['testserver', HOST])
class DashboardSegmentCrossAppTest(TestCase):
    """apps.accounts.views.HomeView resolves a meeting's segment name from
    that meeting's own agenda, not the organisation's current live settings —
    the cross-app spot where this was easy to get wrong."""

    def setUp(self):
        self.org, self.team, self.user = build_org('Dashboard Segments Org')
        self.meeting = make_meeting(self.team, self.user)
        self.client.force_login(self.user)

    def test_dashboard_names_the_next_meetings_own_segment(self):
        resp = self.client.get('/', HTTP_HOST=HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Weekly 90-minute rhythm')

    def test_after_reordering_an_existing_meeting_keeps_showing_its_own_segment(self):
        self.meeting.start()
        self.meeting.current_segment = 1
        self.meeting.save(update_fields=['current_segment'])
        # Add a brand-new first segment to the organisation's live agenda.
        MeetingSegmentDefinition.objects.create(
            organization=self.org, order=0, segment_type=CUSTOM_NOTES,
            label='New First Segment', duration_minutes=5,
        )
        resp = self.client.get('/', HTTP_HOST=HOST)
        content = resp.content.decode()
        self.assertNotIn('New First Segment', content)
        self.assertIn('Metrics Board Review', content)
