from django.contrib import admin
from django.utils import timezone

from .models import Feedback, Service, ServiceTag


@admin.register(ServiceTag)
class ServiceTagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "campus", "is_published", "is_featured", "verified_on"]
    list_filter = ["campus", "is_published", "tags"]
    search_fields = ["name", "offers"]
    filter_horizontal = ["tags"]
    readonly_fields = ["verified_by", "verified_on"]
    actions = ["verify_and_publish"]

    @admin.action(description="Mark verified by me and publish")
    def verify_and_publish(self, request, queryset):
        count = queryset.update(
            verified_by=request.user, verified_on=timezone.localdate(), is_published=True,
        )
        self.message_user(request, f"{count} service(s) verified and published.")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["created_on", "category", "rating", "short_message"]
    list_filter = ["category", "rating", "created_on"]
    readonly_fields = ["category", "message", "rating", "created_on"]

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message[:80]

    def has_add_permission(self, request):
        return False  # feedback only ever comes from the anonymous form
