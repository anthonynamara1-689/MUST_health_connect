from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import AuditLog, Event, Item, Location, PolicyActivity, StockLevel, StockMovement
from .services import StockError, issue_stock, issue_stock_with_procedure


class StockTransactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.item = Item.objects.create(name="Test kits", category="commodity", reorder_level=2)
        cls.location = Location.objects.create(name="Test point", campus="town", is_pickup_point=True)
        cls.level = StockLevel.objects.create(item=cls.item, location=cls.location, quantity=5)

    def issue(self, qty):
        return issue_stock(item_id=self.item.pk, location_id=self.location.pk,
                           qty=qty, event_id=None, user_id=None)

    def test_issue_reduces_stock_and_logs_movement(self):
        remaining, log = self.issue(3)
        self.level.refresh_from_db()
        self.assertEqual((remaining, self.level.quantity), (2, 2))
        self.assertEqual(StockMovement.objects.get().qty_change, -3)
        self.assertEqual(log[-1]["kind"], "ok")

    def test_over_issue_rolls_back(self):
        with self.assertRaises(StockError):
            self.issue(9)
        self.level.refresh_from_db()
        self.assertEqual(self.level.quantity, 5)
        self.assertFalse(StockMovement.objects.exists())

    @override_settings(HC_FAIL_AFTER_UPDATE=True)
    def test_crash_after_update_is_undone(self):
        with self.assertRaises(StockError):
            self.issue(1)
        self.level.refresh_from_db()
        self.assertEqual(self.level.quantity, 5)

    def test_trigger_writes_audit_log(self):
        self.issue(1)
        self.assertTrue(AuditLog.objects.filter(table_name="stock_level", action="UPDATE").exists())

    def test_check_constraint_blocks_negative_stock(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE stock_level SET quantity = -1 WHERE id = %s", [self.level.pk])

    def test_stored_procedure(self):
        issue_stock_with_procedure(item_id=self.item.pk, location_id=self.location.pk, qty=2)
        self.level.refresh_from_db()
        self.assertEqual(self.level.quantity, 3)


class StaffPageTests(TestCase):
    databases = {"default", "reports"}

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("peer", password="test-pass-123")

    def test_staff_pages_need_login(self):
        for name in ("tracker:report", "tracker:events", "tracker:stock"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_report_reads_views_through_reports_connection(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("tracker:report")).status_code, 200)

    def test_health_check(self):
        response = self.client.get(reverse("health_db"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["default"]["ok"])


class DemoDataPageTests(TransactionTestCase):
    """The staff pages with the seed data loaded, as in the live demo.

    TransactionTestCase commits the seed data for real. A plain TestCase keeps it
    in an open transaction on "default", which the separate "reports" connection
    cannot see, so the report would show zeros.
    """
    databases = {"default", "reports"}

    def setUp(self):
        call_command("seed_demo", stdout=StringIO())
        self.user = get_user_model().objects.get(username="peer1")
        self.client.force_login(self.user)

    def test_all_staff_pages_render_with_data(self):
        for name in ("tracker:report", "tracker:events", "tracker:stock"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_report_totals_come_from_the_views(self):
        summary = self.client.get(reverse("tracker:report")).context["summary"]
        self.assertGreater(summary["spent"], 0)
        self.assertGreater(summary["reached"], 0)

    def test_attendance_saves_eight_rows_in_one_go(self):
        page = self.client.get(reverse("tracker:events"))
        event = page.context["selected"]
        self.assertTrue(event.can_record_attendance)
        data = {"event": event.pk, **{f"{g}_{y}": 2 for g in "fm" for y in range(1, 5)}}
        self.client.post(reverse("tracker:events"), data)
        self.assertEqual(event.attendance.count(), 8)
        self.assertEqual(sum(a.headcount for a in event.attendance.all()), 16)


class StaffInteractionTests(TransactionTestCase):
    """The dialogs and switches on the staff pages."""
    databases = {"default", "reports"}

    def setUp(self):
        call_command("seed_demo", stdout=StringIO())
        self.user = get_user_model().objects.get(username="peer1")
        self.client.force_login(self.user)

    def test_plan_event_dialog_creates_event(self):
        activity = PolicyActivity.objects.first()
        location = Location.objects.first()
        response = self.client.post(reverse("tracker:events"), {
            "action": "plan", "title": "Testing day at Town campus", "activity": activity.pk,
            "event_date": "2026-12-09", "location": location.pk, "is_public": "on",
        })
        event = Event.objects.get(title="Testing day at Town campus")
        self.assertRedirects(response, f"{reverse('tracker:events')}?event={event.pk}")
        self.assertEqual(event.organiser, self.user)

    def test_invalid_plan_keeps_dialog_open(self):
        response = self.client.post(reverse("tracker:events"), {"action": "plan", "title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["plan_open"])

    def test_crash_switch_rolls_back(self):
        level = StockLevel.objects.select_related("item").first()
        before = level.quantity
        self.client.post(reverse("tracker:stock"), {
            "item": level.item_id, "location": level.location_id, "quantity": 1, "simulate_crash": "on",
        })
        level.refresh_from_db()
        self.assertEqual(level.quantity, before)
        self.assertFalse(StockMovement.objects.exists())
