from django.test import TestCase
from django.contrib.auth.models import User
from apps.accounts.models import Organization
from apps.vision.models import VTO, VTOSection, VTOSectionHistory, VTOCoreValue, SectionKey


def make_org():
    return Organization.objects.get_or_create(name='VTO Org')[0]


class SectionKeyTest(TestCase):
    def test_all_keys_present(self):
        self.assertIn(SectionKey.CORE_FOCUS_PURPOSE, SectionKey.ALL)
        self.assertIn(SectionKey.ONE_YEAR_GOALS, SectionKey.ALL)
        self.assertEqual(len(SectionKey.ALL), 15)

    def test_labels_match_all(self):
        for key in SectionKey.ALL:
            self.assertIn(key, SectionKey.LABELS)

    def test_single_line_subset(self):
        for key in SectionKey.SINGLE_LINE:
            self.assertIn(key, SectionKey.ALL)


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
