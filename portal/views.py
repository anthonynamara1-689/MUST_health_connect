import re

from django.conf import settings
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from tracker.models import Event

from .content import CAMPUS_CHOICES, FEEDBACK_ICONS, RIGHTS, TOPICS
from .forms import FeedbackForm
from .models import Feedback, Service, ServiceTag


# Home page slider: every photo in this folder is shown, in file-name order.
HERO_DIR = settings.BASE_DIR / "static" / "img" / "hero"
HERO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def hero_slides():
    """Photos for the home page slider. Drop files into static/img/hero/ to add slides.

    Name files so they sort in the order you want, e.g. 1-peer-talk.jpg, 2-testing-day.jpg.
    The name (without the number) becomes the alt text read out by screen readers.
    """
    photos = sorted(p for p in HERO_DIR.glob("*") if p.suffix.lower() in HERO_TYPES) if HERO_DIR.is_dir() else []
    if not photos:
        return [{"src": "img/hero.jpg", "alt": "Students at a peer education talk on campus"}]
    return [
        {
            "src": f"img/hero/{photo.name}",
            "alt": re.sub(r"^\d+[-_ ]*", "", photo.stem).replace("-", " ").replace("_", " ").capitalize(),
        }
        for photo in photos
    ]


def published_services():
    # prefetch_related loads every service's tags in ONE extra query, not one per service.
    return Service.objects.filter(is_published=True).prefetch_related("tags")


def public_events():
    """Events students may see: public and not cancelled."""
    return (
        Event.objects.filter(is_public=True)
        .exclude(status=Event.Status.CANCELLED)
        .select_related("location")
    )


def home(request):
    today = timezone.localdate()
    next_event = (
        public_events()
        .filter(status=Event.Status.PLANNED, event_date__gte=today)
        .order_by("event_date")
        .first()
    )
    return render(request, "portal/home.html", {
        "topics": TOPICS,
        "rights": RIGHTS,
        "hero_slides": hero_slides(),
        "popular": published_services().filter(is_featured=True)[:3],
        "service_count": Service.objects.filter(is_published=True).count(),
        "next_event": next_event,
        "days_to_event": (next_event.event_date - today).days if next_event else None,
        "campus_choices": CAMPUS_CHOICES,
    })


def topics(request):
    return render(request, "portal/topics.html", {"topics": TOPICS, "rights": RIGHTS})


def directory(request):
    q = request.GET.get("q", "").strip()
    tag = request.GET.get("tag", "")
    campus = request.GET.get("campus", "")

    services = published_services()
    if q:
        # The ORM sends q as a parameter, never pasted into the SQL text.
        services = services.filter(
            Q(name__icontains=q) | Q(offers__icontains=q) | Q(tags__name__icontains=q)
        ).distinct()
    if tag:
        services = services.filter(tags__slug=tag)
    if campus:
        services = services.filter(campus=campus)

    # One GROUP BY query: how many published services each tag has (for the filter counts).
    # (Meta.ordering is ignored in GROUP BY queries, so order_by is needed here.)
    tags = list(
        ServiceTag.objects.annotate(total=Count("services", filter=Q(services__is_published=True)))
        .filter(total__gt=0)
        .order_by("name")
    )

    services = list(services.order_by("name"))
    # ?open=<id> opens that service's details when the page loads (used by the home page links).
    open_id = request.GET.get("open", "")
    open_id = int(open_id) if open_id.isdigit() and any(s.pk == int(open_id) for s in services) else None

    return render(request, "portal/directory.html", {
        "services": services,
        "open_id": open_id,
        "tags": tags,
        "all_count": Service.objects.filter(is_published=True).count(),
        "selected_tag": tag,
        "selected_tag_name": next((t.name for t in tags if t.slug == tag), ""),
        "q": q,
        "campus": campus,
        "campus_name": dict(CAMPUS_CHOICES).get(campus, ""),
        "campus_choices": CAMPUS_CHOICES,
    })


def events(request):
    today = timezone.localdate()
    events = list(public_events().order_by("event_date"))
    return render(request, "portal/events.html", {
        "upcoming": [e for e in events if e.event_date >= today and e.status == Event.Status.PLANNED],
        "past": [e for e in reversed(events) if e.event_date < today or e.status == Event.Status.HELD][:8],
    })


def feedback(request):
    initial = {}
    if request.GET.get("category") in dict(FeedbackForm.base_fields["category"].choices):
        initial["category"] = request.GET["category"]
    form = FeedbackForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        # Only the form fields are stored. Nothing from the request (user, IP) is saved.
        Feedback.objects.create(**form.cleaned_data)
        return redirect(reverse("portal:feedback") + "?sent=1")
    return render(request, "portal/feedback.html", {
        "form": form,
        "sent": request.GET.get("sent") == "1",
        "category_icons": FEEDBACK_ICONS,
    })
