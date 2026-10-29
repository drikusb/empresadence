from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import TestCase, override_settings

from apps.accounts.forms import TerminologyForm
from apps.accounts.models import Membership, Organization, OrganizationDomain
from apps.accounts.terminology import DEFAULTS, PLURAL_KEYS, TERMS, Terms, terms_for

HOSTS = ['testserver', 'mercury.example.test', 'silavapi.example.test']
MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

PRIORITIES = {'rock': 'Priority', 'rocks': 'Priorities'}

# A custom word distinct from any shipped default, for tests that must tell
# "this was explicitly overridden" apart from "this happens to match the default."
BOULDERS = {'rock': 'Boulder', 'rocks': 'Boulders'}


class TermsTest(TestCase):
    def test_defaults(self):
        terms = Terms()
        self.assertEqual(terms.rock, 'Priority')
        self.assertEqual(terms.rocks, 'Priorities')
        self.assertEqual(terms.meeting, 'Weekly Meeting')
        self.assertEqual(terms.meetings, 'Weekly Meetings')
        self.assertEqual(terms.accountability_chart, 'Org Chart')
        self.assertEqual(terms.as_dict(), DEFAULTS)
        self.assertEqual(terms.overrides(), {})

    def test_every_term_has_a_singular_and_a_plural_key(self):
        for key, singular, plural, _ in TERMS:
            with self.subTest(key=key):
                self.assertEqual(DEFAULTS[key], singular)
                self.assertEqual(DEFAULTS[PLURAL_KEYS[key]], plural)
        self.assertEqual(len(DEFAULTS), 2 * len(TERMS))

    def test_override(self):
        terms = Terms(PRIORITIES)
        self.assertEqual(terms.rock, 'Priority')
        self.assertEqual(terms.rocks, 'Priorities')
        self.assertEqual(terms.issue, 'Blocker')
        self.assertIn('rock', terms)
        self.assertNotIn('boulder', terms)

    def test_unknown_key_is_ignored(self):
        terms = Terms({'boulder': 'Boulder', 'rock': 'Mountain'})
        self.assertEqual(terms.overrides(), {'rock': 'Mountain'})
        with self.assertRaises(AttributeError):
            terms.boulder
        with self.assertRaises(KeyError):
            terms.get('boulder')

    def test_empty_or_blank_override_is_ignored(self):
        terms = Terms({'rock': '', 'rocks': '   ', 'issue': None, 'todo': 0})
        self.assertEqual(terms.overrides(), {})
        self.assertEqual(terms.rock, 'Priority')

    def test_override_is_stripped(self):
        self.assertEqual(Terms({'rock': '  Boulder '}).rock, 'Boulder')

    def test_get_by_count(self):
        terms = Terms(PRIORITIES)
        self.assertEqual(terms.get('rock', count=1), 'Priority')
        self.assertEqual(terms.get('rock', count=2), 'Priorities')
        self.assertEqual(terms.get('rock', count=0), 'Priorities')
        self.assertEqual(terms.get('rock'), 'Priority')

    def test_get_plural_and_lower(self):
        terms = Terms(PRIORITIES)
        self.assertEqual(terms.get('rock', plural=True), 'Priorities')
        self.assertEqual(terms.get('rock', lower=True), 'priority')
        self.assertEqual(terms.get('rock', count=3, lower=True), 'priorities')
        self.assertEqual(terms.get('meeting', plural=True, lower=True), 'weekly meetings')

    def test_overrides_round_trip(self):
        overrides = {'rock': 'Boulder', 'rocks': 'Boulders', 'meeting': 'Weekly Sync'}
        self.assertEqual(Terms(overrides).overrides(), overrides)
        self.assertEqual(Terms(Terms(overrides).as_dict()).overrides(), overrides)
        self.assertEqual(Terms({'rock': 'Priority'}).overrides(), {})

    def test_ids_plural_lives_under_ids_plural(self):
        self.assertEqual(PLURAL_KEYS['ids'], 'ids_plural')
        self.assertNotIn('idss', DEFAULTS)
        terms = Terms({'ids_plural': 'Problem Solving Sessions'})
        self.assertEqual(terms.ids, 'PRS')
        self.assertEqual(terms.ids_plural, 'Problem Solving Sessions')
        self.assertEqual(terms.get('ids', count=2), 'Problem Solving Sessions')

    def test_equality(self):
        self.assertEqual(Terms(BOULDERS), Terms(BOULDERS))
        self.assertNotEqual(Terms(BOULDERS), Terms())

    def test_terms_for_organisation(self):
        self.assertEqual(terms_for(None), Terms())
        org = Organization(name='x', terminology=PRIORITIES)
        self.assertEqual(terms_for(org).rocks, 'Priorities')
        self.assertEqual(terms_for(Organization(name='y')), Terms())


