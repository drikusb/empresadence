"""The vision document's structure: the shipped default, and per-organisation overrides."""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.vision.models import (
    VTO, VTOSection, VisionPage, VisionSectionDefinition, VisionSectionGroup,
)
from apps.vision.structure import (
    DEFAULT_STRUCTURE, RENDER_LIST, RENDER_SINGLE_LINE, section_specs_for, structure_for,
)

HOST = 'structure.example.test'


def build_org(name='Structure Org', hostname=HOST):
    org = Organization.objects.create(name=name)
    OrganizationDomain.objects.create(organization=org, hostname=hostname)
    team = Team.objects.create(organization=org, name=f'{name} Team')
    user = User.objects.create_user(username=f'{name.lower().replace(" ", "")}user', password='pw')
    Membership.objects.create(user=user, organization=org, role=Membership.ROLE_ADMIN)
    user.profile.teams.add(team)
    return org, user


def custom_structure(org):
    """A deliberately different two-page structure, sharing no key with the default."""
    page = VisionPage.objects.create(organization=org, label='Where We Are Going', order=0)
    group = VisionSectionGroup.objects.create(page=page, label='North Star', hint='Our one metric', order=0)
    VisionSectionDefinition.objects.create(
        group=group, key='north_star', label='The number', order=0, render_as=RENDER_SINGLE_LINE,
    )
    VisionSectionDefinition.objects.create(
        group=group, key='bets', label='Bets we are making', order=1, render_as=RENDER_LIST,
    )
    second = VisionPage.objects.create(organization=org, label='How We Get There', order=1)
    plan = VisionSectionGroup.objects.create(page=second, label='This Year', order=0)
    VisionSectionDefinition.objects.create(group=plan, key='this_year', label='Focus', order=0)
    return page, second


class StructureForTest(TestCase):
    def test_organisation_without_pages_gets_the_shipped_default(self):
        org = Organization.objects.create(name='Plain Org')
        self.assertIs(structure_for(org), DEFAULT_STRUCTURE)

    def test_no_organisation_gets_the_shipped_default(self):
        self.assertIs(structure_for(None), DEFAULT_STRUCTURE)

    def test_default_structure_covers_every_section_key_it_ships(self):
        keys = list(section_specs_for(None))
        self.assertEqual(len(keys), len(set(keys)), 'the default structure repeats a key')
        # The keys existing VTOSection rows are stored against must all survive,
        # or an organisation on the default structure would lose written content.
        self.assertIn('ten_year_target', keys)
        self.assertIn('three_uniques_3', keys)
        self.assertIn('one_year_goals', keys)

    def test_pages_replace_the_default_entirely(self):
        org = Organization.objects.create(name='Custom Org')
        custom_structure(org)
        pages = structure_for(org)
        self.assertEqual([p.label for p in pages], ['Where We Are Going', 'How We Get There'])
        self.assertEqual(sorted(section_specs_for(org)), ['bets', 'north_star', 'this_year'])
        self.assertNotIn('ten_year_target', section_specs_for(org))

    def test_render_style_and_hint_come_through(self):
        org = Organization.objects.create(name='Render Org')
        custom_structure(org)
        group = structure_for(org)[0].groups[0]
        self.assertEqual(group.hint, 'Our one metric')
        north_star, bets = group.sections
        self.assertTrue(north_star.is_single_line)
        self.assertFalse(north_star.is_list)
        self.assertTrue(bets.is_list)

    def test_duplicate_key_in_one_organisation_is_rejected(self):
        org = Organization.objects.create(name='Duplicate Org')
        page, _ = custom_structure(org)
        other_group = VisionSectionGroup.objects.create(page=page, label='Elsewhere', order=1)
        clash = VisionSectionDefinition(group=other_group, key='north_star', label='Again')
        with self.assertRaises(ValidationError):
            clash.full_clean()

    def test_the_same_key_in_two_organisations_is_fine(self):
        first = Organization.objects.create(name='First Org')
        second = Organization.objects.create(name='Second Org')
        custom_structure(first)
        page = VisionPage.objects.create(organization=second, label='Theirs')
        group = VisionSectionGroup.objects.create(page=page, label='Theirs')
        VisionSectionDefinition(group=group, key='north_star', label='Theirs').full_clean()


