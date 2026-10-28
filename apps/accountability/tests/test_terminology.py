from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accountability.models import AccountabilityNode, AccountabilityRole
from apps.accounts.models import Membership, Organization, OrganizationDomain

HOSTS = ['testserver', 'mercury.example.test', 'silavapi.example.test']
MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

# Distinct from the shipped defaults ('Role', 'Org Chart') so the default-host
# test below can tell "customised" apart from "just happens to match the default."
RENAMED = {
    'seat': 'Position', 'seats': 'Positions',
    'accountability_chart': 'Team Map', 'accountability_charts': 'Team Maps',
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
        self.assertContains(resp, '<title>Team Map — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Team Map\n        </h1>')
        self.assertContains(resp, 'Add Position')
        self.assertContains(resp, 'title="Add child position"')
        self.assertContains(resp, 'title="Edit position"')
        self.assertContains(resp, 'title="Remove position"')
        self.assertContains(resp, 'add a child position beneath a node')
        self.assertContains(resp, 'Dashed border = vacant position.')
        self.assertNotContains(resp, 'Seat')
        self.assertNotContains(resp, 'seat')

    def test_empty_chart_uses_the_organisations_words(self):
        resp = self.client.get('/accountability/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'No positions yet')
        self.assertContains(resp, 'Start by adding the top-level positions')
        self.assertContains(resp, 'Add First Position')

    def test_node_form_uses_the_organisations_words(self):
        resp = self.client.get('/accountability/nodes/add/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Add Position — Team Map — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Add Position</h1>')
        self.assertContains(resp, 'Position Name')
        self.assertContains(resp, 'Leave blank for an unfilled / vacant position.')
        self.assertNotContains(resp, 'Seat Name')
        self.assertNotContains(resp, 'Add Seat')
        # The node_type choice labels are model choices and stay as they are.
        self.assertContains(resp, '<option value="seat" selected>Seat</option>', html=True)

    def test_node_delete_page_counts_children_in_the_organisations_word(self):
        parent = self.node(self.mercury, 'Sales')
        self.node(self.mercury, 'SDR', parent=parent)
        resp = self.client.get(f'/accountability/nodes/{parent.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '<title>Remove Position — Team Map — Mercury Org</title>', html=True)
        self.assertContains(resp, 'Remove Position</h1>')
        self.assertContains(resp, 'This position and <strong>all child positions beneath it</strong>')
        self.assertContains(resp, '1 child position</strong>')
        self.assertContains(resp, 'Yes, Remove Position')
        self.node(self.mercury, 'AE', parent=parent)
        resp = self.client.get(f'/accountability/nodes/{parent.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, '2 child positions</strong>')

    def test_role_pages_name_the_seat_in_the_organisations_word(self):
        node = self.node(self.mercury, 'Integrator')
        resp = self.client.get(f'/accountability/nodes/{node.pk}/roles/add/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'owned by the person in this position.')
        role = AccountabilityRole.objects.create(node=node, description='Run the meeting')
        resp = self.client.get(f'/accountability/roles/{role.pk}/delete/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Position: <strong>Integrator</strong>')

    def test_default_host_shows_the_generic_words(self):
        resp = self.client.get('/accountability/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, '<title>Org Chart — Silavapi Org</title>', html=True)
        self.assertContains(resp, 'No roles yet')
        self.assertContains(resp, 'Add First Role')
        self.assertNotContains(resp, 'Position')
        resp = self.client.get('/accountability/nodes/add/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'Add Role</h1>')
        self.assertContains(resp, 'Role Name')
