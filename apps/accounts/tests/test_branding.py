from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.branding import Brand, brand_for, default_brand
from apps.accounts.forms import OrganizationSettingsForm
from apps.accounts.models import Membership, Organization, OrganizationDomain

HOSTS = ['testserver', 'mercury.example.test', 'silavapi.example.test']
MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

TEAL = '#1f6f8b'


class BrandTest(TestCase):
    def test_defaults(self):
        brand = Brand(name='Acme')
        self.assertEqual(brand.navbar_classes, 'navbar-dark bg-dark')
        self.assertEqual(brand.primary_rgb, '')
        self.assertEqual(brand.primary_hover, '')
        self.assertEqual(brand.primary_active, '')
        self.assertEqual(brand.tagline, '')

    def test_primary_rgb(self):
        self.assertEqual(Brand(name='x', primary_color='#0d6efd').primary_rgb, '13, 110, 253')
        self.assertEqual(Brand(name='x', primary_color='#FFFFFF').primary_rgb, '255, 255, 255')

    def test_shading_darkens_by_15_and_20_percent(self):
        brand = Brand(name='x', primary_color='#ff8000')
        self.assertEqual(brand.primary_hover, '#d96d00')
        self.assertEqual(brand.primary_active, '#cc6600')
        self.assertEqual(Brand(name='x', primary_color='#000000').primary_hover, '#000000')

    def test_navbar_classes(self):
        self.assertEqual(Brand(name='x', navbar_style='light').navbar_classes, 'navbar-light bg-light border-bottom')
        self.assertEqual(Brand(name='x', navbar_style='primary').navbar_classes, 'navbar-dark bg-primary')
        self.assertEqual(Brand(name='x', navbar_style='nonsense').navbar_classes, 'navbar-dark bg-dark')

    @override_settings(DEFAULT_BRAND_NAME='My EOS')
    def test_default_brand_uses_the_setting(self):
        self.assertEqual(default_brand().name, 'My EOS')
        self.assertEqual(default_brand().tagline, 'Operating cadence for leadership teams')
        self.assertEqual(brand_for(None), default_brand())

    def test_brand_for_organisation(self):
        org = Organization.objects.create(
            name='Mercury Org', display_name='Mercury Consortium', tagline='Onwards',
            primary_color=TEAL, navbar_style='primary', support_email='help@mercury.test',
        )
        brand = brand_for(org)
        self.assertEqual(brand.name, 'Mercury Consortium')
        self.assertEqual(brand.tagline, 'Onwards')
        self.assertEqual(brand.primary_color, TEAL)
        self.assertEqual(brand.navbar_style, 'primary')
        self.assertEqual(brand.support_email, 'help@mercury.test')
        self.assertEqual(brand.logo_url, '')
        self.assertEqual(brand.favicon_url, '')


class OrganizationBrandingModelTest(TestCase):
    def test_display_name_falls_back_to_name(self):
        org = Organization(name='Mercury Org')
        self.assertEqual(org.get_display_name(), 'Mercury Org')
        org.display_name = 'Mercury Consortium'
        self.assertEqual(org.get_display_name(), 'Mercury Consortium')

    def test_primary_color_must_be_a_six_digit_hex(self):
        for bad in ['red', '#fff', '0d6efd', '#0d6efd0', '#ggg000']:
            with self.subTest(color=bad):
                with self.assertRaises(ValidationError):
                    Organization(name='x', primary_color=bad).full_clean()
        for good in ['', '#0d6efd', '#ABCDEF']:
            with self.subTest(color=good):
                Organization(name='x', primary_color=good).full_clean()

    def test_favicon_extension_is_checked(self):
        org = Organization(name='x', favicon=SimpleUploadedFile('icon.gif', b'x'))
        with self.assertRaises(ValidationError):
            org.full_clean()


