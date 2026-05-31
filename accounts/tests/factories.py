import factory

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@edisa.com")
    name = factory.Faker("name", locale="es_ES")
    dept = "desarrollo"  # se ignora — `dept` ya no acepta "desarrollo"; sobrescribimos abajo
    is_jugador = True
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.pop("dept", None)  # quita el valor inválido por defecto
        password = kwargs.pop("password", "test-password")
        user = model_class.objects.create_user(password=password, **kwargs)
        return user


class GestorFactory(UserFactory):
    is_jugador = True
    is_gestor = True
