import re

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.accounts.tests.test_isolation import build_org, pk_urls

MERCURY = 'mercury.example.test'
TITLE = re.compile(r'<title>(.*?)</title>', re.DOTALL)


def page_title(resp):
    match = TITLE.search(resp.content.decode())
    return match.group(1).strip() if match else None


@override_settings(ALLOWED_HOSTS=['testserver', MERCURY])
class BrandedPageTitleTest(TestCase):
    """Every page's <title> ends with the organisation's display name, not the default brand."""

    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', display_name='Mercury Consortium')
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        team = Team.objects.create(organization=self.mercury, name='Mercury Team')
        self.user = User.objects.create_user(username='mercurymember', password='pw')
        Membership.objects.create(user=self.user, organization=self.mercury)
        self.user.profile.teams.add(team)

    def assertBrandedTitle(self, resp, path):
        self.assertEqual(resp.status_code, 200, path)
        title = page_title(resp)
        self.assertIsNotNone(title, f'{path} has no <title>')
        self.assertTrue(title.endswith(' — Mercury Consortium'), f'{path}: {title!r}')
        self.assertFalse(title.startswith(' —'), f'{path} has an empty page title: {title!r}')
        self.assertNotIn('EOS App', title, path)

    def test_logged_in_pages_across_apps(self):
        self.client.force_login(self.user)
        for path in ['/', '/rocks/', '/issues/', '/todos/', '/scorecards/', '/vto/', '/meetings/', '/accountability/']:
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_HOST=MERCURY)
                self.assertBrandedTitle(resp, path)

    def test_specific_titles(self):
        self.client.force_login(self.user)
        for path, title in [
            ('/', 'Dashboard — Mercury Consortium'),
            ('/issues/', 'Blockers — Mercury Consortium'),
            ('/todos/', 'Actions — Mercury Consortium'),
            ('/scorecards/', 'Metrics Boards — Mercury Consortium'),
            ('/meetings/', 'Weekly Meetings — Mercury Consortium'),
            ('/vto/', 'Vision Plan — Mercury Consortium'),
        ]:
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_HOST=MERCURY)
                self.assertContains(resp, f'<title>{title}</title>', html=True)

    def test_anonymous_pages(self):
        for path in ['/accounts/login/', '/accounts/password_reset/done/', '/accounts/reset/done/']:
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_HOST=MERCURY)
                self.assertBrandedTitle(resp, path)

    def test_password_reset_titles(self):
        for path, title in [
            ('/accounts/password_reset/done/', 'Check Your Email — Mercury Consortium'),
            ('/accounts/reset/done/', 'Password Reset Complete — Mercury Consortium'),
        ]:
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_HOST=MERCURY)
                self.assertContains(resp, f'<title>{title}</title>', html=True)


@override_settings(DEFAULT_BRAND_NAME='Probe Brand')
class DefaultBrandNeverLeaksTest(TestCase):
    """No template still hard-codes the old "EOS App" suffix once the brand name is configurable."""

    LIST_PATHS = [
        '/', '/rocks/', '/rocks/new/', '/rocks/archive/', '/issues/', '/issues/new/',
        '/todos/', '/todos/new/', '/scorecards/', '/scorecards/new/', '/vto/',
        '/vto/core-values/add/', '/meetings/', '/meetings/create/', '/accountability/',
        '/accountability/nodes/add/', '/teams/', '/teams/new/', '/org/', '/org/settings/',
        '/profile/', '/profile/edit/', '/users/', '/users/invite/',
        '/notifications/preferences/', '/search/?q=probe', '/accounts/2fa/setup/', '/org/audit/',
    ]

    def setUp(self):
        self.fixture = build_org('Probe')
        self.client.force_login(self.fixture['user'])

    def test_pk_pages_never_show_the_old_name(self):
        gets, _posts = pk_urls(self.fixture)
        for url in gets:
            with self.subTest(url=url):
                resp = self.client.get(url)
                if resp.status_code != 200 or not resp['Content-Type'].startswith('text/html'):
                    continue
                self.assertNotIn('EOS App', resp.content.decode())
                self.assertTrue(page_title(resp).endswith(' — Probe Org'), page_title(resp))

    def test_list_pages_never_show_the_old_name(self):
        for url in self.LIST_PATHS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                if resp.status_code != 200 or not resp['Content-Type'].startswith('text/html'):
                    continue
                self.assertNotIn('EOS App', resp.content.decode())
                self.assertTrue(page_title(resp).endswith(' — Probe Org'), page_title(resp))

    def test_anonymous_pages_use_the_configured_default(self):
        self.client.logout()
        for url in ['/accounts/login/', '/accounts/password_reset/done/', '/accounts/reset/done/']:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn('EOS App', resp.content.decode())
                self.assertTrue(page_title(resp).endswith(' — Probe Brand'), page_title(resp))
