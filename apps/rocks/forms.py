from django import forms
from django.contrib.auth.models import User

from apps.accounts.terminology import terms_for
from .models import Rock, RockDependency
from apps.accounts.models import Team
from apps.accounts.scoping import is_org_admin


class RockForm(forms.ModelForm):
    class Meta:
        model = Rock
        # team is excluded: always set to the user's active team in the view
        fields = ['title', 'description', 'owner', 'quarter', 'year', 'due_date',
                  'parent_rock', 'is_company_rock']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What does "done" look like? Be specific and measurable.',
            }),
            'owner': forms.Select(attrs={'class': 'form-select'}),
            'quarter': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2099}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'parent_rock': forms.Select(attrs={'class': 'form-select'}),
            'is_company_rock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, team=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        terms = self.terms = terms_for(team.organization if team else None)
        # Only an admin of the team's organisation may flag a Rock as company-wide.
        is_admin = bool(user) and is_org_admin(user, team.organization if team else None)
        if is_admin:
            self.fields['confirm_demote_children'] = forms.BooleanField(
                required=False,
                label=f"Also remove company-wide status from this {terms.rock}'s company-wide child {terms.rocks}",
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            )
        else:
            del self.fields['is_company_rock']
        if team:
            self.fields['owner'].queryset = User.objects.filter(
                profile__teams=team
            ).distinct().order_by('first_name', 'username')
            self.fields['parent_rock'].queryset = Rock.objects.filter(
                team=team
            ).order_by('-year', '-quarter', 'title')
        else:
            self.fields['owner'].queryset = User.objects.none()
            self.fields['parent_rock'].queryset = Rock.objects.none()
        self.fields['title'].widget.attrs['placeholder'] = f'What is this {terms.rock}? Keep it concise.'
        self.fields['parent_rock'].required = False
        self.fields['parent_rock'].empty_label = f'— None (top-level {terms.rock}) —'
        self.fields['description'].required = False

        if not self.instance.pk:
            self.fields['quarter'].initial = Rock.current_quarter()
            self.fields['year'].initial = Rock.current_year()
            q = Rock.current_quarter()
            y = Rock.current_year()
            self.fields['due_date'].initial = Rock.quarter_end_date(q, y)

    @property
    def company_children(self):
        """This Rock's existing company-wide child Rocks, if it has any."""
        if not self.instance.pk:
            return Rock.objects.none()
        return self.instance.child_rocks.filter(is_company_rock=True)

    def clean(self):
        cleaned_data = super().clean()
        # is_company_rock is absent from cleaned_data for non-admins, who can't
        # change it, so fall back to the Rock's current stored value.
        is_company_rock = cleaned_data.get(
            'is_company_rock', getattr(self.instance, 'is_company_rock', False)
        )
        parent_rock = cleaned_data.get('parent_rock')
        if is_company_rock and parent_rock and not parent_rock.is_company_rock:
            self.add_error(
                'parent_rock',
                f'A company-wide {self.terms.rock} needs a company-wide parent, or no parent at all.',
            )

        self._children_to_demote = Rock.objects.none()
        was_company_rock = self.instance.pk and Rock.objects.filter(
            pk=self.instance.pk, is_company_rock=True
        ).exists()
        if was_company_rock and not is_company_rock:
            children = self.company_children
            if children.exists():
                if cleaned_data.get('confirm_demote_children'):
                    self._children_to_demote = children
                else:
                    count = children.count()
                    titles = ', '.join(children.values_list('title', flat=True))
                    terms = self.terms
                    self.add_error(None, (
                        f'Demoting this {terms.rock} will also remove company-wide status from '
                        f'{count} child {terms.get("rock", count=count)}: {titles}. '
                        f'Check "Also remove company-wide status from this {terms.rock}’s '
                        f'company-wide child {terms.rocks}" below and save again to confirm.'
                    ))
        return cleaned_data

    def save(self, commit=True):
        rock = super().save(commit=commit)
        if commit and self._children_to_demote.exists():
            self._children_to_demote.update(is_company_rock=False)
        return rock


class RockStatusForm(forms.Form):
    """Simple form to set a Rock's status from the dashboard or detail page."""
    status = forms.ChoiceField(choices=Rock.STATUS_CHOICES)
    next = forms.CharField(required=False, widget=forms.HiddenInput())


class RockDependencyForm(forms.ModelForm):
    class Meta:
        model = RockDependency
        fields = ['depends_on_rock', 'description']
        widgets = {
            'depends_on_rock': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, rock=None, **kwargs):
        super().__init__(*args, **kwargs)
        terms = terms_for(rock.team.organization if rock else None)
        self.fields['description'].widget.attrs['placeholder'] = (
            f'Why does this {terms.rock} depend on the other? (optional)'
        )
        if rock:
            # Show only rocks from the same org, different team, same quarter/year
            self.fields['depends_on_rock'].queryset = (
                Rock.objects
                .filter(team__organization=rock.team.organization, quarter=rock.quarter, year=rock.year)
                .exclude(pk=rock.pk)
                .exclude(dependencies__rock=rock)   # exclude already-linked
                .select_related('team', 'owner')
                .order_by('team__name', 'title')
            )
            self.fields['depends_on_rock'].label_from_instance = (
                lambda r: f'{r.title} ({r.team.name} — {r.owner.get_full_name() or r.owner.username})'
            )
        self.fields['description'].required = False
