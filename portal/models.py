from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .content import CAMPUS_CHOICES, FEEDBACK_CATEGORIES


class ServiceTag(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "service_tag"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Service(models.Model):
    """A verified support service shown in the public directory."""

    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=120, blank=True)
    offers = models.TextField()
    location_text = models.CharField(max_length=150)
    campus = models.CharField(max_length=20, choices=CAMPUS_CHOICES)
    hours = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    tags = models.ManyToManyField(ServiceTag, related_name="services", blank=True)
    is_featured = models.BooleanField(default=False, help_text="Show under 'Popular right now'.")
    is_published = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    verified_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "service"
        ordering = ["name"]
        constraints = [
            # A service can only be published once someone has verified it.
            models.CheckConstraint(
                condition=Q(is_published=False) | Q(verified_on__isnull=False),
                name="service_published_needs_verification",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        return self.tags.all()


class Feedback(models.Model):
    """Anonymous by design: no user, no IP address, no time of day."""

    category = models.CharField(max_length=20, choices=FEEDBACK_CATEGORIES)
    message = models.TextField(max_length=2000)
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_on = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "feedback"
        ordering = ["-created_on", "-id"]
        verbose_name_plural = "feedback"
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__isnull=True) | Q(rating__gte=1, rating__lte=5),
                name="feedback_rating_1_to_5",
            ),
        ]

    def __str__(self):
        return f"{self.get_category_display()} ({self.created_on})"
