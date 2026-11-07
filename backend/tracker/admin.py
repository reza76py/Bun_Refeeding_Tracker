from django.contrib import admin

from tracker.models import Aisle, AisleCage, AssumptionSet, Bay, CageLog, Store, WorkDay


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "timezone")


@admin.register(Aisle)
class AisleAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "store", "active")


@admin.register(Bay)
class BayAdmin(admin.ModelAdmin):
    list_display = ("id", "aisle", "bay_number", "estimated_catalogue_lines")


@admin.register(AisleCage)
class AisleCageAdmin(admin.ModelAdmin):
    list_display = ("id", "aisle", "code", "lines")


@admin.register(AssumptionSet)
class AssumptionSetAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "version", "provenance", "effective_at")


@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "work_date", "store", "assumption_set")


@admin.register(CageLog)
class CageLogAdmin(admin.ModelAdmin):
    list_display = ("id", "work_day", "status", "estimated_seconds", "actual_active_seconds")
