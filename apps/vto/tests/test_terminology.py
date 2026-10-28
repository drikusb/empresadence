from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.vto.models import VTO, VTOCoreValue

METRICS_HOST = 'metrics.example.test'
PLAIN_HOST = 'plain.example.test'

# 'vto' is distinct from the shipped default ('Vision Plan') so the
# default-host test below can tell "customised" apart from "just happens to
# match the default."
METRICS_WORDS = {
    'scorecard': 'Metrics Board', 'scorecards': 'Metrics Boards',
    'core_value': 'Value', 'core_values': 'Values',
    'rock': 'Priority', 'rocks': 'Priorities',
    'issue': 'Blocker', 'issues': 'Blockers',
    'vto': 'Blueprint',
}


@override_settings(ALLOWED_HOSTS=['testserver', METRICS_HOST, PLAIN_HOST])
class VTOTerminologyTest(TestCase):
    """The VTO pages and messages use the organisation's own words."""

    def setUp(self):
        self.metrics_org = Organization.objects.create(name='Metrics Org', terminology=METRICS_WORDS)
        self.plain_org = Organization.objects.create(name='Plain Org')
        OrganizationDomain.objects.create(organization=self.metrics_org, hostname=METRICS_HOST)
        OrganizationDomain.objects.create(organization=self.plain_org, hostname=PLAIN_HOST)

        self.user = User.objects.create_user(username='vtoterms', password='pw')
        Membership.objects.create(user=self.user, organization=self.metrics_org)
        Membership.objects.create(user=self.user, organization=self.plain_org)
        team = Team.objects.create(organization=self.metrics_org, name='Leadership')
        self.user.profile.teams.add(team)
        self.client.force_login(self.user)

    def test_detail_headings_use_the_organisation_words(self):
        resp = self.client.get('/vto/', HTTP_HOST=METRICS_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Blueprint — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Blueprint</h1>')
        self.assertContains(resp, '<span class="fw-semibold small">Values</span>', html=False)
        self.assertContains(resp, 'No values yet.')
        self.assertContains(resp, 'Company Priorities</span>', html=False)
        self.assertContains(resp, 'live from Priorities module')
        self.assertContains(resp, 'No company-wide Priorities for')
        self.assertContains(resp, 'Company Blockers List</span>', html=False)
        self.assertContains(resp, 'Long-term strategic blockers · live from Blockers module')
        self.assertNotContains(resp, 'Vision / Traction Organizer')
        self.assertNotContains(resp, 'Core Values')
        self.assertNotContains(resp, 'Company Rocks')
        self.assertNotContains(resp, 'Company Issues')

    def test_print_view_uses_the_organisation_words(self):
        resp = self.client.get('/vto/print/', HTTP_HOST=METRICS_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Blueprint — Metrics Org — Print</title>', html=True)
        self.assertContains(resp, '<div class="text-muted small">Blueprint</div>', html=False)
        self.assertContains(resp, '<span class="fw-semibold small">Values</span>', html=False)
        self.assertContains(resp, '<span class="fw-semibold small">Company Priorities — ', html=False)
        self.assertContains(resp, 'No company-wide Priorities for')
        self.assertContains(resp, '<span class="fw-semibold small">Company Blockers List (Long-Term)</span>', html=False)
        self.assertNotContains(resp, 'Core Values')
        self.assertNotContains(resp, 'Company Rocks')
        self.assertNotContains(resp, 'Company Issues')

    def test_core_value_form_uses_the_organisation_words(self):
        resp = self.client.get('/vto/core-values/add/', HTTP_HOST=METRICS_HOST)
        self.assertContains(resp, '<title>Add Value — Blueprint — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Add Value</h1>')
        self.assertContains(resp, '<div class="text-muted small">Blueprint</div>', html=False)
        self.assertContains(resp, 'Value <span class="text-danger">*</span>')
        self.assertNotContains(resp, 'Core Value')

    def test_section_edit_title_uses_the_organisation_word(self):
        resp = self.client.get('/vto/edit/ten_year_target/', HTTP_HOST=METRICS_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Edit 10-Year Target — Blueprint — Metrics Org</title>', html=True)

    def test_add_core_value_message_uses_the_organisation_word(self):
        resp = self.client.post(
            '/vto/core-values/add/',
            {'name': 'Integrity', 'description': 'Do what you say.', 'order': 1},
            HTTP_HOST=METRICS_HOST, follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Value &quot;Integrity&quot; added.')
        vto = VTO.for_org(self.metrics_org)
        self.assertTrue(vto.core_values.filter(name='Integrity').exists())

    def test_edit_and_remove_core_value_use_the_organisation_words(self):
        cv = VTOCoreValue.objects.create(vto=VTO.for_org(self.metrics_org), name='Integrity')

        resp = self.client.post(
            f'/vto/core-values/{cv.pk}/edit/',
            {'name': 'Candour', 'description': '', 'order': 1},
            HTTP_HOST=METRICS_HOST, follow=True,
        )
        self.assertContains(resp, 'Value &quot;Candour&quot; updated.')

        resp = self.client.get(f'/vto/core-values/{cv.pk}/delete/', HTTP_HOST=METRICS_HOST)
        self.assertContains(resp, '<title>Remove Value — Blueprint — Metrics Org</title>', html=True)
        self.assertContains(resp, 'Remove Value</h1>')
        self.assertContains(resp, 'This value will be permanently removed from your Blueprint.')

        resp = self.client.post(f'/vto/core-values/{cv.pk}/delete/', HTTP_HOST=METRICS_HOST, follow=True)
        self.assertContains(resp, 'Value &quot;Candour&quot; removed.')

    def test_default_host_shows_the_generic_words(self):
        resp = self.client.get('/vto/', HTTP_HOST=PLAIN_HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Vision Plan — Plain Org</title>', html=True)
        self.assertContains(resp, 'Vision Plan</h1>')
        self.assertContains(resp, '<span class="fw-semibold small">Values</span>', html=False)
        self.assertContains(resp, 'No values yet.')
        self.assertContains(resp, 'Company Priorities</span>', html=False)
        self.assertContains(resp, 'Company Blockers List</span>', html=False)
        self.assertNotContains(resp, 'Blueprint')

        resp = self.client.post(
            '/vto/core-values/add/',
            {'name': 'Integrity', 'description': '', 'order': 1},
            HTTP_HOST=PLAIN_HOST, follow=True,
        )
        self.assertContains(resp, 'Value &quot;Integrity&quot; added.')
