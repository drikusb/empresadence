from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.accounts.models import Membership, Organization, OrganizationDomain, Team
from apps.rocks.forms import RockDependencyForm, RockForm
from apps.rocks.models import Rock

MERCURY = 'mercury.example.test'
SILAVAPI = 'silavapi.example.test'

PRIORITIES = {
    'rock': 'Priority', 'rocks': 'Priorities',
    'milestone': 'Step', 'milestones': 'Steps',
}


def make_org(name, hostname, terminology=None):
    """An organisation on its own host, with one team and one member on that team."""
    org = Organization.objects.create(name=name, terminology=terminology or {})
    OrganizationDomain.objects.create(organization=org, hostname=hostname)
    team = Team.objects.create(organization=org, name=f'{name} Team')
    user = User.objects.create_user(username=f'{name.lower()}-member', password='pw')
    Membership.objects.create(user=user, organization=org)
    user.profile.teams.add(team)
    return org, team, user


def make_rock(team, owner, title):
    quarter, year = Rock.current_quarter(), Rock.current_year()
    return Rock.objects.create(
        title=title, owner=owner, team=team, quarter=quarter, year=year,
        due_date=Rock.quarter_end_date(quarter, year),
    )


@override_settings(ALLOWED_HOSTS=['testserver', MERCURY, SILAVAPI])
class RockTerminologyTest(TestCase):
    """The Rocks pages use the words the organisation chose."""

    def setUp(self):
        self.org, self.team, self.user = make_org('Mercury', MERCURY, PRIORITIES)
        self.rock = make_rock(self.team, self.user, 'Launch the beta')
        self.other_rock = make_rock(self.team, self.user, 'Hire a designer')

        self.default_org, self.default_team, self.default_user = make_org('Silavapi', SILAVAPI)
        make_rock(self.default_team, self.default_user, 'Open the shop')
        make_rock(self.default_team, self.default_user, 'Close the books')

        self.quarter_label = f'Q{Rock.current_quarter()} {Rock.current_year()}'

    def get(self, path, host=MERCURY):
        return self.client.get(path, HTTP_HOST=host)

    def test_list_page_uses_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.get('/rocks/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            '<h1 class="h3 mb-0"><i class="bi bi-gem me-2 text-success"></i>Priorities</h1>',
            html=True,
        )
        self.assertContains(
            resp,
            f'<title>Priorities — {self.quarter_label} — {self.org.get_display_name()}</title>',
            html=True,
        )
        self.assertContains(resp, '2 Priorities')
        self.assertContains(resp, 'New Priority')
        self.assertContains(resp, 'EOS recommends 3–7 Priorities per team')
        self.assertNotContains(resp, 'Rocks')
        self.assertNotContains(resp, 'New Rock')

    def test_count_line_uses_the_singular_for_one(self):
        self.other_rock.delete()
        self.client.force_login(self.user)
        resp = self.get('/rocks/')
        self.assertContains(resp, '1 Priority')
        self.assertNotContains(resp, '1 Priorities')

    def test_empty_list_uses_the_organisations_words(self):
        Rock.objects.filter(team=self.team).delete()
        self.client.force_login(self.user)
        resp = self.get('/rocks/')
        self.assertContains(resp, f'No Priorities for {self.quarter_label}')
        self.assertContains(resp, 'Create first Priority')

    def test_archive_page_uses_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.get('/rocks/archive/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Total Priorities')
        self.assertContains(resp, '0 of 2 Priorities completed')
        self.assertContains(resp, '2 Priorities')
        self.assertNotContains(resp, 'Rocks')

    def test_create_page_uses_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.get('/rocks/new/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'New Priority')
        self.assertContains(resp, 'Create Priority')
        self.assertContains(resp, 'Parent Priority')
        self.assertContains(resp, '— None (top-level Priority) —')
        self.assertContains(
            resp, f'<title>Create Priority — {self.org.get_display_name()}</title>', html=True
        )
        self.assertNotContains(resp, 'Create Rock')

    def test_creating_a_rock_reports_in_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.client.post('/rocks/new/', {
            'title': 'Ship the thing',
            'description': '',
            'owner': self.user.pk,
            'quarter': Rock.current_quarter(),
            'year': Rock.current_year(),
            'due_date': Rock.quarter_end_date(Rock.current_quarter(), Rock.current_year()),
        }, HTTP_HOST=MERCURY, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Priority &quot;Ship the thing&quot; created.')
        self.assertNotContains(resp, 'Rock &quot;Ship the thing&quot; created.')

    def test_detail_page_milestone_section_uses_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.get(f'/rocks/{self.rock.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<i class="bi bi-flag me-1"></i>Steps')
        self.assertContains(resp, 'placeholder="Add a step…"')
        self.assertContains(resp, '— Select a Priority —')
        self.assertNotContains(resp, 'Milestone')
        self.assertNotContains(resp, 'Add a milestone')

    def test_milestone_messages_use_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/rocks/{self.rock.pk}/milestones/add/', {'title': 'Write the brief'},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Step added.')
        self.assertNotContains(resp, 'Milestone added.')
        resp = self.client.post(
            f'/rocks/{self.rock.pk}/milestones/add/', {'title': ''},
            HTTP_HOST=MERCURY, follow=True,
        )
        self.assertContains(resp, 'Step title is required.')

    def test_delete_page_uses_the_organisations_words(self):
        self.client.force_login(self.user)
        resp = self.get(f'/rocks/{self.rock.pk}/delete/')
        self.assertContains(resp, 'Delete Priority?')
        self.assertContains(
            resp, f'<title>Delete Priority — {self.org.get_display_name()}</title>', html=True
        )
        resp = self.client.post(f'/rocks/{self.rock.pk}/delete/', HTTP_HOST=MERCURY, follow=True)
        self.assertContains(resp, 'Priority &quot;Launch the beta&quot; deleted.')

    def test_default_host_still_says_rocks(self):
        self.client.force_login(self.default_user)
        resp = self.get('/rocks/', host=SILAVAPI)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            '<h1 class="h3 mb-0"><i class="bi bi-gem me-2 text-success"></i>Rocks</h1>',
            html=True,
        )
        self.assertContains(resp, '2 Rocks')
        self.assertContains(resp, 'New Rock')
        self.assertNotContains(resp, 'Priorit')
        resp = self.get(f'/rocks/{Rock.objects.filter(team=self.default_team).first().pk}/', host=SILAVAPI)
        self.assertContains(resp, '<i class="bi bi-flag me-1"></i>Milestones')

    def test_company_wide_lines_use_the_organisations_words(self):
        Membership.objects.filter(user=self.user).update(role=Membership.ROLE_ADMIN)
        self.rock.is_company_rock = True
        self.rock.save()
        self.client.force_login(self.user)

        resp = self.get('/rocks/')
        self.assertContains(resp, 'title="Company Priority, shown on the VTO"')
        resp = self.get(f'/rocks/{self.rock.pk}/')
        self.assertContains(resp, 'Company Priority')
        self.assertNotContains(resp, 'Company Rock')
        resp = self.get('/rocks/new/')
        self.assertContains(resp, 'Company-wide Priority')
        self.assertContains(resp, "Shows this Priority on the VTO, instead of just this team's Priority list.")
        self.assertNotContains(resp, 'Company-wide Rock')

    def test_child_rock_tooltip_uses_the_organisations_words(self):
        child = make_rock(self.team, self.user, 'Write the beta announcement')
        child.parent_rock = self.rock
        child.save()
        self.client.force_login(self.user)

        resp = self.get('/rocks/')
        self.assertContains(resp, 'title="Has child Priorities"')
        self.assertNotContains(resp, 'Has child Rocks')


