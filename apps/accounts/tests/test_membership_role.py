from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization
from apps.audit.models import AuditEvent


class MembershipRoleUpdateTest(TestCase):
    """An Admin may change a member's role from the Users page (#136)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Role Org')
        self.admin = User.objects.create_user(username='admin', password='pw')
        self.other_admin = User.objects.create_user(username='otheradmin', password='pw')
        self.member = User.objects.create_user(username='member', password='pw')
        self.admin_membership = Membership.objects.create(
            user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN
        )
        self.other_admin_membership = Membership.objects.create(
            user=self.other_admin, organization=self.org, role=Membership.ROLE_ADMIN
        )
        self.member_membership = Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.ROLE_MEMBER
        )
        self.client.force_login(self.admin)

    def _url(self, membership):
        return f'/accounts/users/memberships/{membership.pk}/role/'

    def test_admin_can_promote_a_member_to_leader(self):
        resp = self.client.post(self._url(self.member_membership), {'role': Membership.ROLE_LEADER})
        self.assertRedirects(resp, '/accounts/users/')
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, Membership.ROLE_LEADER)

    def test_role_change_is_recorded_in_the_audit_log(self):
        self.client.post(self._url(self.member_membership), {'role': Membership.ROLE_ADMIN})
        event = AuditEvent.objects.get(action='membership.role_changed')
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.details['old_role'], Membership.ROLE_MEMBER)
        self.assertEqual(event.details['new_role'], Membership.ROLE_ADMIN)

    def test_cannot_demote_the_only_admin(self):
        self.other_admin_membership.delete()
        resp = self.client.post(self._url(self.admin_membership), {'role': Membership.ROLE_MEMBER})
        self.assertRedirects(resp, '/accounts/users/')
        self.admin_membership.refresh_from_db()
        self.assertEqual(self.admin_membership.role, Membership.ROLE_ADMIN)

    def test_can_demote_an_admin_when_another_admin_remains(self):
        resp = self.client.post(self._url(self.admin_membership), {'role': Membership.ROLE_MEMBER})
        self.assertRedirects(resp, '/accounts/users/')
        self.admin_membership.refresh_from_db()
        self.assertEqual(self.admin_membership.role, Membership.ROLE_MEMBER)

    def test_invalid_role_is_rejected(self):
        resp = self.client.post(self._url(self.member_membership), {'role': 'wizard'})
        self.assertRedirects(resp, '/accounts/users/')
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, Membership.ROLE_MEMBER)

    def test_non_admin_cannot_change_roles(self):
        self.client.force_login(self.member)
        resp = self.client.post(self._url(self.other_admin_membership), {'role': Membership.ROLE_MEMBER})
        self.assertEqual(resp.status_code, 403)

    def test_cannot_change_a_membership_in_another_organisation(self):
        other_org = Organization.objects.create(name='Other Org')
        outsider = User.objects.create_user(username='outsider', password='pw')
        outsider_membership = Membership.objects.create(
            user=outsider, organization=other_org, role=Membership.ROLE_MEMBER
        )
        resp = self.client.post(self._url(outsider_membership), {'role': Membership.ROLE_ADMIN})
        self.assertEqual(resp.status_code, 404)
