"""Give the read-only reports user exactly what it needs.  python manage.py grant_report_access"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from psycopg import sql

VIEWS = ["v_policy_lines", "v_quarterly_progress", "v_low_stock", "v_feedback_summary"]


class Command(BaseCommand):
    help = "GRANT CONNECT, schema USAGE and SELECT on the 4 reporting views to the reports user."

    def handle(self, *args, **options):
        role = settings.DATABASES["reports"]["USER"]
        if role == settings.DATABASES["default"]["USER"]:
            self.stdout.write("Both connections use the same user, so there is nothing to grant.")
            return
        with connection.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cur.fetchone() is None:
                self.stdout.write(self.style.WARNING(f"User {role!r} does not exist yet. Create it, then redeploy."))
                return
            who = sql.Identifier(role)
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(connection.settings_dict["NAME"]), who))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(who))
            cur.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(v) for v in VIEWS), who))
        self.stdout.write(self.style.SUCCESS(f"{role} can now read the 4 reporting views (and nothing else)."))