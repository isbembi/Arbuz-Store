from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Customer


class UserRegisterForm(UserCreationForm):
    """
    Extended registration form with email field.
    Extends Django's built-in UserCreationForm to include email.
    """
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap styling to form fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        # Change help text labels
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm Password'

    def clean_email(self):
        """Ensure email is unique in the database."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email


class UserLoginForm(forms.Form):
    """
    Simple login form for authentication.
    Takes username and password only.
    """
    username = forms.CharField(
        label='Username',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'})
    )
