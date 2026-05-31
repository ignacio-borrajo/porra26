import factory

from pot.models import Payment, Prize


class PrizeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prize

    scope = "global"
    position = 1
    amount = 200
    label = "1er premio"


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    player = factory.SubFactory("accounts.tests.factories.UserFactory")
    paid = False
