from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("topics/", views.topics, name="topics"),
    path("support/", views.directory, name="directory"),
    path("events/", views.events, name="events"),
    path("ask/", views.feedback, name="feedback"),
]
