from django.contrib import admin

from competition.models import BetsClosingReport


@admin.register(BetsClosingReport)
class BetsClosingReportAdmin(admin.ModelAdmin):
    list_display = ("match", "generated_at", "sent_at", "attempts")
    list_filter = ("sent_at",)
    search_fields = ("match__home__name", "match__away__name")
    readonly_fields = ("created_at", "last_sha256")
    fields = ("match", "generated_at", "sent_at", "attempts", "last_sha256", "created_at")
