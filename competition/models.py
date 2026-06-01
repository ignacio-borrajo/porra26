from datetime import timedelta

from django.db import models
from django.utils import timezone


class Team(models.Model):
    code = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=80)
    flag = models.CharField(max_length=8)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Round(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    label = models.CharField(max_length=40)
    short = models.CharField(max_length=10)
    points = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label


class Match(models.Model):
    round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="matches")
    group = models.CharField(max_length=20)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    home = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_matches")
    away = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_matches")
    kickoff = models.DateTimeField()
    result_home = models.PositiveSmallIntegerField(null=True, blank=True)
    result_away = models.PositiveSmallIntegerField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["kickoff"]
        indexes = [
            models.Index(fields=["round", "matchday", "kickoff"]),
            models.Index(fields=["finished_at"]),
        ]

    def __str__(self):
        return f"{self.home_id} vs {self.away_id} @ {self.kickoff:%Y-%m-%d %H:%M}"

    @property
    def has_result(self) -> bool:
        return self.result_home is not None and self.result_away is not None

    @property
    def status(self) -> str:
        now = timezone.now()
        if self.has_result:
            return "done"
        close_at = self.kickoff - timedelta(hours=2)
        if now >= self.kickoff:
            return "live"
        if now >= close_at:
            return "closed"
        if close_at - now <= timedelta(hours=2):
            return "closing"
        return "open"

    @property
    def editable(self) -> bool:
        return self.status in ("open", "closing")

    @property
    def predictions_open(self) -> bool:
        """True solo si el partido es editable Y su jornada está desbloqueada."""
        if not self.editable:
            return False
        from competition.services.matchday_gate import is_matchday_open

        return is_matchday_open(self.round_id, self.matchday)


class Prediction(models.Model):
    player = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="predictions"
    )
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    home = models.PositiveSmallIntegerField()
    away = models.PositiveSmallIntegerField()
    earned = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "match"], name="uniq_pred_per_player_match"),
        ]
        indexes = [models.Index(fields=["match", "player"])]

    def __str__(self):
        return f"{self.player_id} → {self.match_id}"
