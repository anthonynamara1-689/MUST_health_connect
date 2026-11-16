from django.test import TestCase
from django.urls import reverse

from .models import Feedback, Service


class PortalTests(TestCase):
    def test_feedback_is_saved_without_identity(self):
        self.client.post(reverse("portal:feedback"),
                         {"category": "question", "message": "Hello", "rating": "4"})
        self.assertEqual(Feedback.objects.get().rating, 4)
        columns = {f.name for f in Feedback._meta.get_fields()}
        self.assertEqual(columns, {"id", "category", "message", "rating", "created_on"})

    def test_search_box_cannot_inject_sql(self):
        response = self.client.get(reverse("portal:directory"), {"q": "'; DROP TABLE service; --"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Service.objects.count(), 0)  # the table still exists

    def test_public_pages_load(self):
        for name in ("portal:home", "portal:topics", "portal:directory", "portal:events", "portal:feedback"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
