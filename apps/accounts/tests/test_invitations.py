from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import (
    Membership, Organization, OrganizationDomain, OrganizationInvitation, Team,
)
from apps.accounts.scoping import SESSION_ORG_KEY
from apps.audit.models import AuditEvent

PINNED = 'beta.example.test'


class InvitationTestCase(TestCase):
    """Dana is a member of Alpha. Beta's admin wants her in Beta as well."""

    def setUp(self):
        self.alpha = Organization.objects.create(name='Alpha Org')
        self.beta = Organization.objects.create(name='Beta Org')
        self.beta_team = Team.objects.create(organization=self.beta, name='Beta Team')
        self.alpha_team = Team.objects.create(organization=self.alpha, name='Alpha Team')
        self.admin = User.objects.create_user(
            username='betaadmin', email='admin@beta.example', password='pw',
            first_name='Bea', last_name='Admin',
        )
        Membership.objects.create(user=self.admin, organization=self.beta, role=Membership.ROLE_ADMIN)
        self.dana = User.objects.create_user(username='dana', email='dana@example.com', password='pw')
        Membership.objects.create(user=self.dana, organization=self.alpha)

    def invite(self, **overrides):
        data = {
            'username': 'somebody', 'email': 'dana@example.com',
            'role': Membership.ROLE_LEADER, 'teams': [self.beta_team.pk],
        }
        data.update(overrides)
        return self.client.post('/users/invite/', data)

    def invitation(self):
        return OrganizationInvitation.objects.get(organization=self.beta, user=self.dana)

    def make_invitation(self, **fields):
        invitation = OrganizationInvitation.objects.create(
            organization=self.beta, user=self.dana, role=Membership.ROLE_LEADER,
            invited_by=self.admin, **fields,
        )
        invitation.teams.add(self.beta_team)
        return invitation


class InviteExistingUserTest(InvitationTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_existing_email_gets_an_invitation_not_a_membership_or_a_new_account(self):
        users_before = User.objects.count()
        resp = self.invite()
        self.assertRedirects(resp, '/users/')
        self.assertEqual(User.objects.count(), users_before)
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())
        self.assertFalse(self.dana.profile.teams.filter(pk=self.beta_team.pk).exists())
        invitation = self.invitation()
        self.assertEqual(invitation.role, Membership.ROLE_LEADER)
        self.assertEqual(list(invitation.teams.all()), [self.beta_team])
        self.assertEqual(invitation.invited_by, self.admin)
        self.assertTrue(invitation.can_be_answered)

    def test_email_match_ignores_case(self):
        self.invite(email='DANA@Example.com')
        self.assertEqual(self.invitation().user, self.dana)

    def test_invitation_email_links_to_the_accept_page_and_sets_no_password(self):
        self.invite()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['dana@example.com'])
        self.assertIn('Beta Org', message.subject)
        self.assertIn(self.invitation().get_absolute_url(), message.body)
        self.assertIn('Bea Admin', message.body)
        self.assertNotIn('/reset/', message.body)

    def test_sending_is_recorded_in_the_audit_log(self):
        self.invite()
        event = AuditEvent.objects.get(action='invitation.sent')
        self.assertEqual(event.organization, self.beta)
        self.assertEqual(event.actor, self.admin)

    def test_username_and_matching_email_pick_that_account(self):
        twin = User.objects.create_user(username='dana2', email='dana@example.com', password='pw')
        self.invite(username='dana2')
        self.assertEqual(OrganizationInvitation.objects.get().user, twin)

    def test_shared_email_without_a_username_match_is_refused(self):
        User.objects.create_user(username='dana2', email='dana@example.com', password='pw')
        resp = self.invite()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'More than one account uses this email address')
        self.assertFalse(OrganizationInvitation.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_username_with_another_email_is_still_refused(self):
        resp = self.invite(username='dana', email='someone-else@example.com')
        self.assertContains(resp, 'A user with that username already exists.')
        self.assertFalse(OrganizationInvitation.objects.exists())
        self.assertFalse(User.objects.filter(email='someone-else@example.com').exists())

    def test_inactive_account_is_not_invited(self):
        self.dana.is_active = False
        self.dana.save()
        self.invite(username='dana')
        self.assertFalse(OrganizationInvitation.objects.exists())

    def test_someone_already_in_the_organisation_is_refused(self):
        Membership.objects.create(user=self.dana, organization=self.beta)
        resp = self.invite()
        self.assertContains(resp, 'This person is already in Beta Org.')
        self.assertFalse(OrganizationInvitation.objects.exists())

    def test_inviting_again_updates_the_open_invitation(self):
        self.invite()
        first = self.invitation()
        self.invite(role=Membership.ROLE_MEMBER, teams=[])
        again = self.invitation()
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.role, Membership.ROLE_MEMBER)
        self.assertEqual(again.teams.count(), 0)
        self.assertEqual(len(mail.outbox), 2)

    def test_new_email_still_creates_an_account_and_membership(self):
        resp = self.invite(username='newbie', email='newbie@example.com')
        self.assertRedirects(resp, '/users/')
        newbie = User.objects.get(username='newbie')
        self.assertTrue(Membership.objects.filter(user=newbie, organization=self.beta).exists())
        self.assertFalse(OrganizationInvitation.objects.exists())
        self.assertIn('/reset/', mail.outbox[0].body)

    def test_non_admin_cannot_invite_an_existing_user(self):
        member = User.objects.create_user(username='plain', password='pw')
        Membership.objects.create(user=member, organization=self.beta)
        self.client.force_login(member)
        self.assertEqual(self.invite().status_code, 403)
        self.assertFalse(OrganizationInvitation.objects.exists())

    def test_second_open_invitation_for_the_same_person_is_rejected_by_the_database(self):
        self.make_invitation()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_invitation()

    def test_answered_invitation_does_not_block_a_new_one(self):
        self.make_invitation(declined_at=timezone.now())
        self.invite()
        self.assertEqual(OrganizationInvitation.objects.count(), 2)