class TermTagTest(TestCase):
    @staticmethod
    def render(source, **context):
        return Template('{% load terms %}' + source).render(Context(context))

    def test_singular_plural_count_and_lower(self):
        terms = Terms(PRIORITIES)
        self.assertEqual(self.render('{% term "rock" %}', terms=terms), 'Priority')
        self.assertEqual(self.render('{% term "rock" plural=True %}', terms=terms), 'Priorities')
        self.assertEqual(self.render('{% term "rock" count=n %}', terms=terms, n=1), 'Priority')
        self.assertEqual(self.render('{% term "rock" count=n %}', terms=terms, n=2), 'Priorities')
        self.assertEqual(self.render('{% term "rock" lower=True %}', terms=terms), 'priority')

    def test_as_variable(self):
        html = self.render(
            '{% term "rock" count=2 as label %}{{ label }}!', terms=Terms(PRIORITIES)
        )
        self.assertEqual(html, 'Priorities!')

    def test_falls_back_to_defaults_without_the_context_processor(self):
        self.assertEqual(self.render('{% term "rock" plural=True %}'), 'Priorities')
        self.assertEqual(self.render('{% term "meeting" %}', terms=None), 'Weekly Meeting')

    def test_attribute_access_in_templates(self):
        html = Template('{{ terms.rocks }} / {{ terms.ids_plural }}').render(
            Context({'terms': Terms(PRIORITIES)})
        )
        self.assertEqual(html, 'Priorities / PRS')


@override_settings(ALLOWED_HOSTS=HOSTS)
class TerminologyContextTest(TestCase):
    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', terminology=BOULDERS)
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)

    def test_anonymous_request_on_the_main_host_gets_the_defaults(self):
        resp = self.client.get('/accounts/login/', HTTP_HOST='testserver')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['terms'], Terms())
        self.assertEqual(resp.context['terms'].rocks, 'Priorities')

    def test_anonymous_request_on_the_org_host_gets_its_terms(self):
        resp = self.client.get('/accounts/login/', HTTP_HOST=MERCURY)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['terms'].rocks, 'Boulders')

    def test_logged_in_user_gets_the_active_org_terms(self):
        user = User.objects.create_user(username='mercuryadmin', password='pw')
        Membership.objects.create(user=user, organization=self.mercury, role=Membership.ROLE_ADMIN)
        self.client.force_login(user)
        resp = self.client.get('/', HTTP_HOST='testserver')
        self.assertEqual(resp.context['terms'].rock, 'Boulder')


class TerminologyFormTest(TestCase):
    def test_fields_show_current_values_and_default_placeholders(self):
        form = TerminologyForm(terms=Terms(PRIORITIES))
        self.assertEqual(form['rock'].value(), 'Priority')
        self.assertEqual(form['rocks'].value(), 'Priorities')
        self.assertEqual(form['issue'].value(), 'Blocker')
        self.assertEqual(form['rock'].field.widget.attrs['placeholder'], 'Priority')
        self.assertEqual(form['rocks'].field.widget.attrs['placeholder'], 'Priorities')
        self.assertEqual(form['ids_plural'].field.widget.attrs['placeholder'], 'PRS')
        self.assertEqual(len(form.fields), 2 * len(TERMS))

    def test_rows_pair_each_term_with_its_fields(self):
        rows = list(TerminologyForm().rows())
        self.assertEqual(len(rows), len(TERMS))
        self.assertEqual(rows[0]['key'], 'rock')
        self.assertEqual(rows[0]['description'], 'Quarterly priorities')
        self.assertEqual(rows[0]['singular_field'].name, 'rock')
        self.assertEqual(rows[0]['plural_field'].name, 'rocks')

    def test_save_stores_only_overrides(self):
        org = Organization.objects.create(name='Form Org')
        form = TerminologyForm(data={'rock': 'Boulder', 'rocks': 'Boulders', 'issue': 'Blocker'})
        self.assertTrue(form.is_valid(), form.errors)
        form.save(org)
        org.refresh_from_db()
        # 'issue': 'Blocker' matches the current default, so it is not stored.
        self.assertEqual(org.terminology, BOULDERS)

    def test_too_long_word_is_rejected(self):
        form = TerminologyForm(data={'rock': 'x' * 51})
        self.assertFalse(form.is_valid())
        self.assertIn('rock', form.errors)


