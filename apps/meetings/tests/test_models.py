from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from apps.accounts.models import Organization, Team
from apps.meetings.models import Meeting, SegueEntry, Headline, MeetingRating


def make_meeting(status=Meeting.STATUS_SCHEDULED):
    org = Organization.objects.get_or_create(name='Meeting Org')[0]
    team = Team.objects.get_or_create(organization=org, name='Meeting Team')[0]
    user = User.objects.get_or_create(username='meetinguser')[0]
    return Meeting.objects.create(
        team=team,
        scheduled_date=date.today(),
        status=status,
        created_by=user,
    )


class MeetingStatusTest(TestCase):
    def test_scheduled_by_default(self):
        m = make_meeting()
        self.assertTrue(m.is_scheduled)
        self.assertFalse(m.is_active)
        self.assertFalse(m.is_complete)

    def test_start_transitions_to_active(self):
        m = make_meeting()
        m.start()
        self.assertTrue(m.is_active)
        self.assertIsNotNone(m.started_at)

    def test_complete_transitions_to_complete(self):
        m = make_meeting(status=Meeting.STATUS_ACTIVE)
        m.started_at = timezone.now()
        m.save()
        m.complete(cascading_messages='Follow up with sales')
        self.assertTrue(m.is_complete)
        self.assertIsNotNone(m.ended_at)
        self.assertEqual(m.cascading_messages, 'Follow up with sales')

    def test_str(self):
        m = make_meeting()
        self.assertIn(m.team.name, str(m))


class MeetingAdvanceTest(TestCase):
    def test_advance_increments_segment(self):
        m = make_meeting()
        m.advance()
        self.assertEqual(m.current_segment, 1)

    def test_advance_does_not_exceed_last(self):
        m = make_meeting()
        m.current_segment = len(m.agenda) - 1
        m.save()
        m.advance()
        self.assertEqual(m.current_segment, len(m.agenda) - 1)

    def test_is_last_segment(self):
        m = make_meeting()
        self.assertFalse(m.is_last_segment)
        m.current_segment = len(m.agenda) - 1
        self.assertTrue(m.is_last_segment)

    def test_segment_name_and_duration(self):
        m = make_meeting()
        self.assertEqual(m.segment_name, 'Check-in')
        self.assertIsInstance(m.segment_duration, int)

    def test_a_new_meeting_snapshots_the_shipped_default_agenda(self):
        m = make_meeting()
        self.assertEqual(
            [s['segment_type'] for s in m.agenda],
            ['check_in', 'metrics_review', 'priority_review', 'updates',
             'action_review', 'ids', 'conclude'],
        )
        self.assertEqual(m.agenda[5]['duration_minutes'], 60)


class MeetingRatingTest(TestCase):
    def setUp(self):
        self.meeting = make_meeting()
        self.user1 = User.objects.get_or_create(username='rater1')[0]
        self.user2 = User.objects.get_or_create(username='rater2')[0]

    def test_average_rating_none_when_no_ratings(self):
        self.assertIsNone(self.meeting.average_rating)

    def test_average_rating_single(self):
        MeetingRating.objects.create(meeting=self.meeting, participant=self.user1, score=8)
        self.assertEqual(self.meeting.average_rating, 8.0)

    def test_average_rating_multiple(self):
        MeetingRating.objects.create(meeting=self.meeting, participant=self.user1, score=8)
        MeetingRating.objects.create(meeting=self.meeting, participant=self.user2, score=6)
        self.assertEqual(self.meeting.average_rating, 7.0)


class MeetingDurationTest(TestCase):
    def test_duration_none_when_not_started(self):
        m = make_meeting()
        self.assertIsNone(m.duration_minutes)

    def test_duration_calculated_from_start_end(self):
        m = make_meeting(status=Meeting.STATUS_COMPLETE)
        m.started_at = timezone.now() - timezone.timedelta(minutes=90)
        m.ended_at = timezone.now()
        m.save()
        self.assertAlmostEqual(m.duration_minutes, 90, delta=1)