class RockFormTerminologyTest(TestCase):
    """Form placeholders and labels come from the team's organisation."""

    def setUp(self):
        self.org, self.team, self.user = make_org('Mercury', MERCURY, PRIORITIES)
        self.rock = make_rock(self.team, self.user, 'Launch the beta')

    def test_rock_form_uses_the_teams_organisation_words(self):
        form = RockForm(team=self.team)
        self.assertEqual(
            form.fields['title'].widget.attrs['placeholder'],
            'What is this Priority? Keep it concise.',
        )
        self.assertEqual(form.fields['parent_rock'].empty_label, '— None (top-level Priority) —')

    def test_company_wide_form_messages_use_the_organisations_words(self):
        Membership.objects.filter(user=self.user).update(role=Membership.ROLE_ADMIN)
        form = RockForm(team=self.team, user=self.user)
        self.assertEqual(
            form.fields['confirm_demote_children'].label,
            "Also remove company-wide status from this Priority's company-wide child Priorities",
        )

        self.rock.is_company_rock = True
        self.rock.save()
        child = make_rock(self.team, self.user, 'Ship the beta')
        child.parent_rock = self.rock
        child.is_company_rock = True
        child.save()
        form = RockForm(
            data={
                'title': self.rock.title, 'owner': self.user.pk, 'quarter': self.rock.quarter,
                'year': self.rock.year, 'due_date': self.rock.due_date,
            },
            instance=self.rock, team=self.team, user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Demoting this Priority will also remove company-wide status from 1 child Priority: '
            'Ship the beta. Check "Also remove company-wide status from this Priority’s '
            'company-wide child Priorities" below and save again to confirm.',
            form.non_field_errors(),
        )

        other = make_rock(self.team, self.user, 'Plain parent')
        form = RockForm(
            data={
                'title': 'Needs a company parent', 'owner': self.user.pk, 'quarter': other.quarter,
                'year': other.year, 'due_date': other.due_date,
                'parent_rock': other.pk, 'is_company_rock': 'on',
            },
            team=self.team, user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'A company-wide Priority needs a company-wide parent, or no parent at all.',
            form.errors['parent_rock'],
        )

    def test_rock_form_without_a_team_uses_the_defaults(self):
        form = RockForm()
        self.assertEqual(
            form.fields['title'].widget.attrs['placeholder'],
            'What is this Rock? Keep it concise.',
        )
        self.assertEqual(form.fields['parent_rock'].empty_label, '— None (top-level Rock) —')

    def test_dependency_form_uses_the_rocks_organisation_words(self):
        form = RockDependencyForm(rock=self.rock)
        self.assertEqual(
            form.fields['description'].widget.attrs['placeholder'],
            'Why does this Priority depend on the other? (optional)',
        )
        self.assertEqual(
            RockDependencyForm().fields['description'].widget.attrs['placeholder'],
            'Why does this Rock depend on the other? (optional)',
        )
