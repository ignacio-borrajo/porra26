from django import forms
from django.contrib.auth import authenticate

from accounts.models import User

from .validators import validate_email_domain


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email

    def get_user(self, request):
        return authenticate(
            request,
            email=self.cleaned_data.get("email"),
            password=self.cleaned_data.get("password"),
        )


class ChangePasswordForm(forms.Form):
    current = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    new1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput, min_length=10)
    new2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput, min_length=10)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current(self):
        if not self.user.check_password(self.cleaned_data["current"]):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return self.cleaned_data["current"]

    def clean(self):
        c = super().clean()
        if c.get("new1") and c.get("new2") and c["new1"] != c["new2"]:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        if c.get("new1"):
            pwd = c["new1"]
            if not any(ch.isupper() for ch in pwd) or not any(ch.isdigit() for ch in pwd):
                raise forms.ValidationError(
                    "La contraseña debe tener al menos una mayúscula y un dígito."
                )
        return c


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "dept", "sede", "puesto"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "dept": forms.Select(attrs={"class": "input"}),
            "sede": forms.Select(attrs={"class": "input"}),
            "puesto": forms.Select(attrs={"class": "input"}),
        }
