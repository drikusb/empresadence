from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.meetings.forms import MeetingCreateForm
from apps.meetings.models import Meeting

DAY = date(2026, 11, 25)


class ScheduledMeetingTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Harbour Lights')
        self.team = Team.objects.create(organization=self.org, name='Leadership')
        self.other_team = Team.objects.create(organization=self.org, name='Operations')
        self.scheduler = self.make_user('scheduler', teams=[self.team])
        self.meeting = Meeting.objects.create(
            team=self.team, scheduled_date=DAY, created_by=self.scheduler,
        )

    def make_user(self, username, *, teams=(), role=Membership.ROLE_MEMBER):
        user = User.objects.create_user(username=username, password='pw')
        Membership.objects.create(user=user, organization=self.org, role=role)
        user.profile.teams.add(*teams)
        return user


class CanBeChangedByTest(ScheduledMeetingTestCase):
    def test_the_person_who_scheduled_it_may_change_it(self):
        self.assertTrue(self.meeting.can_be_changed_by(self.scheduler))

    def test_a_member_of_the_team_may_change_it(self):
        self.assertTrue(self.meeting.can_be_changed_by(self.make_user('teammate', teams=[self.team])))

    def test_an_organisation_admin_may_change_it(self):
        admin = self.make_user('admin', role=Membership.ROLE_ADMIN)
        self.assertTrue(self.meeting.can_be_changed_by(admin))

    def test_someone_on_another_team_may_not(self):
        self.assertFalse(self.meeting.can_be_changed_by(self.make_user('outsider', teams=[self.other_team])))

    def test_nobody_may_change_a_meeting_that_has_started_or_finished(self):
        admin = self.make_user('admin', role=Membership.ROLE_ADMIN)
        self.meeting.start()
        self.assertFalse(self.meeting.can_be_changed_by(admin))
        self.meeting.complete()
        self.assertFalse(self.meeting.can_be_changed_by(admin))


class DuplicateScheduleTest(ScheduledMeetingTestCase):
    def form(self, team, day, instance=None):
        return MeetingCreateForm(
            {'team': team.pk, 'scheduled_date': day.isoformat()}, org=self.org, instance=instance,
        )

    def test_a_second_meeting_for_the_same_team_and_date_is_refused(self):
        form = self.form(self.team, DAY)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('__all__', code='duplicate'))
        self.assertIn('25 November 2026', form.non_field_errors()[0])

    def test_another_date_or_another_team_is_accepted(self):
        self.assertTrue(self.form(self.team, DAY + timedelta(days=7)).is_valid())
        self.assertTrue(self.form(self.other_team, DAY).is_valid())

    def test_a_meeting_does_not_clash_with_itself_when_edited(self):
        self.assertTrue(self.form(self.team, DAY, instance=self.meeting).is_valid())

    def test_a_meeting_that_already_ran_that_day_does_not_block_a_new_one(self):
        self.meeting.start()
        self.meeting.complete()
        self.assertTrue(self.form(self.team, DAY).is_valid())

    def test_the_schedule_page_shows_the_error_and_creates_nothing(self):
        self.client.force_login(self.scheduler)
        resp = self.client.post('/meetings/create/', {'team': self.team.pk, 'scheduled_date': DAY.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Leadership already has one scheduled for 25 November 2026.')
        self.assertEqual(Meeting.objects.count(), 1)


class MeetingEditViewTest(ScheduledMeetingTestCase):
    def url(self):
        return f'/meetings/{self.meeting.pk}/edit/'

    def test_the_form_opens_with_the_saved_team_and_date(self):
        self.client.force_login(self.scheduler)
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'value="2026-11-25"')
        self.assertContains(resp, f'<option value="{self.team.pk}" selected>')
        self.assertContains(resp, 'Save changes')

    def test_saving_moves_the_meeting(self):
        self.client.force_login(self.scheduler)
        new_day = DAY + timedelta(days=1)
        resp = self.client.post(self.url(), {'team': self.other_team.pk, 'scheduled_date': new_day.isoformat()})
        self.assertRedirects(resp, '/meetings/')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.scheduled_date, new_day)
        self.assertEqual(self.meeting.team, self.other_team)

    def test_moving_onto_another_scheduled_meeting_is_refused(self):
        other = Meeting.objects.create(team=self.team, scheduled_date=DAY + timedelta(days=7))
        self.client.force_login(self.scheduler)
        resp = self.client.post(self.url(), {'team': self.team.pk, 'scheduled_date': other.scheduled_date.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already has one scheduled')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.scheduled_date, DAY)

    def test_someone_on_another_team_is_refused(self):
        self.client.force_login(self.make_user('outsider', teams=[self.other_team]))
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        resp = self.client.post(self.url(), {'team': self.team.pk, 'scheduled_date': '2026-12-01'})
        self.assertEqual(resp.status_code, 403)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.scheduled_date, DAY)

    def test_a_started_meeting_goes_back_to_its_page_unchanged(self):
        self.meeting.start()
        self.client.force_login(self.scheduler)
        resp = self.client.post(self.url(), {'team': self.team.pk, 'scheduled_date': '2026-12-01'})
        self.assertRedirects(resp, f'/meetings/{self.meeting.pk}/')
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.scheduled_date, DAY)


