-- Thalam's two application roles (SPEC-002-R3): Kaval's split, one layer down (CLAUDE.md rule 3).
-- covers: SPEC-002-R3
--
-- thalam_reader  SELECT only, and read-only at login. `make ask` uses it, and Phase 2's agent
--                inherits it, so it gets no side doors: no temp tables, no writes of any kind.
-- thalam_loader  writes the mirror tables, and may only INSERT into the written-once ones, so the
--                code that loads history cannot change it (thalam_shared/models.py: two kinds).
--
-- Plain SQL, run as the owner by scripts/ops/db_roles.py after every `make migrate` (a GRANT on
-- ALL TABLES reaches only the tables that exist). Safe to repeat: passwords and grants are set
-- again, and an advisory lock queues two concurrent runs instead of letting them collide.
--
-- No password reaches the server or its log. The runner computes each role's SCRAM-SHA-256
-- verifier on the client and hands it over as a transaction setting (a bound parameter); only the
-- verifier is ever in a statement. A failing EXECUTE would put its statement text in the error
-- CONTEXT, so each one is wrapped and re-raised with the statement text left out. Kaval learned
-- the other halves: psql's :'var' does not reach inside DO $$ (KAV-56), and a bare SELECT of a
-- password prints it (KAV-125).

SELECT pg_advisory_xact_lock(hashtext('thalam.db_roles'));

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_loader') THEN
    BEGIN
      EXECUTE format('CREATE ROLE thalam_loader LOGIN PASSWORD %L',
                     current_setting('thalam.loader_verifier'));
    EXCEPTION WHEN query_canceled OR OTHERS THEN
      RAISE EXCEPTION USING ERRCODE = SQLSTATE, MESSAGE = 'thalam_loader: ' || SQLERRM;
    END;
  ELSE
    BEGIN
      EXECUTE format('ALTER ROLE thalam_loader LOGIN PASSWORD %L',
                     current_setting('thalam.loader_verifier'));
    EXCEPTION WHEN query_canceled OR OTHERS THEN
      RAISE EXCEPTION USING ERRCODE = SQLSTATE, MESSAGE = 'thalam_loader: ' || SQLERRM;
    END;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_reader') THEN
    BEGIN
      EXECUTE format('CREATE ROLE thalam_reader LOGIN PASSWORD %L',
                     current_setting('thalam.reader_verifier'));
    EXCEPTION WHEN query_canceled OR OTHERS THEN
      RAISE EXCEPTION USING ERRCODE = SQLSTATE, MESSAGE = 'thalam_reader: ' || SQLERRM;
    END;
  ELSE
    BEGIN
      EXECUTE format('ALTER ROLE thalam_reader LOGIN PASSWORD %L',
                     current_setting('thalam.reader_verifier'));
    EXCEPTION WHEN query_canceled OR OTHERS THEN
      RAISE EXCEPTION USING ERRCODE = SQLSTATE, MESSAGE = 'thalam_reader: ' || SQLERRM;
    END;
  END IF;

  -- The ALTER branch never resets these, and on a managed server it could not: refuse instead.
  IF EXISTS (SELECT FROM pg_roles
             WHERE rolname IN ('thalam_loader', 'thalam_reader')
               AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls OR rolreplication))
     OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
                WHERE r.rolname IN ('thalam_loader', 'thalam_reader')) THEN
    RAISE EXCEPTION 'thalam_loader or thalam_reader holds a privilege or membership it must not';
  END IF;
END $$;

ALTER ROLE thalam_reader SET default_transaction_read_only = on;

-- PUBLIC may connect and make temp tables by default; keep both to the two roles (and the owner).
DO $$
BEGIN
  EXECUTE format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO thalam_loader, thalam_reader',
                 current_database());
END $$;

GRANT USAGE ON SCHEMA public TO thalam_loader, thalam_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM thalam_loader, thalam_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM thalam_loader, thalam_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO thalam_reader;

-- Mirrors: made to match the files. A component is retired, never deleted, and never renamed (its
-- name is its identity: renaming two would move a release to another component), so no DELETE and
-- no UPDATE of name.
GRANT SELECT, INSERT ON component TO thalam_loader;
GRANT UPDATE (owner, type, lifecycle, description, retired_at) ON component TO thalam_loader;
GRANT SELECT, INSERT, DELETE ON dependency TO thalam_loader;
GRANT SELECT, INSERT, UPDATE, DELETE ON release_item, calendar_window TO thalam_loader;
-- Written once: INSERT, never UPDATE or DELETE.
GRANT SELECT, INSERT ON release, release_need, release_event TO thalam_loader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO thalam_loader;
