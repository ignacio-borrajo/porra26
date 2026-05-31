from decimal import Decimal
from pot.models import Payment, PotSettings


def app_context(request):
    try:
        per = PotSettings.load().per_player
    except Exception:
        per = Decimal("10")
    paid_count = Payment.objects.filter(paid=True).count()
    return {
        "app_version": "0.1.0",
        "pot_total": int(per * paid_count),
    }
