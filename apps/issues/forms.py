from django import forms
from django.db.models import Q

from apps.accounts.models import Team
from apps.accounts.scoping import TeamPickerMixin, is_org_admin
from apps.rocks.models import Rock
from apps.accounts.terminology import Terms, terms_for
from .models import Issue, IssueActivity


class IssueForm(TeamPickerMixin, forms.ModelForm):
    team_field_name = 'originating_team'

    class Meta:
        model = Issue
        fields = [
            'title', 'description', 'issue_type', 'originating_team',
            'delegated_to_team',
            'linked_rocks',
            'target_quarter', 'target_year',
            'is_company_issue',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'target_year': forms.NumberInput(attrs={'min': 2020, 'max': 2099}),
            'is_company_issue': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, team=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only an admin of the team's organisation may mark an Issue company-wide
        is_admin = bool(user) and is_org_admin(user, team.organization if team else None)
        if not is_admin:
            del self.fields['is_company_issue']
        self.user = user
        # The submitted team when bound, so linked Rocks follow a change of team.
        team = self.init_team_picker(team, user)
        if team:
            # Delegation can go to any team in the org
            org_teams = Team.objects.filter(organization=team.organization).order_by('name')
            self.fields['delegated_to_team'].queryset = org_teams
            # Existing links stay choices even when they are private Rocks this
            # user is not on, so saving the form does not unlink them.
            current = Q(pk__in=self.instance.linked_rocks.values('pk')) if self.instance.pk else Q(pk__in=[])
            self.fields['linked_rocks'].queryset = (
                Rock.objects
                .filter(team=team, status__in=[Rock.STATUS_ON_TRACK, Rock.STATUS_OFF_TRACK])
                .filter(Rock.visible_q(user) | current)
                .select_related('owner')
                .order_by('title')
            )
            self.fields['linked_rocks'].error_messages['invalid_choice'] = (
                f'Linked {terms_for(team.organization).rocks} must be on {team.name}.'
            )
            rock_word = terms_for(team.organization).rock
            self.fields['linked_rocks'].label_from_instance = (
                lambda r: r.title if r.is_visible_to(user) else f'A private {rock_word}'
            )
        else:
            self.fields['delegated_to_team'].queryset = Team.objects.none()
            self.fields['linked_rocks'].queryset = Rock.objects.none()
        self.fields['delegated_to_team'].required = False
        self.fields['linked_rocks'].required = False
        self.fields['target_quarter'].required = False
        self.fields['target_year'].required = False
        self.terms = terms_for(team.organization if team else None)

    def clean(self):
        cleaned_data = super().clean()
        issue_type = cleaned_data.get('issue_type')
        target_quarter = cleaned_data.get('target_quarter')
        target_year = cleaned_data.get('target_year')
        if issue_type == Issue.TYPE_LONG_TERM:
            if not target_quarter:
                self.add_error('target_quarter', f'Required for long-term {self.terms.issues.lower()}.')
            if not target_year:
                self.add_error(
                    'target_year', f'Required for long-term {self.terms.issues.lower()}.'
                )
        elif 'is_company_issue' in cleaned_data:
            # Company-wide only means anything for long-term issues, the VTO only
            # ever shows those. Don't let a short-term issue carry the flag.
            cleaned_data['is_company_issue'] = False
        return cleaned_data

    def save(self, commit=True):
        moved_from = None
        if commit and self.instance.pk and 'originating_team' in self.changed_data:
            moved_from = Team.objects.get(pk=self.initial['originating_team'])
        issue = super().save(commit=commit)
        if moved_from is not None:
            IssueActivity.objects.create(
                issue=issue, actor=self.user, action=IssueActivity.ACTION_STATUS_CHANGED,
                notes=f'Moved from {moved_from.name} to {issue.originating_team.name}.',
            )
        return issue


class IssueStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Issue.STATUS_CHOICES)
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        max_length=2000,
    )

    def __init__(self, *args, terms=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.terms = terms or Terms()

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        notes = cleaned_data.get('resolution_notes', '').strip()
        if status == Issue.STATUS_RESOLVED and not notes:
            self.add_error(
                'resolution_notes',
                f'Please describe how this {self.terms.issue.lower()} was resolved.',
            )
        return cleaned_data


class IssueDelegateForm(forms.Form):
    delegated_to_team = forms.ModelChoiceField(
        queryset=Team.objects.none(),
        empty_label='— Remove delegation (recall) —',
        required=False,
        label='Delegate to team',
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        teams = Team.objects.none()
        if organization:
            teams = Team.objects.filter(organization=organization).order_by('name')
        self.fields['delegated_to_team'].queryset = teams


class IssueCommentForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Add a comment…'}),
        max_length=2000,
        label='',
    )
