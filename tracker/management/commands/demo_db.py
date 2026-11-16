"""Show several connectivity features in the terminal, one after another.

    python manage.py demo_db

Nothing here changes data: every write it tries is refused or rolled back.
"""
from django.core.management.base import BaseCommand
from django.db import DatabaseError, connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from portal.models import Service
from tracker.models import StockLevel


class Command(BaseCommand):
    help = "Demonstrate privileges, SQL injection safety, N+1 queries and the stored procedure."

    def heading(self, text):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(text))

    def handle(self, *args, **options):
        # 1. Who is each connection logged in as?
        self.heading("1. Two connections, two PostgreSQL roles")
        for alias in ("default", "reports"):
            with connections[alias].cursor() as cur:
                cur.execute("SELECT current_user, current_database()")
                user, db = cur.fetchone()
            self.stdout.write(f"   {alias:8} -> logged in as {user} on {db}")

        # 2. The read-only role is refused anything but the views.
        self.heading("2. The reports role can read views, nothing else")
        with connections["reports"].cursor() as cur:
            cur.execute("SELECT count(*) FROM v_policy_lines")
            self.stdout.write(f"   SELECT FROM v_policy_lines   -> OK, {cur.fetchone()[0]} rows")
        for sql in ("SELECT * FROM feedback", "DELETE FROM feedback"):
            try:
                with transaction.atomic(using="reports"), connections["reports"].cursor() as cur:
                    cur.execute(sql)
                self.stdout.write(self.style.ERROR(f"   {sql:28} -> allowed (check docs/setup.sql grants)"))
            except DatabaseError as exc:
                self.stdout.write(f"   {sql:28} -> refused: {str(exc).splitlines()[0]}")

        # 3. SQL injection: string formatting vs parameters.
        self.heading("3. SQL injection: f-string vs parameter")
        evil = "x' OR '1'='1"
        with connection.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM service WHERE name = '{evil}'")  # never do this
            unsafe = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM service WHERE name = %s", [evil])
            safe = cur.fetchone()[0]
        self.stdout.write(f"   input: {evil}")
        self.stdout.write(self.style.ERROR(f"   f-string query matched {unsafe} rows (the attacker got every row)"))
        self.stdout.write(self.style.SUCCESS(f"   parameterised query matched {safe} rows (input treated as plain text)"))

        # 4. N+1 queries: ORM without and with prefetch_related.
        self.heading("4. ORM: the N+1 problem")
        with CaptureQueriesContext(connection) as plain:
            for service in Service.objects.all():
                list(service.tags.all())
        with CaptureQueriesContext(connection) as prefetched:
            for service in Service.objects.prefetch_related("tags"):
                list(service.tags.all())
        self.stdout.write(f"   Service.objects.all() + tags            -> {len(plain)} queries")
        self.stdout.write(f"   Service.objects.prefetch_related('tags') -> {len(prefetched)} queries")

        # 5. Stored procedure: the rule is enforced inside PostgreSQL.
        self.heading("5. Stored procedure issue_stock() refuses an over-issue")
        row = StockLevel.objects.select_related("item", "location").order_by("quantity").first()
        if row is None:
            self.stdout.write("   No stock rows yet. Run: python manage.py seed_demo")
            return
        try:
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute(
                    "CALL issue_stock(%s::bigint, %s::bigint, %s::integer, NULL, NULL)",
                    [row.item_id, row.location_id, row.quantity + 1],
                )
        except DatabaseError as exc:
            self.stdout.write(
                f"   CALL issue_stock({row.item.name} at {row.location.name}, qty {row.quantity + 1})"
            )
            self.stdout.write(f"   -> PostgreSQL said: {str(exc).splitlines()[0]}")
        row.refresh_from_db()
        self.stdout.write(f"   Stock is still {row.quantity}. Nothing changed.")
        self.stdout.write("")