class PendingInvitationsListTest(InvitationTestCase):
    def setUp(self):
        super().setUp()
        self.dana.first_name, self.dana.last_name = 'Dana', 'Private'
        self.dana.save()
        self.invitation_obj = self.make_invitation()
        self.client.force_login(self.admin)

    def test_users_page_lists_the_email_but_not_the_name(self):
        resp = self.client.get('/users/')
        self.assertContains(resp, 'Pending invitations')
        self.assertContains(resp, 'dana@example.com')
        self.assertNotContains(resp, 'Dana Private')

    def test_answered_and_withdrawn_invitations_are_not_listed(self):
        self.invitation_obj.withdrawn_at = timezone.now()
        self.invitation_obj.save()
        self.assertNotContains(self.client.get('/users/'), 'Pending invitations')

    def test_other_organisations_invitations_are_not_listed(self):
        gamma = Organization.objects.create(name='Gamma Org')
        outsider = User.objects.create_user(username='gammaadmin', password='pw')
        Membership.objects.create(user=outsider, organization=gamma, role=Membership.ROLE_ADMIN)
        self.client.force_login(outsider)
        self.assertNotContains(self.client.get('/users/'), 'dana@example.com')

    def test_resend_extends_the_expiry_and_sends_the_email_again(self):
        OrganizationInvitation.objects.filter(pk=self.invitation_obj.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        resp = self.client.post(f'/users/invitations/{self.invitation_obj.pk}/resend/')
        self.assertRedirects(resp, '/users/')
        self.assertTrue(self.invitation().can_be_answered)
        self.assertEqual(len(mail.outbox), 1)

    def test_withdraw_closes_the_invitation_and_is_audited(self):
        self.client.post(f'/users/invitations/{self.invitation_obj.pk}/withdraw/')
        self.assertIsNotNone(self.invitation().withdrawn_at)
        self.assertTrue(AuditEvent.objects.filter(action='invitation.withdrawn').exists())

    def test_admin_of_another_organisation_cannot_resend_or_withdraw(self):
        gamma = Organization.objects.create(name='Gamma Org')
        outsider = User.objects.create_user(username='gammaadmin', password='pw')
        Membership.objects.create(user=outsider, organization=gamma, role=Membership.ROLE_ADMIN)
        self.client.force_login(outsider)
        for action in ('resend', 'withdraw'):
            resp = self.client.post(f'/users/invitations/{self.invitation_obj.pk}/{action}/')
            self.assertEqual(resp.status_code, 404)
        self.assertIsNone(self.invitation().withdrawn_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_plain_member_cannot_resend_or_withdraw(self):
        member = User.objects.create_user(username='plain', password='pw')
        Membership.objects.create(user=member, organization=self.beta)
        self.client.force_login(member)
        for action in ('resend', 'withdraw'):
            resp = self.client.post(f'/users/invitations/{self.invitation_obj.pk}/{action}/')
            self.assertEqual(resp.status_code, 403)


class RespondToInvitationTest(InvitationTestCase):
    def setUp(self):
        super().setUp()
        self.invitation_obj = self.make_invitation()
        self.url = self.invitation_obj.get_absolute_url()
        self.client.force_login(self.dana)

    def test_page_names_the_organisation_role_and_inviter(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'Join Beta Org?')
        self.assertContains(resp, 'Team Leader')
        self.assertContains(resp, 'Bea Admin')
        self.assertNotContains(resp, 'Beta Team')

    def test_anonymous_visitor_is_sent_to_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])

    def test_another_account_gets_404_even_with_the_right_link(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'action': 'accept'}).status_code, 404)
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())
        self.assertIsNone(self.invitation().accepted_at)

    def test_wrong_token_gets_404(self):
        bad = f'/accounts/invitations/{self.invitation_obj.pk}/{"0" * 32}/'
        self.assertEqual(self.client.get(bad).status_code, 404)
        self.assertEqual(self.client.post(bad, {'action': 'accept'}).status_code, 404)
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())

    def test_accept_creates_the_membership_and_adds_the_teams(self):
        resp = self.client.post(self.url, {'action': 'accept'})
        self.assertRedirects(resp, '/', fetch_redirect_response=False)
        membership = Membership.objects.get(user=self.dana, organization=self.beta)
        self.assertEqual(membership.role, Membership.ROLE_LEADER)
        self.assertTrue(self.dana.profile.teams.filter(pk=self.beta_team.pk).exists())
        self.assertIsNotNone(self.invitation().accepted_at)
        self.assertEqual(self.client.session[SESSION_ORG_KEY], self.beta.pk)
        event = AuditEvent.objects.get(action='invitation.accepted')
        self.assertEqual(event.actor, self.dana)
        self.assertEqual(event.organization, self.beta)

    def test_accept_skips_a_team_that_moved_to_another_organisation(self):
        self.invitation_obj.teams.add(self.alpha_team)
        Membership.objects.filter(user=self.dana, organization=self.alpha).delete()
        self.client.post(self.url, {'action': 'accept'})
        self.assertFalse(self.dana.profile.teams.filter(pk=self.alpha_team.pk).exists())

    def test_decline_adds_nothing_and_is_audited(self):
        resp = self.client.post(self.url, {'action': 'decline'})
        self.assertRedirects(resp, self.url)
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())
        self.assertIsNotNone(self.invitation().declined_at)
        self.assertTrue(AuditEvent.objects.filter(action='invitation.declined').exists())
        self.assertContains(self.client.get(self.url), 'Invitation declined')

    def test_expired_invitation_cannot_be_accepted(self):
        OrganizationInvitation.objects.filter(pk=self.invitation_obj.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        resp = self.client.post(self.url, {'action': 'accept'})
        self.assertContains(resp, 'no longer open')
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())

    def test_withdrawn_invitation_cannot_be_accepted(self):
        OrganizationInvitation.objects.filter(pk=self.invitation_obj.pk).update(
            withdrawn_at=timezone.now()
        )
        resp = self.client.post(self.url, {'action': 'accept'})
        self.assertContains(resp, 'no longer open')
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())

    def test_declined_invitation_cannot_be_accepted_afterwards(self):
        self.client.post(self.url, {'action': 'decline'})
        self.client.post(self.url, {'action': 'accept'})
        self.assertFalse(Membership.objects.filter(user=self.dana, organization=self.beta).exists())

    def test_profile_lists_an_open_invitation(self):
        resp = self.client.get('/profile/')
        self.assertContains(resp, self.url)
        self.assertContains(resp, 'Beta Org')

    def test_profile_hides_an_expired_invitation(self):
        OrganizationInvitation.objects.filter(pk=self.invitation_obj.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertNotContains(self.client.get('/profile/'), self.url)

    @override_settings(INVITATION_EXPIRY_DAYS=3)
    def test_expiry_follows_the_setting(self):
        self.invitation_obj.delete()
        fresh = self.make_invitation()
        remaining = fresh.expires_at - timezone.now()
        self.assertTrue(timedelta(days=2, hours=23) < remaining <= timedelta(days=3))


@override_settings(ALLOWED_HOSTS=[PINNED, 'testserver'])
class InvitationOnPinnedHostTest(InvitationTestCase):
    """Beta has its own hostname, where a signed-in non-member normally gets 403."""

    def setUp(self):
        super().setUp()
        OrganizationDomain.objects.create(organization=self.beta, hostname=PINNED, is_primary=True)
        self.invitation_obj = self.make_invitation()
        self.url = self.invitation_obj.get_absolute_url()
        self.client.force_login(self.dana)

    def test_non_member_is_still_locked_out_of_the_rest_of_the_host(self):
        self.assertEqual(self.client.get('/', HTTP_HOST=PINNED).status_code, 403)

    def test_invited_person_can_open_and_accept_on_the_pinned_host(self):
        self.assertEqual(self.client.get(self.url, HTTP_HOST=PINNED).status_code, 200)
        resp = self.client.post(self.url, {'action': 'accept'}, HTTP_HOST=PINNED)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.get('/', HTTP_HOST=PINNED).status_code, 200)

    def test_declining_on_the_pinned_host_lands_on_a_page_they_can_see(self):
        resp = self.client.post(self.url, {'action': 'decline'}, HTTP_HOST=PINNED, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invitation declined')

    def test_email_link_uses_the_organisations_own_hostname(self):
        self.invitation_obj.delete()
        self.client.force_login(self.admin)
        self.invite()
        self.assertIn(f'://{PINNED}{self.invitation().get_absolute_url()}', mail.outbox[0].body)
