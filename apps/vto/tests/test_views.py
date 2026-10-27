from django.test import TestCase
from django.contrib.auth.models import User

from apps.accounts.models import Membership, Organization


class VTOPrintColourAdjustTest(TestCase):
    """Regression test: browsers drop background colours when printing by default,
    which was silently stripping the colour off the Rock and Issue status badges."""

    def setUp(self):
        self.org = Organization.objects.create(name='Print Colour Org')
        self.user = User.objects.create_user(username='printcolouruser', password='pw')
        Membership.objects.create(user=self.user, organization=self.org)

    def test_print_colour_is_forced_on(self):
        self.client.force_login(self.user)
        resp = self.client.get('/vto/print/')
        self.assertContains(resp, 'print-color-adjust: exact')


class VTOPrintPageBreakTest(TestCase):
    """Regression test: keeping the outer .row on one page pushed the whole VTO,
    which is taller than a page, off the title page and left that page blank."""

    def setUp(self):
        self.org = Organization.objects.create(name='Print Break Org')
        self.user = User.objects.create_user(username='printbreakuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.org)

    def test_cards_stay_whole_and_the_row_may_break(self):
        self.client.force_login(self.user)
        resp = self.client.get('/vto/print/')
        self.assertContains(resp, '.card { break-inside: avoid; page-break-inside: avoid; }')
        self.assertNotContains(resp, '.row { page-break-inside: avoid; }')

    def test_traction_starts_on_a_new_page(self):
        self.client.force_login(self.user)
        resp = self.client.get('/vto/print/')
        self.assertContains(resp, '.page-traction { break-before: page; page-break-before: always; }')
        self.assertContains(resp, '<div class="col-lg-6 page-traction">')
