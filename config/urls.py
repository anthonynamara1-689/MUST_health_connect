from django.contrib import admin
from django.urls import include, path

from tracker.views import health_db

admin.site.site_header = "MUST HealthConnect admin"
admin.site.site_title = "MUST HealthConnect"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("health/db/", health_db, name="health_db"),
    path("staff/", include("tracker.urls")),
    path("", include("portal.urls")),
]
