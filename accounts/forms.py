from django import forms
from django.contrib.auth import authenticate

from .models import User
from .services.avatar import UnidentifiedImageError, process_avatar
from .validators import validate_email_domain

MAX_AVATAR_BYTES = 2 * 1024 * 1024

INPUT_ATTRS = {"class": "input"}


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs=INPUT_ATTRS))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs=INPUT_ATTRS))

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
    current = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput(attrs=INPUT_ATTRS),
    )
    new1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs=INPUT_ATTRS),
        min_length=10,
    )
    new2 = forms.CharField(
        label="Repite la contraseña",
        widget=forms.PasswordInput(attrs=INPUT_ATTRS),
        min_length=10,
    )

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
        fields = ["name", "sede", "puesto", "dept", "avatar"]
        labels = {
            "name": "Nombre",
            "sede": "Sede",
            "puesto": "Puesto",
            "dept": "Departamento",
            "avatar": "Foto de perfil",
        }
        widgets = {
            "name": forms.TextInput(attrs=INPUT_ATTRS),
            "sede": forms.Select(attrs=INPUT_ATTRS),
            "puesto": forms.Select(attrs=INPUT_ATTRS),
            "dept": forms.Select(attrs=INPUT_ATTRS),
            "avatar": forms.FileInput(
                attrs={"class": "avatar-input", "accept": "image/jpeg,image/png,image/webp"}
            ),
        }

    def clean_name(self):
        value = (self.cleaned_data.get("name") or "").strip()
        if not value:
            raise forms.ValidationError("El nombre es obligatorio.")
        return value

    def clean_avatar(self):
        f = self.cleaned_data.get("avatar")
        if not f or not hasattr(f, "size"):
            return f
        if f.size > MAX_AVATAR_BYTES:
            raise forms.ValidationError("La foto no puede pesar más de 2 MB.")
        try:
            return process_avatar(f)
        except (UnidentifiedImageError, OSError) as err:
            raise forms.ValidationError("El archivo no es una imagen válida.") from err


class TeamProfileForm(forms.ModelForm):
    """Form mínimo para el modal de incentivo al perfil de equipo: solo sede,
    departamento y puesto, los tres obligatorios."""

    class Meta:
        model = User
        fields = ["sede", "dept", "puesto"]
        labels = {
            "sede": "Sede",
            "dept": "Departamento",
            "puesto": "Puesto",
        }
        widgets = {
            "sede": forms.Select(attrs=INPUT_ATTRS),
            "dept": forms.Select(attrs=INPUT_ATTRS),
            "puesto": forms.Select(attrs=INPUT_ATTRS),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("sede", "dept", "puesto"):
            field = self.fields[field_name]
            field.required = True
            field.choices = [("", "Selecciona…")] + [c for c in field.choices if c[0]]
