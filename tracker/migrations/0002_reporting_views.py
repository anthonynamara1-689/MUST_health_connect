"""Database objects Django cannot describe as models: views, a trigger and a procedure.

Connectivity feature 7 (calling database objects) and feature 2 (GRANT for the read-only role).
"""
from django.db import migrations

VIEWS = """
CREATE OR REPLACE VIEW v_policy_lines AS
SELECT id AS activity_id, name, indicator, target_value, target_measure, annual_budget_ugx
FROM policy_activity;

CREATE OR REPLACE VIEW v_quarterly_progress AS
WITH att AS (
    SELECT e.activity_id,
           date_trunc('quarter', e.event_date)::date AS quarter_start,
           SUM(ea.headcount) AS reached,
           COUNT(DISTINCT e.id) AS events_held
    FROM event e
    JOIN event_attendance ea ON ea.event_id = e.id
    GROUP BY 1, 2
), spend AS (
    SELECT activity_id,
           date_trunc('quarter', spent_on)::date AS quarter_start,
           SUM(amount_ugx) AS spent
    FROM expenditure
    GROUP BY 1, 2
), quarters AS (
    SELECT activity_id, quarter_start FROM att
    UNION
    SELECT activity_id, quarter_start FROM spend
)
SELECT q.activity_id,
       q.quarter_start,
       COALESCE(att.reached, 0)     AS reached,
       COALESCE(att.events_held, 0) AS events_held,
       COALESCE(spend.spent, 0)     AS spent
FROM quarters q
LEFT JOIN att   ON att.activity_id = q.activity_id   AND att.quarter_start = q.quarter_start
LEFT JOIN spend ON spend.activity_id = q.activity_id AND spend.quarter_start = q.quarter_start;

CREATE OR REPLACE VIEW v_low_stock AS
SELECT i.name AS item, l.name AS location, s.quantity, i.reorder_level
FROM stock_level s
JOIN item i     ON i.id = s.item_id
JOIN location l ON l.id = s.location_id
WHERE s.quantity < i.reorder_level;

CREATE OR REPLACE VIEW v_feedback_summary AS
SELECT date_trunc('month', created_on)::date AS month,
       category,
       COUNT(*) AS messages,
       ROUND(AVG(rating), 1) AS avg_rating
FROM feedback
GROUP BY 1, 2;

DO $grant$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hc_report') THEN
        GRANT SELECT ON v_policy_lines, v_quarterly_progress, v_low_stock, v_feedback_summary TO hc_report;
    END IF;
END
$grant$;
"""

DROP_VIEWS = """
DROP VIEW IF EXISTS v_feedback_summary, v_low_stock, v_quarterly_progress, v_policy_lines;
"""

AUDIT_TRIGGER = """
CREATE OR REPLACE FUNCTION audit_stock_level() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, row_id, action, old_data, new_data)
        VALUES (TG_TABLE_NAME, OLD.id, TG_OP, to_jsonb(OLD), NULL);
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, row_id, action, old_data, new_data)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, to_jsonb(OLD), to_jsonb(NEW));
    ELSE
        INSERT INTO audit_log (table_name, row_id, action, old_data, new_data)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, NULL, to_jsonb(NEW));
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_stock_level
AFTER INSERT OR UPDATE OR DELETE ON stock_level
FOR EACH ROW EXECUTE FUNCTION audit_stock_level();
"""

DROP_AUDIT_TRIGGER = """
DROP TRIGGER IF EXISTS trg_audit_stock_level ON stock_level;
DROP FUNCTION IF EXISTS audit_stock_level();
"""

ISSUE_PROCEDURE = """
CREATE OR REPLACE PROCEDURE issue_stock(
    p_item bigint, p_location bigint, p_qty integer, p_event bigint, p_user integer
)
LANGUAGE plpgsql AS $$
DECLARE
    v_qty integer;
BEGIN
    IF p_qty <= 0 THEN
        RAISE EXCEPTION 'Quantity must be 1 or more';
    END IF;

    SELECT quantity INTO v_qty
    FROM stock_level
    WHERE item_id = p_item AND location_id = p_location
    FOR UPDATE;

    IF v_qty IS NULL THEN
        RAISE EXCEPTION 'This item is not stocked at that location';
    ELSIF v_qty < p_qty THEN
        RAISE EXCEPTION 'Only % left', v_qty;
    END IF;

    UPDATE stock_level SET quantity = quantity - p_qty
    WHERE item_id = p_item AND location_id = p_location;

    INSERT INTO stock_movement (item_id, location_id, qty_change, reason, event_id, user_id)
    VALUES (p_item, p_location, -p_qty, 'issued', p_event, p_user);
END;
$$;
"""

DROP_ISSUE_PROCEDURE = """
DROP PROCEDURE IF EXISTS issue_stock(bigint, bigint, integer, bigint, integer);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0001_initial"),
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(VIEWS, DROP_VIEWS),
        migrations.RunSQL(AUDIT_TRIGGER, DROP_AUDIT_TRIGGER),
        migrations.RunSQL(ISSUE_PROCEDURE, DROP_ISSUE_PROCEDURE),
    ]