@override_settings(ALLOWED_HOSTS=['testserver', HOST])
class DefaultStructureRendersTest(TestCase):
    """An organisation that never customises sees exactly what it saw before."""

    def setUp(self):
        self.org, self.user = build_org()
        self.client.force_login(self.user)

    def test_detail_shows_the_default_cards_and_pages(self):
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertEqual(resp.status_code, 200)
        for text in [
            'Page 1 — Vision', 'Page 2 — Delivery',
            'Core Focus', '10-Year Target', 'Marketing Strategy',
            '3-Year Picture', '1-Year Plan',
            'Purpose / Passion / Cause', 'Niche', 'Target Market',
            'Unique 1.', 'Unique 2.', 'Unique 3.', 'Proven Process', 'Guarantee',
        ]:
            with self.subTest(text=text):
                self.assertContains(resp, text)

    def test_detail_links_every_default_section_to_its_edit_page(self):
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        for key in section_specs_for(self.org):
            with self.subTest(key=key):
                self.assertContains(resp, f'/vision/edit/{key}/')

    def test_print_shows_both_pages_and_breaks_before_the_second(self):
        resp = self.client.get('/vision/print/', HTTP_HOST=HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Page 1 — Vision')
        self.assertContains(resp, 'Page 2 — Delivery')
        # The first page must not carry the break, or it starts on its own sheet.
        self.assertContains(resp, 'class="col-lg-6"')
        self.assertContains(resp, 'class="col-lg-6 page-break"')

    def test_written_content_renders_in_its_section(self):
        vto = VTO.for_org(self.org)
        VTOSection.objects.create(vto=vto, key='ten_year_target', content='A billion widgets')
        VTOSection.objects.create(
            vto=vto, key='one_year_goals', content='Hire a designer\nShip the beta',
        )
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertContains(resp, 'A billion widgets')
        # A list-rendered section splits its lines into items.
        self.assertContains(resp, '<li>Hire a designer</li>', html=True)
        self.assertContains(resp, '<li>Ship the beta</li>', html=True)

    def test_half_width_sections_share_a_row(self):
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        # Revenue and profit are the only half-width pair in the default.
        self.assertContains(resp, 'col-6')
        groups = {g['label']: g for p in resp.context['pages'] for g in p['groups']}
        rows = groups['1-Year Plan']['rows']
        self.assertEqual([len(r) for r in rows], [2, 1])
        self.assertEqual(
            [e['spec'].key for e in rows[0]], ['one_year_revenue', 'one_year_profit']
        )


@override_settings(ALLOWED_HOSTS=['testserver', HOST])
class CustomStructureRendersTest(TestCase):
    def setUp(self):
        self.org, self.user = build_org('Custom Render Org')
        custom_structure(self.org)
        self.client.force_login(self.user)

    def test_detail_shows_the_organisations_own_structure_and_not_the_default(self):
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Page 1 — Where We Are Going')
        self.assertContains(resp, 'Page 2 — How We Get There')
        self.assertContains(resp, 'North Star')
        self.assertContains(resp, 'Our one metric')
        self.assertNotContains(resp, '10-Year Target')
        self.assertNotContains(resp, 'Marketing Strategy')

    def test_the_built_in_cards_still_pin_to_the_first_and_last_page(self):
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertContains(resp, 'timeless guiding principles')   # core values, page 1
        self.assertContains(resp, 'live from Priorities module')   # company priorities, last
        self.assertContains(resp, 'Company Blockers List')

    def test_a_custom_section_is_editable(self):
        resp = self.client.get('/vision/edit/north_star/', HTTP_HOST=HOST)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'The number')
        resp = self.client.post(
            '/vision/edit/north_star/', {'content': '10,000 subscribers'},
            HTTP_HOST=HOST, follow=True,
        )
        self.assertContains(resp, '&quot;The number&quot; updated.')
        self.assertContains(resp, '10,000 subscribers')

    def test_a_section_the_organisation_does_not_have_is_refused(self):
        resp = self.client.get('/vision/edit/ten_year_target/', HTTP_HOST=HOST, follow=True)
        self.assertContains(resp, 'Unknown section.')

    def test_removing_a_section_keeps_its_content_for_later(self):
        """Decision 2 in STRUCTURAL-CONFIGURABILITY.md: removal archives, never destroys."""
        self.client.post('/vision/edit/north_star/', {'content': 'Worth keeping'}, HTTP_HOST=HOST)
        definition = VisionSectionDefinition.objects.get(key='north_star')
        group = definition.group
        definition.delete()

        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertNotContains(resp, 'Worth keeping')
        stored = VTOSection.objects.get(vto=VTO.for_org(self.org), key='north_star')
        self.assertEqual(stored.content, 'Worth keeping')

        # Putting the section back brings the content back with it.
        VisionSectionDefinition.objects.create(
            group=group, key='north_star', label='The number', order=0,
        )
        resp = self.client.get('/vision/', HTTP_HOST=HOST)
        self.assertContains(resp, 'Worth keeping')
