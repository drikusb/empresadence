from django.test import TestCase
from django.contrib.auth.models import User
from apps.accounts.models import Organization
from apps.vision.models import VTO, VTOSection, VTOSectionHistory, VTOCoreValue, SectionKey
from apps.vision.structure import section_specs_for


def make_org():
    return Organization.objects.get_or_create(name='VTO Org')[0]


class SectionKeyTest(TestCase):
    """The default structure must use the keys existing content is stored against.

    Labels, grouping and render style moved to apps.vision.structure (and are
    covered by test_structure.py); what has to stay stable here is the keys
    themselves, because a key that stops being referenced takes its written
    content off the page with it.
    """

    def test_every_default_key_is_in_the_default_structure(self):
        shipped = section_specs_for(None)
        for name in dir(SectionKey):
            if name.isupper() and name != 'THREE_UNIQUES':
                with self.subTest(key=name):
                    self.assertIn(getattr(SectionKey, name), shipped)


class VTOForOrgTest(TestCase):
    def test_creates_vto_for_org(self):
        org = make_org()
        vto = VTO.for_org(org)
        self.assertEqual(vto.organization, org)

    def test_idempotent(self):
        org = make_org()
        v1 = VTO.for_org(org)
        v2 = VTO.for_org(org)
        self.assertEqual(v1.pk, v2.pk)

    def test_str(self):
        org = make_org()
        vto = VTO.for_org(org)
        self.assertIn(org.name, str(vto))


class VTOSectionSaveContentTest(TestCase):
    def setUp(self):
        org = make_org()
        self.vto = VTO.for_org(org)
        self.user = User.objects.get_or_create(username='vtouser')[0]
        self.section, _ = VTOSection.objects.get_or_create(
            vto=self.vto, key=SectionKey.TEN_YEAR_TARGET
        )

    def test_saves_content(self):
        self.section.save_content('$1B revenue', self.user)
        self.assertEqual(self.section.content, '$1B revenue')
        self.assertEqual(self.section.last_edited_by, self.user)

    def test_snapshots_previous_content(self):
        self.section.save_content('First version', self.user)
        self.section.save_content('Second version', self.user)
        self.assertEqual(self.section.history.count(), 1)
        snap = self.section.history.first()
        self.assertEqual(snap.content, 'First version')

    def test_trims_history_to_5(self):
        for i in range(7):
            self.section.save_content(f'Version {i}', self.user)
        self.assertLessEqual(self.section.history.count(), 5)


class VTOCoreValueTest(TestCase):
    def test_str(self):
        org = make_org()
        vto = VTO.for_org(org)
        cv = VTOCoreValue.objects.create(vto=vto, name='Integrity')
        self.assertEqual(str(cv), 'Integrity')
