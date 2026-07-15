from django.contrib import admin

from .models import Raffle, RaffleEntry


class RaffleEntryInline(admin.TabularInline):
    model = RaffleEntry
    extra = 0
    raw_id_fields = ["player"]


@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    inlines = [RaffleEntryInline]
