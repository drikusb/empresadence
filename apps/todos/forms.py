from datetime import date, timedelta

from django import forms
from django.contrib.auth.models import User

from apps.accounts.models import Team
from apps.accounts.scoping import TeamPickerMixin
from apps.rocks.models import Rock
from apps.issues.models import Issue
from .models import ToDo


class ToDoForm(TeamPickerMixin, forms.ModelForm):
    class Meta:
        model = ToDo
        fields = ['title', 'description', 'owner', 'team', 'due_date', 'linked_rock',
                  'linked_issue']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, team=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['due_date'].initial = date.today() + timedelta(days=7)

        # The submitted team when bound, so owner and links follow a change of team.
        team = self.init_team_picker(team, user)
        if team:
            self.fields['owner'].queryset = (
                User.objects
                .filter(profile__teams=team)
                .distinct()
                .order_by('first_name', 'last_name', 'username')
            )
            self.fields['linked_rock'].queryset = (
                Rock.objects
                .filter(team=team, status__in=[Rock.STATUS_ON_TRACK, Rock.STATUS_OFF_TRACK])
                .order_by('title')
            )
            self.fields['linked_issue'].queryset = (
                Issue.objects
                .filter(originating_team=team, status__in=[Issue.STATUS_OPEN, Issue.STATUS_IN_IDS])
                .order_by('-created_at')
            )
            self.fields['owner'].error_messages['invalid_choice'] = (
                f'That person is not a member of {team.name}.'
            )
            self.fields['linked_rock'].error_messages['invalid_choice'] = (
                f'The linked Rock must be on {team.name}.'
            )
            self.fields['linked_issue'].error_messages['invalid_choice'] = (
                f'The linked Issue must have been raised by {team.name}.'
            )
        else:
            self.fields['owner'].queryset = User.objects.none()
            self.fields['linked_rock'].queryset = Rock.objects.none()
            self.fields['linked_issue'].queryset = Issue.objects.none()

        self.fields['description'].required = False
        self.fields['linked_rock'].required = False
        self.fields['linked_issue'].required = False

    def clean_due_date(self):
        d = self.cleaned_data.get('due_date')
        if d and d < date.today() and not self.instance.pk:
            raise forms.ValidationError('Due date cannot be in the past.')
        return d


class QuickToDoForm(forms.ModelForm):
    """Minimal form for in-context To-Do creation (title + owner + due date)."""

    class Meta:
        model = ToDo
        fields = ['title', 'owner', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['due_date'].initial = date.today() + timedelta(days=7)
        if team:
            self.fields['owner'].queryset = (
                User.objects
                .filter(profile__teams=team)
                .distinct()
                .order_by('first_name', 'last_name', 'username')
            )
