import secrets

from django import forms

from accounts.models import User
from accounts.validators import validate_email_domain


class PlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "dept", "role"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email


def generate_temp_password() -> str:
    return secrets.token_urlsafe(9)
