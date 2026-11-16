from django.urls import path

from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.report, name="report"),
    path("events/", views.events, name="events"),
    path("stock/", views.stock, name="stock"),
]
