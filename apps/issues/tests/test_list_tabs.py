from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Membership, Organization, Team
from apps.issues.models import Issue


class IssueListStatusTabsTest(TestCase):
    """The default tab is not a second "Open" (#80)."""

    def setUp(self):
        self.org = Organization.objects.create(name='Tabs Org')
        self.team = Team.objects.create(organization=self.org, name='Tabs Team')
        self.user = User.objects.create_user(username='tabsuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.ROLE_MEMBER)
        self.user.profile.teams.add(self.team)
        for status in (Issue.STATUS_OPEN, Issue.STATUS_IN_IDS, Issue.STATUS_RESOLVED):
            Issue.objects.create(
                title=f'{status} issue', originating_team=self.team,
                created_by=self.user, status=status,
            )
        self.client.force_login(self.user)

    def test_open_appears_once(self):
        resp = self.client.get('/issues/')
        self.assertEqual(resp.content.decode().count('>\n        Open\n    </a>'), 1)

    def test_default_tab_is_active(self):
        resp = self.client.get('/issues/')
        self.assertContains(resp, '<a href="?" class="btn btn-sm btn-dark">\n        Active\n    </a>', html=False)

    def test_default_tab_still_shows_open_and_in_ids(self):
        resp = self.client.get('/issues/')
        titles = {i.title for i in resp.context['issues']}
        self.assertEqual(titles, {'open issue', 'in_ids issue'})

    def test_open_tab_shows_only_open(self):
        resp = self.client.get('/issues/', {'status': Issue.STATUS_OPEN})
        self.assertEqual([i.title for i in resp.context['issues']], ['open issue'])
