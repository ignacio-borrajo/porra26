from competition.models import Prediction


def streak(player_id: int) -> int:
    rows = (
        Prediction.objects.filter(player_id=player_id, earned__isnull=False)
        .order_by("-match__kickoff")
        .values_list("earned", flat=True)
    )
    n = 0
    for e in rows:
        if e and e > 0:
            n += 1
        else:
            break
    return n
