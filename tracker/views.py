import time
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, OperationalError, connections, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import EventForm, IssueStockForm
from .models import Event, EventAttendance, Item, Location, StockLevel, StockMovement
from .services import StockError, issue_stock

# ---------- helpers ----------

FY_QUARTER = {7: 1, 10: 2, 1: 3, 4: 4}  # Uganda's financial year starts in July
QUARTER_END = {1: "Mar", 4: "Jun", 7: "Sep", 10: "Dec"}


def quarter_start(day):
    return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)


def fy_text(start):
    fy = start.year if start.month >= 7 else start.year - 1
    return f"{fy}/{str(fy + 1)[-2:]}"


def db_status(alias="default"):
    """Run SELECT 1 and time it. Used by the report badge and /health/db/."""
    start = time.perf_counter()
    try:
        with connections[alias].cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except OperationalError as exc:
        first_line = str(exc).splitlines()[0] if str(exc) else "unreachable"
        return {"ok": False, "error": first_line}
    return {"ok": True, "ms": round((time.perf_counter() - start) * 1000, 1)}


# ---------- quarterly report (read-only connection) ----------

REPORT_SQL = """
    SELECT l.name, l.indicator, l.target_value, l.target_measure, l.annual_budget_ugx,
           COALESCE(v.reached, 0), COALESCE(v.events_held, 0), COALESCE(v.spent, 0)
    FROM v_policy_lines AS l
    LEFT JOIN v_quarterly_progress AS v
           ON v.activity_id = l.activity_id AND v.quarter_start = %s
    ORDER BY l.activity_id
"""
QUARTERS_SQL = "SELECT DISTINCT quarter_start FROM v_quarterly_progress"
LOW_STOCK_SQL = "SELECT item, location, quantity, reorder_level FROM v_low_stock ORDER BY quantity"


@login_required
def report(request):
    this_quarter = quarter_start(timezone.localdate())
    try:
        selected = quarter_start(date.fromisoformat(request.GET["q"]))
    except (KeyError, ValueError):
        selected = this_quarter

    # Connectivity features 2 and 7: connections["reports"] logs in as hc_report,
    # which can only SELECT from the views created in migration 0002.
    started = time.perf_counter()
    with connections["reports"].cursor() as cur:
        cur.execute(REPORT_SQL, [selected])
        rows = cur.fetchall()
        cur.execute(QUARTERS_SQL)
        quarters = {r[0] for r in cur.fetchall()}
        cur.execute(LOW_STOCK_SQL)
        low_stock = cur.fetchall()
    query_ms = round((time.perf_counter() - started) * 1000, 1)

    lines = []
    for name, indicator, target, measure, budget, reached, held, spent in rows:
        achieved = {"people": reached, "events": held}.get(measure)
        pct = round(achieved * 100 / target) if target and achieved is not None else None
        behind = pct is not None and pct < 40
        lines.append({
            "name": name,
            "indicator": indicator,
            "target": target,
            "measure": measure,
            "reached": achieved if achieved is not None else reached,
            "budget": budget,
            "spent": spent,
            "spent_pct": min(round(spent * 100 / budget), 100) if budget else 0,
            "pct": min(pct, 100) if pct is not None else None,
            "behind": behind,
            # Used by the All / Behind / On track filter on the report page.
            "status": "untracked" if pct is None else ("behind" if behind else "on_track"),
        })

    # SUM() of a bigint column comes back from PostgreSQL as NUMERIC, so Python
    # gets a Decimal. int() keeps the arithmetic below simple.
    total_budget = int(sum(r[4] or 0 for r in rows))
    total_spent = int(sum(r[7] for r in rows))
    summary = {
        "reached": int(sum(r[5] for r in rows)),
        "events_held": int(sum(r[6] for r in rows)),
        "events_planned": Event.objects.filter(
            status=Event.Status.PLANNED, event_date__gte=timezone.localdate()
        ).count(),
        "spent": total_spent,
        "budget": total_budget,
        "spent_m": f"{total_spent / 1e6:.1f}M",
        "budget_m": f"{total_budget / 1e6:.1f}M",
        "low_stock": low_stock,
        "spent_pct": min(round(total_spent * 100 / total_budget), 100) if total_budget else 0,
        "behind": sum(1 for line in lines if line["status"] == "behind"),
        "on_track": sum(1 for line in lines if line["status"] == "on_track"),
        "untracked": sum(1 for line in lines if line["status"] == "untracked"),
    }

    options = sorted(quarters | {this_quarter, selected}, reverse=True)
    return render(request, "tracker/report.html", {
        "quarter_label": f"Quarter {FY_QUARTER[selected.month]}, {fy_text(selected)}",
        "quarter_range": f"{selected:%b} to {QUARTER_END[selected.month]} {selected.year}",
        "quarter_options": [
            {"value": q.isoformat(),
             "label": f"Q{FY_QUARTER[q.month]} {fy_text(q)} ({q:%b}–{QUARTER_END[q.month]} {q.year})"}
            for q in options
        ],
        "selected_quarter": selected.isoformat(),
        "db": db_status("reports"),
        "query_ms": query_ms,
        "summary": summary,
        "lines": lines,
    })


