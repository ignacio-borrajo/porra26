from django.apps import AppConfig


class CompetitionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "competition"

    def ready(self):
        from auditlog.registry import auditlog

        from competition.models import Match, Prediction

        auditlog.register(
            Prediction,
            include_fields=["player", "match", "home", "away", "earned"],
        )
        auditlog.register(
            Match,
            include_fields=["result_home", "result_away", "finished_at"],
        )
