-- Start completely fresh (DELETES ALL DATA). Run as postgres:
--   psql -U postgres -h localhost -f docs/reset.sql
-- then run docs/setup.sql again, migrate and seed_demo.
-- WITH (FORCE) closes any open connections first, e.g. a running runserver.
DROP DATABASE IF EXISTS healthconnect WITH (FORCE);
DROP DATABASE IF EXISTS test_healthconnect WITH (FORCE);
DROP ROLE IF EXISTS hc_report;
DROP ROLE IF EXISTS hc_app;
