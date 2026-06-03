from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from competition.models import BET_CLOSE_HOURS, Round
from pot.models import PotSettings, Prize


class RulesView(LoginRequiredMixin, TemplateView):
    template_name = "core/rules.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pot_settings = PotSettings.load()
        ctx["rounds"] = Round.objects.all()
        ctx["pot_per_player"] = pot_settings.per_player
        ctx["pot_prizes"] = Prize.objects.filter(scope="global").order_by("position")
        ctx["bet_close_hours"] = BET_CLOSE_HOURS
        ctx["rules_updated_at"] = settings.RULES_UPDATED_AT
        ctx["matchday_winner_prize"] = pot_settings.matchday_winner_prize
        ctx["maintenance_cost"] = pot_settings.maintenance_cost
        return ctx
