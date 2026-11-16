-- MUST HealthConnect: create the database and its two roles.
-- Run as the postgres superuser (setup_db.ps1 does this for you on Windows):
--   psql -U postgres -h localhost -f docs/setup.sql
-- Safe to run more than once: anything that already exists is skipped.
-- The passwords below match .env.example. If you change them here, change them in .env too.

\set ON_ERROR_STOP on

-- hc_app owns the tables. CREATEDB lets Django build a throwaway test database.
SELECT 'CREATE ROLE hc_app LOGIN PASSWORD ''hcapp_local_2026'' CREATEDB'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hc_app') \gexec

-- hc_report is read-only: it gets SELECT on the reporting views and nothing else.
SELECT 'CREATE ROLE hc_report LOGIN PASSWORD ''hcreport_local_2026'''
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hc_report') \gexec

SELECT 'CREATE DATABASE healthconnect OWNER hc_app ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'healthconnect') \gexec

REVOKE CONNECT ON DATABASE healthconnect FROM PUBLIC;
GRANT CONNECT ON DATABASE healthconnect TO hc_app, hc_report;

\c healthconnect
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO hc_report;
-- GRANT SELECT on the views happens in migration tracker/0002_reporting_views.py

\echo
\echo 'Database healthconnect and roles hc_app, hc_report are ready.'