class MeetingDeleteViewTest(ScheduledMeetingTestCase):
    def url(self):
        return f'/meetings/{self.meeting.pk}/delete/'

    def test_the_confirmation_page_names_the_meeting_and_deletes_nothing(self):
        self.client.force_login(self.scheduler)
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Leadership')
        self.assertTrue(Meeting.objects.filter(pk=self.meeting.pk).exists())

    def test_confirming_deletes_the_meeting(self):
        self.client.force_login(self.scheduler)
        resp = self.client.post(self.url())
        self.assertRedirects(resp, '/meetings/')
        self.assertFalse(Meeting.objects.filter(pk=self.meeting.pk).exists())

    def test_someone_on_another_team_is_refused(self):
        self.client.force_login(self.make_user('outsider', teams=[self.other_team]))
        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.assertTrue(Meeting.objects.filter(pk=self.meeting.pk).exists())

    def test_a_live_meeting_is_kept(self):
        self.meeting.start()
        self.client.force_login(self.scheduler)
        resp = self.client.post(self.url())
        self.assertRedirects(resp, f'/meetings/{self.meeting.pk}/')
        self.assertTrue(Meeting.objects.filter(pk=self.meeting.pk).exists())

    def test_a_completed_meeting_is_kept(self):
        self.meeting.start()
        self.meeting.complete()
        self.client.force_login(self.scheduler)
        self.client.post(self.url())
        self.assertTrue(Meeting.objects.filter(pk=self.meeting.pk).exists())


class MeetingControlsTest(ScheduledMeetingTestCase):
    def test_the_list_offers_edit_and_delete_on_a_scheduled_meeting(self):
        self.client.force_login(self.scheduler)
        resp = self.client.get('/meetings/')
        self.assertContains(resp, f'/meetings/{self.meeting.pk}/edit/')
        self.assertContains(resp, f'/meetings/{self.meeting.pk}/delete/')

    def test_the_list_offers_neither_once_the_meeting_has_started(self):
        self.meeting.start()
        self.client.force_login(self.scheduler)
        resp = self.client.get('/meetings/')
        self.assertNotContains(resp, f'/meetings/{self.meeting.pk}/edit/')
        self.assertNotContains(resp, f'/meetings/{self.meeting.pk}/delete/')

    def test_the_meeting_page_offers_both_to_someone_who_may_change_it(self):
        self.client.force_login(self.scheduler)
        resp = self.client.get(f'/meetings/{self.meeting.pk}/')
        self.assertContains(resp, f'/meetings/{self.meeting.pk}/edit/')
        self.assertContains(resp, f'/meetings/{self.meeting.pk}/delete/')

    def test_the_meeting_page_offers_neither_to_someone_on_another_team(self):
        self.client.force_login(self.make_user('outsider', teams=[self.other_team]))
        resp = self.client.get(f'/meetings/{self.meeting.pk}/')
        self.assertNotContains(resp, f'/meetings/{self.meeting.pk}/edit/')
        self.assertNotContains(resp, f'/meetings/{self.meeting.pk}/delete/')
