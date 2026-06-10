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
    partial_points = 1
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
    external_id = None

    @factory.post_generation
    def _seed_points_applied(self, create, extracted, **kwargs):
        """Si el match se crea ya con resultado pero sin snapshot, lo congela
        con los puntos vigentes en la ronda. Imita la siembra que hace
        resolve_match() en producción y evita que los tests tengan que
        repetir exact_points_applied/partial_points_applied en cada llamada."""
        if not create:
            return
        if self.result_home is None or self.result_away is None:
            return
        if self.exact_points_applied is not None:
            return
        self.exact_points_applied = self.round.points
        self.partial_points_applied = self.round.partial_points
        self.save(update_fields=["exact_points_applied", "partial_points_applied"])


class PredictionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prediction

    player = factory.SubFactory("accounts.tests.factories.UserFactory")
    match = factory.SubFactory(MatchFactory)
    home = 1
    away = 0
