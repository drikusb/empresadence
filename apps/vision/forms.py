from django import forms
from .models import VTOCoreValue


class VTOSectionForm(forms.Form):
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
    )

    def __init__(self, *args, spec=None, **kwargs):
        """``spec`` is the section's :class:`~apps.vision.structure.SectionSpec`.

        It carries the label and whether this section takes a single line, both
        of which come from the organisation's own structure rather than a fixed
        list of sections.
        """
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.key = spec.key if spec else None
        if spec and spec.is_single_line:
            self.fields['content'].widget = forms.TextInput(attrs={'class': 'form-control'})
        self.fields['content'].label = (spec.label or spec.key) if spec else 'Content'


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
