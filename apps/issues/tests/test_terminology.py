from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.accounts.terminology import Terms
from apps.issues.forms import IssueForm, IssueStatusForm
from apps.issues.models import Issue

HOSTS = ['testserver', 'blockers.example.test', 'plain.example.test']
BLOCKERS = 'blockers.example.test'
PLAIN = 'plain.example.test'

BLOCKER_WORDS = {'issue': 'Blocker', 'issues': 'Blockers'}


def build_org(label, terminology=None, hostname=None):
    """An organisation with one member on one team and two open issues."""
    org = Organization.objects.create(name=f'{label} Org', terminology=terminology or {})
    if hostname:
        OrganizationDomain.objects.create(organization=org, hostname=hostname)
    team = Team.objects.create(organization=org, name=f'{label} Team')
    user = User.objects.create_user(username=f'{label.lower()}user', password='pw')
    Membership.objects.create(user=user, organization=org)
    user.profile.teams.add(team)
    issues = [
        Issue.objects.create(title=f'{label} issue {n}', originating_team=team, created_by=user)
        for n in (1, 2)
    ]
    return {'org': org, 'team': team, 'user': user, 'issues': issues}


@override_settings(ALLOWED_HOSTS=HOSTS)
class IssueTerminologyViewTest(TestCase):
    def setUp(self):
        self.blockers = build_org('Blockers', terminology=BLOCKER_WORDS, hostname=BLOCKERS)
        self.plain = build_org('Plain', hostname=PLAIN)

    def test_list_page_uses_the_organisations_word(self):
        self.client.force_login(self.blockers['user'])
        resp = self.client.get('/issues/', HTTP_HOST=BLOCKERS)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Blockers</h1>')
        self.assertContains(resp, 'New Blocker')
        self.assertContains(resp, '2 Blockers')
        self.assertNotContains(resp, 'Issues</h1>')
        self.assertNotContains(resp, 'New Issue')

    def test_list_count_line_is_singular_for_one_issue(self):
        self.blockers['issues'][1].delete()
        self.client.force_login(self.blockers['user'])
        resp = self.client.get('/issues/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, '1 Blocker<')
        self.assertNotContains(resp, '1 Blockers')

    def test_empty_state_uses_the_organisations_word(self):
        Issue.objects.filter(originating_team=self.blockers['team']).delete()
        self.client.force_login(self.blockers['user'])
        resp = self.client.get('/issues/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'No Blockers found')
        self.assertContains(resp, 'Create first Blocker')
        self.assertNotContains(resp, 'No Issues found')

    def test_create_page_uses_the_organisations_word(self):
        self.client.force_login(self.blockers['user'])
        resp = self.client.get('/issues/new/', HTTP_HOST=BLOCKERS)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create Blocker')
        self.assertContains(resp, 'Blocker Type')
        self.assertContains(resp, 'The presenting blocker')
        self.assertContains(resp, 'The team that raised this blocker.')
        self.assertContains(resp, 'added to the VTO Blockers List.')
        self.assertNotContains(resp, 'Create Issue')
        self.assertNotContains(resp, 'Issue Type')

    def test_creating_an_issue_flashes_the_organisations_word(self):
        self.client.force_login(self.blockers['user'])
        resp = self.client.post('/issues/new/', {
            'title': 'Printer on fire', 'issue_type': Issue.TYPE_SHORT_TERM,
        }, HTTP_HOST=BLOCKERS, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Blocker &quot;Printer on fire&quot; created.')
        self.assertTrue(Issue.objects.filter(title='Printer on fire').exists())

    def test_long_term_issue_without_a_quarter_is_rejected_with_the_organisations_word(self):
        self.client.force_login(self.blockers['user'])
        resp = self.client.post('/issues/new/', {
            'title': 'Strategic gap', 'issue_type': Issue.TYPE_LONG_TERM, 'target_year': 2027,
        }, HTTP_HOST=BLOCKERS)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Required for long-term blockers.')
        self.assertFalse(Issue.objects.filter(title='Strategic gap').exists())

    def test_long_term_issue_without_a_year_is_rejected_with_the_organisations_word(self):
        # The reverse of the quarter case: quarter given, year missing.
        self.client.force_login(self.blockers['user'])
        resp = self.client.post('/issues/new/', {
            'title': 'Strategic gap', 'issue_type': Issue.TYPE_LONG_TERM, 'target_quarter': 2,
        }, HTTP_HOST=BLOCKERS)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Required for long-term blockers.')
        self.assertNotContains(resp, 'Required for long-term issues.')
        self.assertFalse(Issue.objects.filter(title='Strategic gap').exists())

    def test_default_host_long_term_issue_without_a_year_keeps_the_default_word(self):
        self.client.force_login(self.plain['user'])
        resp = self.client.post('/issues/new/', {
            'title': 'Strategic gap', 'issue_type': Issue.TYPE_LONG_TERM, 'target_quarter': 2,
        }, HTTP_HOST=PLAIN)
        self.assertContains(resp, 'Required for long-term issues.')

    def test_detail_and_delete_pages_use_the_organisations_word(self):
        self.client.force_login(self.blockers['user'])
        issue = self.blockers['issues'][0]
        resp = self.client.get(f'/issues/{issue.pk}/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'Drop Blocker')
        self.assertNotContains(resp, 'Drop Issue')
        resp = self.client.get(f'/issues/{issue.pk}/delete/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'Delete Blocker?')
        self.assertNotContains(resp, 'Delete Issue?')

    def test_company_wide_lines_use_the_organisations_words(self):
        Membership.objects.filter(user=self.blockers['user']).update(role=Membership.ROLE_ADMIN)
        issue = self.blockers['issues'][0]
        issue.issue_type = Issue.TYPE_LONG_TERM
        issue.is_company_issue = True
        issue.target_quarter = 1
        issue.target_year = 2026
        issue.save()
        self.client.force_login(self.blockers['user'])

        resp = self.client.get('/issues/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'title="Company Blocker, shown on the VTO"')
        resp = self.client.get(f'/issues/{issue.pk}/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'Company Blocker')
        self.assertNotContains(resp, 'Company Issue')
        resp = self.client.get('/issues/new/', HTTP_HOST=BLOCKERS)
        self.assertContains(resp, 'Company-wide Blocker')
        self.assertContains(resp, "Shows this long-term Blocker on the VTO, instead of just this team's Blockers list.")
        self.assertNotContains(resp, 'Company-wide Issue')

    def test_default_host_keeps_the_eos_words(self):
        self.client.force_login(self.plain['user'])
        resp = self.client.get('/issues/', HTTP_HOST=PLAIN)
        self.assertContains(resp, 'Issues</h1>')
        self.assertContains(resp, 'New Issue')
        self.assertContains(resp, '2 Issues')
        self.assertNotContains(resp, 'Blocker')

        resp = self.client.get('/issues/new/', HTTP_HOST=PLAIN)
        self.assertContains(resp, 'Create Issue')
        self.assertContains(resp, 'Issue Type')

        resp = self.client.post('/issues/new/', {
            'title': 'Strategic gap', 'issue_type': Issue.TYPE_LONG_TERM, 'target_year': 2027,
        }, HTTP_HOST=PLAIN)
        self.assertContains(resp, 'Required for long-term issues.')


class IssueFormTerminologyTest(TestCase):
    def test_issue_form_reads_the_teams_organisation(self):
        org = Organization.objects.create(name='Blockers Org', terminology=BLOCKER_WORDS)
        team = Team.objects.create(organization=org, name='Blockers Team')
        form = IssueForm(
            data={'title': 'x', 'issue_type': Issue.TYPE_LONG_TERM, 'target_year': 2027}, team=team
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['target_quarter'], ['Required for long-term blockers.'])

    def test_issue_form_falls_back_to_the_defaults_without_a_team(self):
        form = IssueForm(data={'title': 'x', 'issue_type': Issue.TYPE_LONG_TERM, 'target_year': 2027})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['target_quarter'], ['Required for long-term issues.'])

    def test_status_form_uses_the_given_terms(self):
        form = IssueStatusForm(
            {'status': Issue.STATUS_RESOLVED, 'resolution_notes': ''}, terms=Terms(BLOCKER_WORDS)
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['resolution_notes'], ['Please describe how this blocker was resolved.']
        )

    def test_status_form_falls_back_to_the_defaults(self):
        form = IssueStatusForm({'status': Issue.STATUS_RESOLVED, 'resolution_notes': ''})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['resolution_notes'], ['Please describe how this issue was resolved.']
        )