class OrgTerminologyViewTest(TestCase):
    url = '/org/settings/terminology/'

    def setUp(self):
        self.org = Organization.objects.create(name='Terms Org')
        self.admin = User.objects.create_user(username='orgadmin', password='pw')
        Membership.objects.create(user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN)
        self.member = User.objects.create_user(username='plainmember', password='pw')
        Membership.objects.create(user=self.member, organization=self.org)

    def post_words(self, **words):
        data = {key: '' for key in DEFAULTS}
        data.update(words)
        return self.client.post(self.url, data, follow=True)

    def test_admin_sees_the_defaults(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<title>Terminology — Terms Org</title>', html=True)
        self.assertContains(resp, 'Quarterly priorities')
        self.assertContains(resp, 'Problem, Solve, Resolve')
        self.assertContains(resp, 'name="rock" value="Priority"')
        self.assertContains(resp, 'name="rocks" value="Priorities"')
        self.assertContains(resp, 'name="ids_plural" value="PRS"')
        self.assertContains(resp, 'placeholder="Weekly Meeting"')
        self.assertContains(resp, 'name="reset"')

    def test_post_saves_only_overrides(self):
        self.client.force_login(self.admin)
        resp = self.post_words(rock='Boulder', rocks='Boulders', issue='Blocker', todo='Action')
        self.assertRedirects(resp, self.url)
        self.assertContains(resp, 'Terminology updated.')
        self.org.refresh_from_db()
        # issue/todo were submitted but match the current defaults, so only rock/rocks persist.
        self.assertEqual(self.org.terminology, BOULDERS)
        self.assertContains(resp, 'name="rock" value="Boulder"')
        self.assertContains(resp, 'name="issue" value="Blocker"')

    def test_blank_fields_fall_back_to_the_defaults(self):
        self.org.terminology = {'rock': 'Boulder', 'rocks': 'Boulders', 'meeting': 'Weekly Sync'}
        self.org.save()
        self.client.force_login(self.admin)
        self.post_words(rock='Boulder', rocks='', meeting='')
        self.org.refresh_from_db()
        self.assertEqual(self.org.terminology, {'rock': 'Boulder'})

    def test_reset_clears_the_overrides(self):
        self.org.terminology = dict(BOULDERS)
        self.org.save()
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {'reset': '1', 'rock': 'Mountain'}, follow=True)
        self.assertRedirects(resp, self.url)
        self.assertContains(resp, 'Terminology reset to defaults.')
        self.assertContains(resp, 'name="rock" value="Priority"')
        self.org.refresh_from_db()
        self.assertEqual(self.org.terminology, {})

    def test_member_is_forbidden(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'rock': 'Hijacked'}).status_code, 403)
        self.org.refresh_from_db()
        self.assertEqual(self.org.terminology, {})

    def test_anonymous_is_redirected_to_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp, f'/accounts/login/?next={self.url}', fetch_redirect_response=False
        )

    def test_linked_from_the_settings_page_and_user_menu(self):
        self.client.force_login(self.admin)
        resp = self.client.get('/org/settings/')
        self.assertContains(resp, f'href="{self.url}"')
        self.client.force_login(self.member)
        resp = self.client.get('/')
        self.assertNotContains(resp, f'href="{self.url}"')


@override_settings(ALLOWED_HOSTS=HOSTS)
class NavigationTerminologyTest(TestCase):
    def setUp(self):
        self.mercury = Organization.objects.create(name='Mercury Org', terminology=BOULDERS)
        self.silavapi = Organization.objects.create(name='Silavapi Org')
        OrganizationDomain.objects.create(organization=self.mercury, hostname=MERCURY)
        OrganizationDomain.objects.create(organization=self.silavapi, hostname=SILAVAPI)
        self.user = User.objects.create_user(username='bothuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.mercury)
        Membership.objects.create(user=self.user, organization=self.silavapi)

    def test_each_host_shows_its_own_words_in_the_navigation(self):
        self.client.force_login(self.user)

        resp = self.client.get('/', HTTP_HOST=MERCURY)
        self.assertContains(resp, 'Quarterly Boulders')
        self.assertContains(resp, 'New Boulder')
        self.assertNotContains(resp, 'Quarterly Priorities')
        self.assertNotContains(resp, 'New Priority')

        resp = self.client.get('/', HTTP_HOST=SILAVAPI)
        self.assertContains(resp, 'Quarterly Priorities')
        self.assertContains(resp, 'New Priority')
        self.assertNotContains(resp, 'Boulder')

    def test_default_labels_are_the_generic_words(self):
        self.client.force_login(self.user)
        resp = self.client.get('/', HTTP_HOST=SILAVAPI)
        for label in [
            'Weekly Meetings', 'Weekly Meeting', 'Blockers List', 'New Blocker', 'My Actions',
            'Team Actions', 'New Action', 'Metrics Boards', 'Vision Plan', 'Org Chart',
        ]:
            with self.subTest(label=label):
                self.assertContains(resp, label)
