from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone

from portal.content import CAMPUS_CHOICES


class PolicyActivity(models.Model):
    """One budget line from section 9.0 of the MUST HIV/AIDS Policy."""

    class Measure(models.TextChoices):
        PEOPLE = "people", "People reached at events"
        EVENTS = "events", "Events held"
        NONE = "none", "Not a number"

    thematic_area = models.CharField(max_length=80)
    name = models.CharField(max_length=120)
    schedule = models.CharField(max_length=50)
    indicator = models.CharField(max_length=160)
    target_value = models.PositiveIntegerField(
        null=True, blank=True, help_text="Leave blank when the target is not a number.",
    )
    target_measure = models.CharField(max_length=10, choices=Measure.choices, default=Measure.PEOPLE)
    annual_budget_ugx = models.PositiveBigIntegerField()  # PostgreSQL CHECK (>= 0)
    funding_source = models.CharField(max_length=80)

    class Meta:
        db_table = "policy_activity"
        ordering = ["id"]
        verbose_name_plural = "policy activities"

    def __str__(self):
        return self.name


class PeerEducator(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="peer_educator",
    )
    faculty = models.CharField(max_length=80)
    cohort_year = models.PositiveSmallIntegerField()
    trained_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "peer_educator"

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Location(models.Model):
    name = models.CharField(max_length=80, unique=True)
    campus = models.CharField(max_length=20, choices=CAMPUS_CHOICES)
    is_pickup_point = models.BooleanField(default=False)

    class Meta:
        db_table = "location"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        HELD = "held", "Held"
        CANCELLED = "cancelled", "Cancelled"

    activity = models.ForeignKey(PolicyActivity, on_delete=models.PROTECT, related_name="events")
    title = models.CharField(max_length=120)
    event_date = models.DateField()
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="events")
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    is_public = models.BooleanField(default=True, help_text="Show on the student home page.")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "event"
        ordering = ["-event_date"]
        indexes = [models.Index(fields=["event_date"], name="event_date_idx")]

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    @property
    def can_record_attendance(self):
        return self.status != self.Status.CANCELLED and self.event_date <= timezone.localdate()


class EventAttendance(models.Model):
    """Headcounts only. Never names or student numbers."""

    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance")
    gender = models.CharField(max_length=1, choices=Gender.choices)
    year_of_study = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)], help_text="4 means year 4 or above.",
    )
    headcount = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "event_attendance"
        verbose_name_plural = "event attendance"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "gender", "year_of_study"], name="attendance_one_row_per_group",
            ),
            models.CheckConstraint(
                condition=Q(year_of_study__gte=1, year_of_study__lte=4), name="attendance_year_1_to_4",
            ),
        ]

    def __str__(self):
        return f"{self.event} · {self.gender} · year {self.year_of_study}: {self.headcount}"


class Item(models.Model):
    class Category(models.TextChoices):
        COMMODITY = "commodity", "Commodity"
        IEC = "iec", "IEC material"

    name = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=10, choices=Category.choices)
    unit = models.CharField(max_length=20, default="piece")
    reorder_level = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "item"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockLevel(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="stock_levels")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="stock_levels")
    quantity = models.PositiveIntegerField(default=0)  # PostgreSQL CHECK (quantity >= 0)

    class Meta:
        db_table = "stock_level"
        constraints = [
            models.UniqueConstraint(fields=["item", "location"], name="stock_one_row_per_item_location"),
        ]

    def __str__(self):
        return f"{self.item} at {self.location}: {self.quantity}"

    @property
    def is_low(self):
        return self.quantity < self.item.reorder_level


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        RECEIVED = "received", "Received"
        ISSUED = "issued", "Issued"
        ADJUSTED = "adjusted", "Adjusted"

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="movements")
    qty_change = models.IntegerField()
    reason = models.CharField(max_length=10, choices=Reason.choices)
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="movements")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    moved_at = models.DateTimeField(db_default=Now())  # PostgreSQL fills it in, even from raw SQL

    class Meta:
        db_table = "stock_movement"
        ordering = ["-moved_at"]
        indexes = [models.Index(fields=["item", "moved_at"], name="movement_item_time_idx")]
        constraints = [
            models.CheckConstraint(condition=~Q(qty_change=0), name="movement_not_zero"),
        ]

    def __str__(self):
        return f"{self.reason} {self.qty_change} × {self.item}"


class Expenditure(models.Model):
    activity = models.ForeignKey(PolicyActivity, on_delete=models.PROTECT, related_name="expenditures")
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenditures")
    amount_ugx = models.PositiveBigIntegerField()
    spent_on = models.DateField()
    receipt_ref = models.CharField(max_length=60, blank=True)

    class Meta:
        db_table = "expenditure"
        ordering = ["-spent_on"]
        constraints = [
            models.CheckConstraint(condition=Q(amount_ugx__gt=0), name="expenditure_positive"),
        ]

    def __str__(self):
        return f"UGX {self.amount_ugx:,} on {self.activity}"


class AuditLog(models.Model):
    """Filled by a PostgreSQL trigger on stock_level, never by Django code."""

    table_name = models.CharField(max_length=60)
    row_id = models.BigIntegerField()
    action = models.CharField(max_length=10)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    changed_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "audit_log"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.action} {self.table_name}#{self.row_id}"
