"""Raw-SQL database work for the stock module (connectivity features 4-7)."""
import time

from django.conf import settings
from django.db import connection, transaction

# Connectivity feature 4: %s marks a parameter. psycopg sends the values separately
# from the SQL text, so user input can never change the shape of the query.
LOCK_SQL = (
    "SELECT quantity FROM stock_level "
    "WHERE item_id = %s AND location_id = %s FOR UPDATE"
)
UPDATE_SQL = (
    "UPDATE stock_level SET quantity = quantity - %s "
    "WHERE item_id = %s AND location_id = %s"
)
INSERT_SQL = (
    "INSERT INTO stock_movement (item_id, location_id, qty_change, reason, event_id, user_id) "
    "VALUES (%s, %s, %s, 'issued', %s, %s)"
)


class StockError(Exception):
    """A business-rule failure. The transaction has been rolled back."""

    def __init__(self, message, log=None):
        super().__init__(message)
        self.log = log or []


def _line(text, kind="plain"):
    return {"text": text, "kind": kind}


def issue_stock(*, item_id, location_id, qty, event_id, user_id, simulate_crash=False):
    """Take stock off the shelf in ONE transaction. Returns (remaining, log).

    Connectivity feature 5: transaction.atomic() -> COMMIT on success, ROLLBACK on any error.
    Connectivity feature 6: SELECT ... FOR UPDATE locks the row, so two people
    issuing the last kits at the same time cannot both succeed.
    simulate_crash=True (the switch on the stock page) fails on purpose after the UPDATE.
    """
    log = [_line("BEGIN;")]
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                # 1. Lock this one row. A second request for the same row waits here.
                cur.execute(LOCK_SQL, [item_id, location_id])
                row = cur.fetchone()
                log.append(_line(LOCK_SQL + ";"))
                if row is None:
                    raise StockError("That item is not stocked at this pick-up point.")
                current = row[0]
                log.append(_line(f"  -> quantity = {current}  (row locked until COMMIT or ROLLBACK)"))

                if settings.HC_LOCK_DEMO_SECONDS:  # demo only: hold the lock longer
                    time.sleep(settings.HC_LOCK_DEMO_SECONDS)

                if qty > current:
                    raise StockError(f"Only {current} left at this pick-up point. Nothing was issued.")

                # 2. Take the stock.
                cur.execute(UPDATE_SQL, [qty, item_id, location_id])
                log.append(_line(UPDATE_SQL + ";"))

                if simulate_crash or settings.HC_FAIL_AFTER_UPDATE:  # demo only: crash half-way
                    raise StockError("Simulated crash after the UPDATE. PostgreSQL undid it.")

                # 3. Record why it moved.
                cur.execute(INSERT_SQL, [item_id, location_id, -qty, event_id, user_id])
                log.append(_line(INSERT_SQL + ";"))
    except StockError as exc:
        log.append(_line(f"ROLLBACK;  -- {exc}", "err"))
        exc.log = log
        raise

    remaining = current - qty
    log.append(_line(f"COMMIT;  -- {remaining} left", "ok"))
    return remaining, log


def issue_stock_with_procedure(*, item_id, location_id, qty, event_id=None, user_id=None):
    """Connectivity feature 7: the same job done by the PL/pgSQL procedure in migration 0002."""
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "CALL issue_stock(%s::bigint, %s::bigint, %s::integer, %s::bigint, %s::integer)",
            [item_id, location_id, qty, event_id, user_id],
        )
