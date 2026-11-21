from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from portal.models import Feedback, Service, ServiceTag
from tracker.models import (
    Event, EventAttendance, Expenditure, Item, Location, PeerEducator, PolicyActivity, StockLevel,
)

GOU = "Government of Uganda"
PREVENTION = "Prevention / user-friendly HIV/AIDS sensitisation"
CARE = "HIV treatment, care and support"
PEOPLE, EVENTS, NONE = "people", "events", "none"

# Budget lines from the MUST HIV/AIDS Policy (Nov 2019), section 9.0, pages 12-13.
# key, thematic area, activity, schedule, indicator, target, measure, budget (UGX), funding
ACTIVITIES = [
    ("peer", PREVENTION, "Peer-to-peer SRH/HIV activities", "Per semester",
     "500 students sensitised per semester", 500, PEOPLE, 4_000_000, GOU),
    ("vct", PREVENTION, "Voluntary counselling and testing (AIC)", "Quarterly",
     "300 people tested per quarter", 300, PEOPLE, 1_000_000, GOU),
    ("iec", PREVENTION, "IEC materials", "Annually",
     "200 brochures, 50 T-shirts, 2 banners a year", None, NONE, 2_000_000, "AfDB-HEST V"),
    ("training", "Capacity building", "HIV/AIDS counselling training", "Annually",
     "50 members trained a year", 50, PEOPLE, 6_000_000, GOU),
    ("contraception", CARE, "Contraception purchase and education", "Per semester",
     "Receipts and distribution records per semester", None, NONE, 1_000_000, GOU),
    ("support", CARE, "Support groups and commemorations", "Twice a year",
     "2 workshops a year, e.g. World AIDS Day", 2, EVENTS, 6_000_000, GOU),
    ("research", "Research", "HIV/AIDS research, study and workplace", "Once a year",
     "1 research report a year", None, NONE, 4_000_000, GOU),
    ("review", "Review of the HIV/AIDS policy", "Review of the HIV/AIDS policy", "Once in 5 years",
     "Workshop reports, minutes, printed booklets", None, NONE, 8_000_000, GOU),
    ("me", "Monitoring and evaluation", "Monitoring and evaluation meetings", "Every four months",
     "2 meetings with minutes and attendance lists", 2, EVENTS, 4_000_000, GOU),
]

TAGS = [
    ("testing", "Testing"), ("prep", "PrEP / PEP"), ("counselling", "Counselling"),
    ("condoms", "Condoms"), ("peer", "Peer support"), ("treatment", "Treatment"),
    ("support", "Support groups"),
]

# DEMO entries. Check names, places, hours and phone numbers with each service before a real pilot.
SERVICES = [
    ("MUST Health Services with AIC", "Kihumuro campus", "kihumuro",
     "Free HIV testing and counselling, TB screening and STI testing for students and staff.",
     ["testing", "counselling"], True),
    ("MRRH HIV/AIDS Clinic", "Mbarara Regional Referral Hospital", "city",
     "HIV treatment, and PrEP and PEP following the national ART guidelines (policy clause 5.6).",
     ["prep", "treatment", "testing"], False),
    ("TASO Mbarara", "Mbarara City", "city",
     "Counselling and support for people living with or affected by HIV.",
     ["counselling", "support"], False),
    ("MUST Peer Project", "Office of the Dean of Students", "town",
     "Trained student peer educators for confidential, judgment-free conversations.",
     ["peer"], True),
    ("Condom and self-test kit pick-up", "Health Centre, Town campus, Guild office", "kihumuro",
     "Free condoms and oral HIV self-test kits. No questions asked.",
     ["condoms", "testing"], True),
]


def set_attendance(event, rows):
    """rows = [(female, male) for year 1, 2, 3, 4+]."""
    for year, (female, male) in enumerate(rows, start=1):
        for gender, count in (("F", female), ("M", male)):
            EventAttendance.objects.update_or_create(
                event=event, gender=gender, year_of_study=year, defaults={"headcount": count},
            )


