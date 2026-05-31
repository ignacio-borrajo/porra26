import factory
from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@edisa.com")
    name = factory.Faker("name", locale="es_ES")
    dept = "Desarrollo"
    role = "jugador"
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "test-password")
        user = model_class.objects.create_user(password=password, **kwargs)
        return user


class GestorFactory(UserFactory):
    role = "gestor"
