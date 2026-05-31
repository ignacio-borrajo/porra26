import secrets

from django import forms

from accounts.models import User
from accounts.validators import validate_email_domain


class PlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "dept", "sede", "puesto", "is_jugador", "is_gestor"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "dept": forms.Select(attrs={"class": "input"}),
            "sede": forms.Select(attrs={"class": "input"}),
            "puesto": forms.Select(attrs={"class": "input"}),
            "is_jugador": forms.CheckboxInput(),
            "is_gestor": forms.CheckboxInput(),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email


def generate_temp_password() -> str:
    return secrets.token_urlsafe(9)
