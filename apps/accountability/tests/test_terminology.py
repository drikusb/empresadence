from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accountability.models import AccountabilityNode, AccountabilityRole
from apps.accounts.models import Membership, Organization, OrganizationDomain

HOSTS = ['testserver', 'mercury.example.test', 'silavapi.example.test']
MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

RENAMED = {
    'seat': 'Role', 'seats': 'Roles',
    'accountability_chart': 'Org Chart', 'accountability_charts': 'Org Charts',
}


@override_settings(ALLOWED_HOSTS=HOSTS)
class AccountabilityTerminologyTest(TestCase):
    """The chart pages call a Seat whatever the organisation calls it."""

    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', terminology=RENAMED)
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        self.silavapi = Organization.objects.create(name='Silavapi Org')
        OrganizationDomain.objects.create(organization=self.silavapi, hostname=SILAVAPI)
        self.user = User.objects.create_user(username='chartuser', password='pw')
        for org in (self.mercury, self.silavapi):
            Membership.objects.create(user=self.user, organization=org)
        self.client.force_login(self.user)

    def node(self, org, name, parent=None):
        return AccountabilityNode.objects.create(organization=org, name=name, parent=parent)

    def test_chart_uses_the_organisations_words(self):
        self.node(self.mercury, 'Integrator')
        resp = self.client.get('/accountability/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Org Chart — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Org Chart\n        </h1>')
        self.assertContains(resp, 'Add Role')
        self.assertContains(resp, 'title="Add child role"')
        self.assertContains(resp, 'title="Edit role"')
        self.assertContains(resp, 'title="Remove role"')
        self.assertContains(resp, 'add a child role beneath a node')
        self.assertContains(resp, 'Dashed border = vacant role.')
        self.assertNotContains(resp, 'Seat')
        self.assertNotContains(resp, 'seat')

    def test_empty_chart_uses_the_organisations_words(self):
        resp = self.client.get('/accountability/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'No roles yet')
        self.assertContains(resp, 'Start by adding the top-level roles')
        self.assertContains(resp, 'Add First Role')

    def test_node_form_uses_the_organisations_words(self):
        resp = self.client.get('/accountability/nodes/add/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Add Role — Org Chart — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Add Role</h1>')
        self.assertContains(resp, 'Role Name')
        self.assertContains(resp, 'Leave blank for an unfilled / vacant role.')
        self.assertNotContains(resp, 'Seat Name')
        self.assertNotContains(resp, 'Add Seat')
        # The node_type choice labels are model choices and stay as they are.
        self.assertContains(resp, '<option value="seat" selected>Seat</option>', html=True)

    def test_node_delete_page_counts_children_in_the_organisations_word(self):
        parent = self.node(self.mercury, 'Sales')
        self.node(self.mercury, 'SDR', parent=parent)
        resp = self.client.get(f'/accountability/nodes/{parent.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Remove Role — Org Chart — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Remove Role</h1>')
        self.assertContains(resp, 'This role and <strong>all child roles beneath it</strong>')
        self.assertContains(resp, '1 child role</strong>')
        self.assertContains(resp, 'Yes, Remove Role')
        self.node(self.mercury, 'AE', parent=parent)
        resp = self.client.get(f'/accountability/nodes/{parent.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '2 child roles</strong>')

    def test_role_pages_name_the_seat_in_the_organisations_word(self):
        node = self.node(self.mercury, 'Integrator')
        resp = self.client.get(f'/accountability/nodes/{node.pk}/roles/add/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'owned by the person in this role.')
        role = AccountabilityRole.objects.create(node=node, description='Run the meeting')
        resp = self.client.get(f'/accountability/roles/{role.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Role: <strong>Integrator</strong>')

    def test_default_host_shows_the_eos_words(self):
        resp = self.client.get('/accountability/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, '<title>Accountability Chart — Silavapi Org</title>', html=True)
        self.assertContains(resp, 'No seats yet')
        self.assertContains(resp, 'Add First Seat')
        self.assertNotContains(resp, 'Role')
        resp = self.client.get('/accountability/nodes/add/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'Add Seat</h1>')
        self.assertContains(resp, 'Seat Name')