class OrganizationSettingsFormTest(TestCase):
    def test_bootstrap_blue_counts_as_no_colour(self):
        form = OrganizationSettingsForm(data={'name': 'x', 'primary_color': '#0D6EFD', 'navbar_style': 'dark'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['primary_color'], '')

    def test_other_colours_are_kept_lowercase(self):
        form = OrganizationSettingsForm(data={'name': 'x', 'primary_color': '#1F6F8B', 'navbar_style': 'dark'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['primary_color'], TEAL)

    def test_colour_input_starts_on_bootstrap_blue_when_unset(self):
        form = OrganizationSettingsForm(instance=Organization(name='x'))
        self.assertEqual(form['primary_color'].value(), '#0d6efd')


class OrgSettingsViewTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Settings Org')
        self.admin = User.objects.create_user(username='orgadmin', password='pw')
        Membership.objects.create(user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN)
        self.member = User.objects.create_user(username='plainmember', password='pw')
        Membership.objects.create(user=self.member, organization=self.org)

    def test_admin_can_open_the_page(self):
        self.client.force_login(self.admin)
        resp = self.client.get('/org/settings/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'type="color"')
        self.assertContains(resp, 'Organisation settings')

    def test_admin_can_update_branding(self):
        self.client.force_login(self.admin)
        resp = self.client.post('/org/settings/', {
            'name': 'Settings Org',
            'display_name': 'Mercury Consortium',
            'tagline': 'Onwards',
            'primary_color': TEAL,
            'navbar_style': 'primary',
            'support_email': 'help@mercury.test',
            'email_from_name': 'Mercury Team',
        }, follow=True)
        self.assertRedirects(resp, '/org/')
        self.assertContains(resp, 'Branding updated.')
        self.org.refresh_from_db()
        self.assertEqual(self.org.display_name, 'Mercury Consortium')
        self.assertEqual(self.org.tagline, 'Onwards')
        self.assertEqual(self.org.primary_color, TEAL)
        self.assertEqual(self.org.navbar_style, 'primary')
        self.assertEqual(self.org.support_email, 'help@mercury.test')
        self.assertEqual(self.org.email_from_name, 'Mercury Team')

    def test_invalid_colour_is_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.post('/org/settings/', {
            'name': 'Settings Org', 'primary_color': 'teal', 'navbar_style': 'dark',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Use a hex colour like #0d6efd.')
        self.org.refresh_from_db()
        self.assertEqual(self.org.primary_color, '')

    def test_member_is_forbidden(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/org/settings/').status_code, 403)
        self.client.post('/org/settings/', {'name': 'Hijacked', 'navbar_style': 'dark'})
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Settings Org')

    def test_anonymous_is_redirected_to_login(self):
        resp = self.client.get('/org/settings/')
        self.assertRedirects(resp, '/accounts/login/?next=/org/settings/', fetch_redirect_response=False)

    def test_settings_links_shown_only_to_admins(self):
        self.client.force_login(self.admin)
        resp = self.client.get('/org/')
        self.assertContains(resp, '/org/settings/')
        self.assertContains(resp, 'Organisation settings')
        self.client.force_login(self.member)
        resp = self.client.get('/org/')
        self.assertNotContains(resp, '/org/settings/')


@override_settings(ALLOWED_HOSTS=HOSTS)
class BrandingContextTest(TestCase):
    """The host's organisation brands every page, including the anonymous login page."""

    def setUp(self):
        self.mercury = Organization.objects.create(
            name='Mercury Org', display_name='Mercury Consortium',
            primary_color=TEAL, navbar_style='primary',
            favicon=SimpleUploadedFile('mercury.png', b'\x89PNG', content_type='image/png'),
        )
        self.silavapi = Organization.objects.create(name='Silavapi Org')
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        OrganizationDomain.objects.create(organization=self.silavapi, hostname=SILAVAPI)
        self.user = User.objects.create_user(username='mercuryadmin', password='pw')
        Membership.objects.create(user=self.user, organization=self.mercury, role=Membership.ROLE_ADMIN)

    def tearDown(self):
        self.mercury.favicon.delete(save=False)

    def test_anonymous_login_page_carries_the_host_org_brand(self):
        resp = self.client.get('/accounts/login/', HTTP_HOST=MERCURY)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mercury Consortium')
        self.assertContains(resp, '<title>Sign In — Mercury Consortium</title>', html=True)
        self.assertContains(resp, f'<link rel="icon" href="{self.mercury.favicon.url}">', html=True)
        self.assertNotContains(resp, 'EOS App')

    def test_other_host_shows_its_own_org_and_not_the_first(self):
        resp = self.client.get('/accounts/login/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'Silavapi Org')
        self.assertNotContains(resp, 'Mercury')
        self.assertNotContains(resp, 'rel="icon"')

    @override_settings(DEFAULT_BRAND_NAME='Empresadence')
    def test_unmapped_host_shows_the_default_brand(self):
        resp = self.client.get('/accounts/login/', HTTP_HOST='testserver')
        self.assertContains(resp, 'Empresadence')
        self.assertContains(resp, 'Operating cadence for leadership teams')
        self.assertNotContains(resp, 'Mercury')
        self.assertNotContains(resp, '--bs-primary:')

    def test_navbar_style_and_colour_apply_only_to_the_org_that_set_them(self):
        self.client.force_login(self.user)
        resp = self.client.get('/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'navbar navbar-expand-lg navbar-dark bg-primary')
        self.assertContains(resp, f'--bs-primary: {TEAL};')
        self.assertContains(resp, '--bs-primary-rgb: 31, 111, 139;')

        Membership.objects.create(user=self.user, organization=self.silavapi)
        resp = self.client.get('/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'navbar navbar-expand-lg navbar-dark bg-dark')
        self.assertNotContains(resp, '--bs-primary:')
        self.assertNotContains(resp, 'navbar-dark bg-primary')

    def test_page_title_uses_the_display_name(self):
        self.client.force_login(self.user)
        resp = self.client.get('/org/settings/', HTTP_HOST=MERCURY)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Organisation settings — Mercury Consortium</title>', html=True)

    def test_child_template_page_title_carries_the_brand(self):
        self.client.force_login(self.user)
        for path, title in [
            ('/', 'Dashboard — Mercury Consortium'),
            ('/rocks/?quarter=1&year=2026', 'Priorities — Q1 2026 — Mercury Consortium'),
        ]:
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_HOST=MERCURY)
                self.assertContains(resp, f'<title>{title}</title>', html=True)

    def test_logged_in_user_on_the_main_host_gets_their_active_org_brand(self):
        self.client.force_login(self.user)
        resp = self.client.get('/', HTTP_HOST='testserver')
        self.assertContains(resp, 'Mercury Consortium')
        self.assertContains(resp, 'navbar-dark bg-primary')
