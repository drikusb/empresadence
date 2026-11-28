from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Membership, Organization, Team
from apps.meetings.models import Meeting


class SegmentTimerTest(TestCase):
    """The countdown must carry on across the reloads every runner action causes (#123)."""

    def setUp(self):
        org = Organization.objects.create(name='Timer Org')
        self.team = Team.objects.create(organization=org, name='Timer Team')
        self.user = User.objects.create_user(username='timeruser', password='pw')
        Membership.objects.create(user=self.user, organization=org, role=Membership.ROLE_ADMIN)
        self.user.profile.teams.add(self.team)
        self.meeting = Meeting.objects.create(
            team=self.team, scheduled_date=date.today(), created_by=self.user,
        )
        self.client.force_login(self.user)
        self.url = f'/meetings/{self.meeting.pk}/'

    def rewind_segment(self, **delta):
        """Pretend the current segment began some time ago."""
        began = timezone.now() - timedelta(**delta)
        Meeting.objects.filter(pk=self.meeting.pk).update(segment_started_at=began)
        return began

    def segment_started_attr(self):
        self.meeting.refresh_from_db()
        local = timezone.localtime(self.meeting.segment_started_at)
        return f'data-segment-started="{local.isoformat()}"'

    def test_starting_a_meeting_starts_the_first_segment(self):
        self.assertIsNone(self.meeting.segment_started_at)
        self.meeting.start()
        self.assertEqual(self.meeting.segment_started_at, self.meeting.started_at)

    def test_advancing_starts_the_next_segment(self):
        self.meeting.start()
        began = self.rewind_segment(minutes=4)
        self.meeting.refresh_from_db()
        self.meeting.advance()
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.current_segment, 1)
        self.assertGreater(self.meeting.segment_started_at, began + timedelta(minutes=3))

    def test_advancing_past_the_last_segment_leaves_the_start_time_alone(self):
        self.meeting.start()
        self.meeting.current_segment = len(self.meeting.agenda) - 1
        self.meeting.save(update_fields=['current_segment'])
        began = self.rewind_segment(minutes=2)
        self.meeting.refresh_from_db()
        self.meeting.advance()
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.segment_started_at, began)

    def test_runner_tells_the_timer_when_the_segment_started(self):
        self.meeting.start()
        self.rewind_segment(minutes=3)
        resp = self.client.get(self.url)
        self.assertContains(resp, self.segment_started_attr())
        self.assertContains(resp, f'data-timer-key="{self.meeting.pk}:0"')

    def test_saving_notes_does_not_restart_the_segment(self):
        self.meeting.start()
        began = self.rewind_segment(minutes=3)
        resp = self.client.post(f'/meetings/{self.meeting.pk}/notes/', {'text': 'Agreed.'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.segment_started_at, began)
        self.assertContains(resp, self.segment_started_attr())

    def test_advance_view_starts_the_next_segments_clock(self):
        self.meeting.start()
        began = self.rewind_segment(minutes=5)
        self.client.post(f'/meetings/{self.meeting.pk}/advance/')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.current_segment, 1)
        self.assertGreater(self.meeting.segment_started_at, began)
        self.assertContains(self.client.get(self.url), f'data-timer-key="{self.meeting.pk}:1"')

    def test_meeting_already_running_before_the_field_existed_still_renders(self):
        self.meeting.start()
        Meeting.objects.filter(pk=self.meeting.pk).update(segment_started_at=None)
        resp = self.client.get(self.url)
        self.assertContains(resp, 'data-segment-started=""')
