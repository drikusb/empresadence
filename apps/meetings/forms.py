from django import forms

from .models import Meeting, SegueEntry, Headline, MeetingRating
from apps.accounts.models import Team


class MeetingCreateForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['team', 'scheduled_date']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        teams = Team.objects.none()
        if org:
            teams = Team.objects.filter(organization=org).order_by('name')
        self.fields['team'].queryset = teams


class SegueEntryForm(forms.ModelForm):
    class Meta:
        model = SegueEntry
        fields = ['personal_best', 'business_best']
        widgets = {
            'personal_best': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'e.g. Ran a 5K this weekend',
            }),
            'business_best': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'e.g. Closed the Acme deal',
            }),
        }


class HeadlineForm(forms.ModelForm):
    class Meta:
        model = Headline
        fields = ['headline_type', 'text']
        widgets = {
            'headline_type': forms.Select(attrs={'class': 'form-select'}),
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Short headline — good news or concern',
            }),
        }

    def __init__(self, *args, terms=None, **kwargs):
        """``terms`` (the organisation's vocabulary) names the headline in the placeholder."""
        super().__init__(*args, **kwargs)
        if terms is not None:
            word = terms.get('headline', lower=True)
            self.fields['text'].widget.attrs['placeholder'] = f'Short {word} — good news or concern'


class MeetingRatingForm(forms.ModelForm):
    class Meta:
        model = MeetingRating
        fields = ['score', 'improvement_note']
        widgets = {
            'score': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 10,
                'style': 'max-width:100px;',
            }),
            'improvement_note': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'What would make next week\'s meeting better?',
            }),
        }

    def __init__(self, *args, terms=None, **kwargs):
        """``terms`` (the organisation's vocabulary) names the meeting in the placeholder."""
        super().__init__(*args, **kwargs)
        if terms is not None:
            word = terms.get('meeting', lower=True)
            self.fields['improvement_note'].widget.attrs['placeholder'] = (
                f"What would make next week's {word} better?"
            )


class CascadingMessagesForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['cascading_messages']
        widgets = {
            'cascading_messages': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'What does the rest of the organisation need to know from this meeting?',
            }),
        }

    def __init__(self, *args, terms=None, **kwargs):
        """``terms`` (the organisation's vocabulary) names the meeting in the placeholder."""
        super().__init__(*args, **kwargs)
        if terms is not None:
            word = terms.get('meeting', lower=True)
            self.fields['cascading_messages'].widget.attrs['placeholder'] = (
                f'What does the rest of the organisation need to know from this {word}?'
            )
