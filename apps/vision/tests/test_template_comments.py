from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Membership, Organization


class VisionTemplateCommentTest(TestCase):
    """Template comments written across several lines rendered as page text."""

    def setUp(self):
        org = Organization.objects.create(name='Comment Org')
        user = User.objects.create_user(username='commentuser', password='pw')
        Membership.objects.create(user=user, organization=org)
        self.client.force_login(user)

    def test_pages_render_no_template_comment_text(self):
        for url in ['/vision/', '/vision/print/']:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertNotContains(resp, '{#')
                self.assertNotContains(resp, '#}')
                self.assertNotContains(resp, 'apps.vision.structure')


class SingleLineCommentTest(SimpleTestCase):
    """``{# #}`` only works on one line; anything longer needs ``{% comment %}``."""

    def test_no_template_opens_a_comment_it_does_not_close_on_the_same_line(self):
        offenders = []
        for directory in settings.TEMPLATES[0]['DIRS']:
            for path in sorted(Path(directory).rglob('*')):
                if not path.is_file() or path.suffix not in {'.html', '.txt'}:
                    continue
                for number, line in enumerate(path.read_text().splitlines(), start=1):
                    if line.count('{#') != line.count('#}'):
                        offenders.append(f'{path.relative_to(directory)}:{number}')
        self.assertEqual(offenders, [])
