from django import forms
from .models import VTOCoreValue, SectionKey


class VTOSectionForm(forms.Form):
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
    )

    def __init__(self, *args, key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key
        if key in SectionKey.SINGLE_LINE:
            self.fields['content'].widget = forms.TextInput(attrs={'class': 'form-control'})
        self.fields['content'].label = SectionKey.LABELS.get(key, 'Content')


class VTOCoreValueForm(forms.ModelForm):
    class Meta:
        model = VTOCoreValue
        fields = ['name', 'description', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. "Do the right thing"',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What does living this value look like in practice?',
            }),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