class Command(BaseCommand):
    help = "Load the policy budget lines and demo data. Safe to run more than once."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()

        act = {}
        for key, area, name, schedule, indicator, target, measure, budget, source in ACTIVITIES:
            act[key], _ = PolicyActivity.objects.update_or_create(
                name=name,
                defaults={
                    "thematic_area": area, "schedule": schedule, "indicator": indicator,
                    "target_value": target, "target_measure": measure,
                    "annual_budget_ugx": budget, "funding_source": source,
                },
            )

        loc = {}
        for key, name, campus, pickup in [
            ("kih", "Kihumuro Health Centre", "kihumuro", True),
            ("town", "Town campus, Dean of Students", "town", True),
            ("guild", "Guild office", "town", True),
            ("gate", "MUST main gate", "town", False),
        ]:
            loc[key], _ = Location.objects.update_or_create(
                name=name, defaults={"campus": campus, "is_pickup_point": pickup},
            )

        items = {}
        for key, name, category, unit, reorder in [
            ("condoms", "Condoms", "commodity", "piece", 200),
            ("kits", "HIV self-test kits", "commodity", "kit", 20),
            ("brochures", "IEC brochures", "iec", "copy", 50),
            ("tshirts", "Awareness T-shirts", "iec", "piece", 5),
        ]:
            items[key], _ = Item.objects.update_or_create(
                name=name, defaults={"category": category, "unit": unit, "reorder_level": reorder},
            )

        stock = {
            "kih": {"condoms": 1400, "kits": 6, "brochures": 80, "tshirts": 12},
            "town": {"condoms": 900, "kits": 25, "brochures": 14, "tshirts": 20},
            "guild": {"condoms": 300, "kits": 10, "brochures": 60, "tshirts": 18},
        }
        for loc_key, quantities in stock.items():
            for item_key, quantity in quantities.items():
                StockLevel.objects.get_or_create(
                    item=items[item_key], location=loc[loc_key], defaults={"quantity": quantity},
                )

        tags = {}
        for slug, name in TAGS:
            tags[slug], _ = ServiceTag.objects.update_or_create(slug=slug, defaults={"name": name})
        for name, place, campus, offers, tag_slugs, featured in SERVICES:
            service, _ = Service.objects.update_or_create(
                name=name,
                defaults={
                    "location_text": place, "campus": campus, "offers": offers,
                    "is_featured": featured, "is_published": True, "verified_on": today,
                },
            )
            service.tags.set([tags[s] for s in tag_slugs])

        def event(title, days, activity, location, status, description=""):
            obj, _ = Event.objects.update_or_create(
                title=title,
                defaults={
                    "event_date": today + timedelta(days=days), "activity": act[activity],
                    "location": loc[location], "status": status, "description": description,
                },
            )
            return obj

        prep = event("Peer talk: PrEP basics", -8, "peer", "town", "held")
        set_attendance(prep, [(14, 9), (11, 8), (7, 6), (5, 4)])
        training = event("Counselling skills training, day 2", -19, "training", "kih", "held")
        set_attendance(training, [(3, 2), (4, 3), (2, 2), (1, 1)])
        testing = event("Testing day with AIC", -30, "vct", "kih", "held")
        set_attendance(testing, [(31, 22), (24, 19), (18, 15), (12, 9)])
        meeting = event("M&E review meeting", -12, "me", "town", "held")
        set_attendance(meeting, [(0, 0), (0, 0), (0, 0), (3, 4)])

        wad = date(today.year, 12, 1)
        event("World AIDS Day march", (wad - today).days if wad > today else 14, "support", "gate",
              "planned", "Free condoms, oral self-test kits and information along the route.")
        event("Peer talk: living positively", 20, "peer", "kih", "planned",
              "An open talk with peer educators. Come as you are.")

        for ref, key, amount, days, ev in [
            ("DEMO-001", "peer", 650_000, -8, prep),
            ("DEMO-002", "training", 2_100_000, -19, training),
            ("DEMO-003", "vct", 250_000, -30, testing),
            ("DEMO-004", "iec", 1_200_000, -25, None),
            ("DEMO-005", "me", 1_000_000, -12, meeting),
        ]:
            Expenditure.objects.update_or_create(
                receipt_ref=ref,
                defaults={"activity": act[key], "amount_ugx": amount,
                          "spent_on": today + timedelta(days=days), "event": ev},
            )

        if not Feedback.objects.exists():
            Feedback.objects.bulk_create([
                Feedback(category="question", message="Can I get PrEP on campus or only at MRRH?", rating=3),
                Feedback(category="idea", message="A talk about telling a partner your status.", rating=4),
                Feedback(category="service", message="The self-test kits ran out at the Health Centre.", rating=2),
            ])

        # "Peer educators" group: may plan events and record attendance in the admin,
        # and look at (not change) stock movements and the audit log. No superuser powers.
        group, _ = Group.objects.get_or_create(name="Peer educators")
        tracker_perms = Permission.objects.filter(
            content_type__app_label="tracker",
            codename__in=[
                "add_event", "change_event", "view_event",
                "add_eventattendance", "change_eventattendance", "view_eventattendance",
                "view_location", "view_policyactivity",
                "view_stockmovement", "view_auditlog", "view_stocklevel", "view_item",
            ],
        )
        # Peer educators may read (not change or delete) the students' anonymous messages.
        feedback_perm = Permission.objects.filter(content_type__app_label="portal", codename="view_feedback")
        group.permissions.set(tracker_perms | feedback_perm)

        # Demo peer educator (staff, but not a superuser). Change the password before showing anyone.
        User = get_user_model()
        peer, created = User.objects.get_or_create(
            username="peer1",
            defaults={"first_name": "Demo", "last_name": "Peer Educator", "is_staff": True},
        )
        if created:
            peer.set_password("peer-demo-2026")
            peer.save()
        peer.groups.add(group)
        PeerEducator.objects.get_or_create(
            user=peer, defaults={"faculty": "Computing and Informatics", "cohort_year": 2025},
        )

        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded. Peer educator login: peer1 / peer-demo-2026"
        ))
