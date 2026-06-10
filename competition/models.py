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
    partial_points = models.PositiveSmallIntegerField(default=1)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label


class Match(models.Model):
    round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="matches")
    group = models.CharField(max_length=20)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    home = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="home_matches",
        null=True,
        blank=True,
    )
    away = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="away_matches",
        null=True,
        blank=True,
    )
    home_slot = models.CharField(max_length=12, blank=True)
    away_slot = models.CharField(max_length=12, blank=True)
    bracket_code = models.CharField(max_length=12, blank=True, null=True, unique=True)
    external_id = models.CharField(max_length=64, blank=True, null=True, unique=True)
    kickoff = models.DateTimeField()
    result_home = models.PositiveSmallIntegerField(null=True, blank=True)
    result_away = models.PositiveSmallIntegerField(null=True, blank=True)
    exact_points_applied = models.PositiveSmallIntegerField(null=True, blank=True)
    partial_points_applied = models.PositiveSmallIntegerField(null=True, blank=True)
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
    def has_teams(self) -> bool:
        return self.home_id is not None and self.away_id is not None

    @property
    def status(self) -> str:
        if self.has_result:
            return "done"
        if not self.has_teams:
            return "pending_teams"
        if timezone.now() >= self.kickoff:
            return "live"
        return "open"

    @property
    def editable(self) -> bool:
        return self.has_teams and self.status == "open"

    @property
    def predictions_open(self) -> bool:
        """True si el partido es editable. Ya no depende del gate de jornada."""
        return self.editable

    @property
    def awaiting_validation(self) -> bool:
        """True si el partido terminó (provider reporta FT) y el gestor aún no
        ha confirmado el resultado oficial. Visualmente la card deja de pintarse
        como "En juego" y pasa al estado intermedio "Pendiente oficial"."""
        if self.has_result:
            return False
        ls = getattr(self, "live_score", None)
        return ls is not None and ls.period == "FT"

    @property
    def teams_slug(self) -> str:
        return f"{self.home_id.lower()}-vs-{self.away_id.lower()}-{self.kickoff:%Y-%m-%d}"


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


class BetsClosingReport(models.Model):
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="closing_report",
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["sent_at"])]

    def __str__(self):
        return f"ClosingReport(match={self.match_id}, sent={self.sent_at is not None})"


class LiveScore(models.Model):
    """Marcador parcial de un partido en juego.

    Espejo de lo que reporta el sports API externo. NO sustituye a
    `Match.result_home`/`result_away`, que son el resultado oficial que solo
    fija el gestor y congelan los puntos. Cuando el gestor introduce el
    oficial, este registro puede quedarse o borrarse — es irrelevante.
    """

    PERIOD_PRE = "PRE"
    PERIOD_FIRST_HALF = "1H"
    PERIOD_HALFTIME = "HT"
    PERIOD_SECOND_HALF = "2H"
    PERIOD_EXTRA_TIME = "ET"
    PERIOD_PENALTIES = "PEN"
    PERIOD_FULL_TIME = "FT"
    PERIOD_CHOICES = [
        (PERIOD_PRE, "Antes del saque"),
        (PERIOD_FIRST_HALF, "1ª parte"),
        (PERIOD_HALFTIME, "Descanso"),
        (PERIOD_SECOND_HALF, "2ª parte"),
        (PERIOD_EXTRA_TIME, "Prórroga"),
        (PERIOD_PENALTIES, "Penaltis"),
        (PERIOD_FULL_TIME, "Final"),
    ]

    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="live_score",
    )
    home_score = models.PositiveSmallIntegerField(default=0)
    away_score = models.PositiveSmallIntegerField(default=0)
    minute = models.PositiveSmallIntegerField(null=True, blank=True)
    period = models.CharField(max_length=4, choices=PERIOD_CHOICES, default=PERIOD_PRE)
    source = models.CharField(max_length=40, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]

    def __str__(self):
        return (
            f"LiveScore(match={self.match_id}, {self.home_score}-{self.away_score}, {self.period})"
        )


class BetsReminderLog(models.Model):
    KIND_T_MINUS_2H = "T_MINUS_2H"
    KIND_T_MINUS_30M = "T_MINUS_30M"
    KIND_MANUAL = "MANUAL"
    KIND_CHOICES = [
        (KIND_T_MINUS_2H, "2 h antes del saque"),
        (KIND_T_MINUS_30M, "30 min antes del saque"),
        (KIND_MANUAL, "Manual"),
    ]
    AUTO_KINDS = (KIND_T_MINUS_2H, KIND_T_MINUS_30M)

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="reminder_logs")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    sent_at = models.DateTimeField()
    pending_count = models.PositiveSmallIntegerField()
    pending_names = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "kind"], name="uniq_reminder_per_match_kind"),
        ]
        indexes = [models.Index(fields=["sent_at"])]

    def __str__(self):
        return f"ReminderLog(match={self.match_id}, kind={self.kind}, sent={self.sent_at})"