# ---------- events and attendance (ORM in a transaction) ----------

YEARS = [1, 2, 3, 4]


@login_required
def events(request):
    plan_form = EventForm(initial={"event_date": timezone.localdate(), "is_public": True})
    if request.method == "POST" and request.POST.get("action") == "plan":
        plan_form = EventForm(request.POST)
        if plan_form.is_valid():
            new_event = plan_form.save(commit=False)
            new_event.organiser = request.user
            new_event.save()  # one INSERT INTO event ... through the ORM
            messages.success(request, f"Planned “{new_event.title}” for {new_event.event_date.day} {new_event.event_date:%b %Y}.")
            return redirect(f"{reverse('tracker:events')}?event={new_event.pk}")
        # Invalid: fall through and show the page again with the dialog open and errors shown.

    event_list = list(
        Event.objects.select_related("location", "activity")
        .annotate(total=Sum("attendance__headcount"))
        .order_by("-event_date")
    )
    selected_id = request.POST.get("event") or request.GET.get("event")
    if selected_id and str(selected_id).isdigit():
        selected = get_object_or_404(Event, pk=selected_id)
    else:
        # Open the latest event that can take attendance, not a future planned one.
        selected = next((e for e in event_list if e.can_record_attendance), None)
        selected = selected or (event_list[0] if event_list else None)

    if request.method == "POST" and request.POST.get("action") != "plan" and selected:
        back = f"{reverse('tracker:events')}?event={selected.pk}"
        if not selected.can_record_attendance:
            messages.error(request, "Attendance opens on the day of the event.")
            return redirect(back)

        counts = {}
        for year in YEARS:
            for gender in ("F", "M"):
                raw = (request.POST.get(f"{gender.lower()}_{year}", "0") or "0").strip()
                if not raw.isdigit():
                    messages.error(request, "Headcounts must be whole numbers, 0 or more.")
                    return redirect(back)
                counts[(gender, year)] = int(raw)

        # Connectivity feature 5: all 8 rows are saved, or none are.
        with transaction.atomic():
            for (gender, year), value in counts.items():
                EventAttendance.objects.update_or_create(
                    event=selected, gender=gender, year_of_study=year,
                    defaults={"headcount": value},
                )
            if selected.status == Event.Status.PLANNED:
                selected.status = Event.Status.HELD
                selected.save(update_fields=["status"])

        messages.success(
            request,
            f"Saved {sum(counts.values())} attendees as 8 headcount rows in one transaction. No names stored.",
        )
        return redirect(back)

    existing = {}
    if selected:
        existing = {(a.gender, a.year_of_study): a.headcount for a in selected.attendance.all()}
    grid = [
        {"year": y, "label": "Year 4+" if y == 4 else f"Year {y}",
         "f": existing.get(("F", y), 0), "m": existing.get(("M", y), 0)}
        for y in YEARS
    ]
    for ev in event_list:
        ev.filter_key = "planned" if ev.status == Event.Status.PLANNED and not ev.total else (
            "cancelled" if ev.status == Event.Status.CANCELLED else "held")
    return render(request, "tracker/events.html", {
        "events": event_list,
        "selected": selected,
        "grid": grid,
        "grid_initial": {f"{g}_{row['year']}": row[g] for row in grid for g in ("f", "m")},
        "total": sum(existing.values()),
        "stats": {
            "held": sum(1 for e in event_list if e.filter_key == "held"),
            "planned": sum(1 for e in event_list if e.filter_key == "planned"),
            "attendees": sum(e.total or 0 for e in event_list),
        },
        "plan_form": plan_form,
        "plan_open": plan_form.is_bound and not plan_form.is_valid(),
    })


