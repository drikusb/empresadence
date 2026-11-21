from django import forms
from django.contrib.auth.models import User
from .models import Membership, Organization, OrganizationInvitation, Team, UserProfile
from .terminology import PLURAL_KEYS, TERMS, Terms


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. Acme Corp',
                'autofocus': True,
            }),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }


class OrganizationSettingsForm(forms.ModelForm):
    # The browser's colour input has no empty state and reports Bootstrap's
    # blue when untouched, so that value means "no custom colour".
    BOOTSTRAP_PRIMARY = '#0d6efd'

    class Meta:
        model = Organization
        fields = [
            'name', 'display_name', 'tagline', 'logo', 'favicon', 'primary_color',
            'navbar_style', 'support_email', 'email_from_name',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'favicon': forms.FileInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={
                'type': 'color', 'class': 'form-control form-control-color',
            }),
            'navbar_style': forms.Select(attrs={'class': 'form-select'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'email_from_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'tagline': 'Shown under the name on the sign-in page and in the footer.',
            'favicon': 'An .ico, .png or .svg file.',
            'primary_color': 'Used for buttons, links and the "Primary colour" navbar style.',
            'support_email': 'Linked from the footer when set.',
            'email_from_name': 'Sender name on emails. Defaults to the display name.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('primary_color'):
            self.initial['primary_color'] = self.BOOTSTRAP_PRIMARY

    def clean_primary_color(self):
        color = (self.cleaned_data.get('primary_color') or '').lower()
        if color == self.BOOTSTRAP_PRIMARY:
            return ''
        return color


class TerminologyForm(forms.Form):
    """A singular and a plural field per term, pre-filled with the effective words."""

    def __init__(self, *args, terms=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.terms = terms or Terms()
        for key, singular, plural, _ in TERMS:
            self.fields[key] = self._word_field(singular, self.terms.get(key))
            self.fields[PLURAL_KEYS[key]] = self._word_field(plural, self.terms.get(key, plural=True))

    @staticmethod
    def _word_field(default, current):
        return forms.CharField(
            required=False, max_length=50, label=default, initial=current,
            widget=forms.TextInput(attrs={
                'class': 'form-control form-control-sm', 'placeholder': default,
            }),
        )

    def rows(self):
        for key, singular, plural, description in TERMS:
            yield {
                'key': key,
                'singular': singular,
                'plural': plural,
                'description': description,
                'singular_field': self[key],
                'plural_field': self[PLURAL_KEYS[key]],
            }

    def save(self, org):
        org.terminology = Terms(self.cleaned_data).overrides()
        org.save(update_fields=['terminology', 'updated_at'])
        return org


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.first_name = self.cleaned_data['first_name']
        profile.user.last_name = self.cleaned_data['last_name']
        profile.user.email = self.cleaned_data['email']
        if commit:
            profile.user.save()
            profile.save()
        return profile


class InviteUserForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=Membership.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        # Set by clean() when the email belongs to an account that already
        # exists: that person is invited instead of a new account being created.
        self.existing_user = None
        teams = Team.objects.none()
        if organization:
            teams = Team.objects.filter(organization=organization)
        self.fields['teams'].queryset = teams

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username')
        email = cleaned.get('email')
        if not username or not email:
            return cleaned

        named = User.objects.filter(username=username).first()
        same_email = User.objects.filter(email__iexact=email, is_active=True)
        if named is not None:
            # The username decides, as long as the email agrees with it.
            if not named.is_active or named.email.lower() != email.lower():
                self.add_error('username', 'A user with that username already exists.')
                return cleaned
            self.existing_user = named
        else:
            matches = list(same_email[:2])
            if len(matches) > 1:
                self.add_error(
                    'email',
                    'More than one account uses this email address. '
                    'Enter the username of the person you want to invite.',
                )
                return cleaned
            if matches:
                self.existing_user = matches[0]

        if self.existing_user is not None and self.organization is not None:
            if Membership.objects.filter(
                user=self.existing_user, organization=self.organization
            ).exists():
                self.existing_user = None
                self.add_error('email', f'This person is already in {self.organization.name}.')
        return cleaned


class TeamMemberForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Members',
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = User.objects.none()
        if organization:
            users = (
                User.objects
                .filter(memberships__organization=organization)
                .order_by('first_name', 'username')
            )
        self.fields['users'].queryset = users
