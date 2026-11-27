-- Thalam's two application roles (SPEC-002-R3): Kaval's split, one layer down (CLAUDE.md rule 3).
-- covers: SPEC-002-R3
--
-- thalam_reader  SELECT only. `make ask` uses it, and Phase 2's agent inherits it.
-- thalam_loader  writes the mirror tables, and may only INSERT into the written-once ones, so the
--                code that loads history cannot change it (thalam_shared/models.py: two kinds).
--
-- Plain SQL, run as the owner by scripts/ops/db_roles.py after every `make migrate` (a GRANT on
-- ALL TABLES reaches only the tables that exist). The passwords arrive as transaction settings the
-- runner sets with bound parameters, and nothing here prints them. Kaval learned both halves:
-- psql's :'var' does not reach inside DO $$ (KAV-56), and a bare SELECT of a password prints it
-- (KAV-125). Safe to repeat: passwords and grants are set again.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_loader') THEN
    EXECUTE format('CREATE ROLE thalam_loader LOGIN PASSWORD %L',
                   current_setting('thalam.loader_password'));
  ELSE
    EXECUTE format('ALTER ROLE thalam_loader LOGIN PASSWORD %L',
                   current_setting('thalam.loader_password'));
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_reader') THEN
    EXECUTE format('CREATE ROLE thalam_reader LOGIN PASSWORD %L',
                   current_setting('thalam.reader_password'));
  ELSE
    EXECUTE format('ALTER ROLE thalam_reader LOGIN PASSWORD %L',
                   current_setting('thalam.reader_password'));
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO thalam_loader, thalam_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM thalam_loader, thalam_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO thalam_reader;

-- Mirrors: made to match the files. A component is retired, never deleted, so no DELETE on it.
GRANT SELECT, INSERT, UPDATE ON component TO thalam_loader;
GRANT SELECT, INSERT, DELETE ON dependency TO thalam_loader;
GRANT SELECT, INSERT, UPDATE, DELETE ON release_item, calendar_window TO thalam_loader;
-- Written once: INSERT, never UPDATE or DELETE.
GRANT SELECT, INSERT ON release, release_need, release_event TO thalam_loader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO thalam_loader;
