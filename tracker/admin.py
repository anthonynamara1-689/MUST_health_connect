from django.contrib import admin

from .models import (
    AuditLog, Event, EventAttendance, Expenditure, Item, Location,
    PeerEducator, PolicyActivity, StockLevel, StockMovement,
)


@admin.register(PolicyActivity)
class PolicyActivityAdmin(admin.ModelAdmin):
    list_display = ["name", "thematic_area", "schedule", "target_value", "target_measure",
                    "annual_budget_ugx", "funding_source"]


class AttendanceInline(admin.TabularInline):
    model = EventAttendance
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "event_date", "location", "activity", "status", "is_public"]
    list_filter = ["status", "activity", "location"]
    date_hierarchy = "event_date"
    search_fields = ["title"]
    inlines = [AttendanceInline]
    exclude = ["organiser"]

    def save_model(self, request, obj, form, change):
        if not obj.organiser_id:
            obj.organiser = request.user
        super().save_model(request, obj, form, change)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "campus", "is_pickup_point"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "unit", "reorder_level"]


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ["item", "location", "quantity"]
    list_filter = ["location", "item"]


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdmin):
    list_display = ["moved_at", "reason", "item", "location", "qty_change", "event", "user"]
    list_filter = ["reason", "location", "item"]


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ["changed_at", "action", "table_name", "row_id"]
    list_filter = ["action", "table_name"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Expenditure)
class ExpenditureAdmin(admin.ModelAdmin):
    list_display = ["spent_on", "activity", "amount_ugx", "event", "receipt_ref"]
    list_filter = ["activity"]


@admin.register(PeerEducator)
class PeerEducatorAdmin(admin.ModelAdmin):
    list_display = ["user", "faculty", "cohort_year", "trained_on"]
