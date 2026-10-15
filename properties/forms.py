from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class StaffCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "phone")


class StaffChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "phone", "first_name", "last_name")


class OTPCodeForm(forms.Form):
    code = forms.RegexField(regex=r"^\d{6}$", max_length=6, widget=forms.TextInput(attrs={
        "autocomplete": "one-time-code",
        "inputmode": "numeric",
        "autofocus": True,
    }))