# ---------- issue stock (raw SQL transaction from services.py) ----------

@login_required
def stock(request):
    locations = list(Location.objects.filter(is_pickup_point=True))
    location_id = request.GET.get("location") or (locations[0].pk if locations else None)

    if request.method == "POST":
        form = IssueStockForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                remaining, log = issue_stock(
                    item_id=data["item"],
                    location_id=data["location"],
                    qty=data["quantity"],
                    event_id=data["event"],
                    user_id=request.user.pk,
                    simulate_crash=data["simulate_crash"],
                )
                messages.success(request, f"Issued {data['quantity']}. {remaining} left at this pick-up point.")
            except StockError as exc:
                log = exc.log
                messages.error(request, str(exc))
            except OperationalError:
                # Connectivity feature 8: the database went away mid-request.
                log = [
                    {"text": "connect() -> OperationalError: database unreachable", "kind": "err"},
                    {"text": "-- caught in the view; nothing was changed", "kind": "plain"},
                ]
                messages.error(request, "The database can't be reached right now. Nothing was changed. Try again in a minute.")
            except DatabaseError as exc:  # e.g. IntegrityError from a CHECK or foreign key
                first = str(exc).splitlines()[0] if str(exc) else ""
                log = [{"text": f"ROLLBACK;  -- {exc.__class__.__name__}: {first}", "kind": "err"}]
                messages.error(request, "The database refused that change, so nothing was saved.")
            request.session["stock_log"] = log
            return redirect(f"{reverse('tracker:stock')}?location={data['location']}&item={data['item']}")
        messages.error(request, "Check the form: every field except the event is required, and quantity must be 1 or more.")
    else:
        form = IssueStockForm(initial={"location": location_id, "item": request.GET.get("item"), "quantity": 1})

    selected_location = next((l for l in locations if str(l.pk) == str(location_id)), None)
    stock_rows = list(
        StockLevel.objects.filter(location_id=selected_location.pk).select_related("item").order_by("item__name")
        if selected_location else []
    )
    for row in stock_rows:
        # Bar length: full at 5x the reorder level, so the reorder mark sits at 20%.
        scale = row.item.reorder_level * 5 or max(row.quantity, 1)
        row.level_pct = min(round(row.quantity * 100 / scale), 100)
    items = list(Item.objects.all())
    selected_item = form["item"].value() or (items[0].pk if items else None)
    movements = (
        StockMovement.objects.filter(location=selected_location)
        .select_related("item", "event", "user")[:6]
        if selected_location else []
    )
    log = request.session.pop("stock_log", [])
    return render(request, "tracker/stock.html", {
        "form": form,
        "items": items,
        "selected_item": str(selected_item or ""),
        "locations": locations,
        "events": Event.objects.exclude(status=Event.Status.CANCELLED).order_by("-event_date")[:20],
        "selected_location": selected_location,
        "stock_rows": stock_rows,
        # {item_id: quantity here}, read by Alpine to warn before an over-issue.
        "stock_map": {str(r.item_id): r.quantity for r in stock_rows},
        "movements": movements,
        "log": log,
        "log_status": log[-1]["kind"] if log else "",
    })


# ---------- health check (connectivity feature 10) ----------

def health_db(request):
    """JSON status of both connections. 200 if both answer, 503 if not."""
    result = {alias: db_status(alias) for alias in ("default", "reports")}
    healthy = all(r["ok"] for r in result.values())
    return JsonResponse(result, status=200 if healthy else 503)
