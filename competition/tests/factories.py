from datetime import timedelta

import factory
from django.utils import timezone

from competition.models import Match, Prediction, Round, Team


class RoundFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Round
        django_get_or_create = ("id",)

    id = "groups"
    label = "Fase de grupos"
    short = "GRP"
    points = 3
    order = 1


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"T{n:02d}")
    name = factory.Sequence(lambda n: f"Equipo {n}")
    flag = "🏳️"


class MatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Match

    round = factory.SubFactory(RoundFactory)
    group = "A"
    matchday = 1
    home = factory.SubFactory(TeamFactory)
    away = factory.SubFactory(TeamFactory)
    kickoff = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))


class PredictionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prediction

    player = factory.SubFactory("accounts.tests.factories.UserFactory")
    match = factory.SubFactory(MatchFactory)
    home = 1
    away = 0
