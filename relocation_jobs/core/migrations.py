"""Schema migrations applied at startup."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from relocation_jobs.core.db import _normalize_url, _utc_now, db_transaction

# First-boot seed for role_filter_tags only. Runtime source of truth is the table;
# admins edit tags in Admin → Config; scrapers load via default_keyword_lists().
_ROLE_FILTER_SEED_INCLUDES = [
    "backend", "back-end", "back end",
    "software engineer", "software developer",
    "platform engineer", "platform developer",
    "infrastructure engineer",
    "golang", "go engineer", "go developer", "go backend",
    "go ", "go,", "go/", "go-",
    "java ", "java,", "java/", "java-",
    "javascript", "javascript ", "javascript,", "javascript/", "javascript-",
    "typescript", "typescript ", "typescript,", "typescript/", "typescript-",
    "kotlin", "kotlin ", "kotlin,", "kotlin/", "kotlin-",
    "python engineer", "python developer", "python ai engineer",
    "python ", "python,", "python/", "python-",
    "spring boot",
    "microservice", "distributed",
    "fullstack", "full-stack", "full stack",
    "product engineer",
    "solutions engineer",
    "senior engineer",
]
_ROLE_FILTER_SEED_EXCLUDES = [
    "frontend", "front-end", "front end",
    "android", "ios", "mobile",
    "designer", " design ", "security", "security engineer",
    "marketing", "sales", "account manager", "account executive",
    "data scientist", "data analyst", "machine learning engineer",
    "product manager", "product owner",
    "recruiter", " hr ", "human resource", "talent acquisition",
    "accounting", "legal counsel", "legal trainee",
    "customer success", "customer support", "customer service",
    "office manager", "executive assistant",
    "content ", "copywriter", "seo",
    "game designer", "game artist", "level designer",
    "3d artist", "animator", "concept artist",
    "vp of", "head of", "director of", "chief ",
    "internship", "intern ",
    "lead ", " lead",
    "engineering manager",
    "principal ",
    "junior", "AI Operations", "AI Ops", "integration engineer",
    "Data analytics", "data analytics engineer",
    "devops", "dev ops", "unity", "value engineer",
    "site reliability", " sre", "associate",
    "cloud site reliability",
]

def _ensure_migrations_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def migration_applied(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = %s",
        (name,),
    ).fetchone()
    return row is not None


def mark_migration_applied(conn, name: str) -> None:
    conn.execute(
        """
        INSERT INTO schema_migrations (name, applied_at)
        VALUES (%s, %s)
        ON CONFLICT (name) DO NOTHING
        """,
        (name, _utc_now()),
    )


def run_migration_once(conn, name: str, fn: Callable) -> None:
    _ensure_migrations_table(conn)
    if migration_applied(conn, name):
        return
    fn(conn)
    mark_migration_applied(conn, name)


def _apply_job_tracking_columns(conn) -> None:
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS rejected INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS rejected_date TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS job_title TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS ats_score INTEGER"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS not_for_me_reason TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS waiting_referral INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS waiting_referral_date TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS referral_linkedin_url TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS seen INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS seen_date TEXT"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS looking_to_apply INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS looking_to_apply_date TEXT"
    )


def _apply_location_gate_override_column(conn) -> None:
    conn.execute(
        """
        ALTER TABLE job_tracking
        ADD COLUMN IF NOT EXISTS location_gate_override INTEGER NOT NULL DEFAULT 0
        """
    )


def _migrate_schema(conn) -> None:
    """Add columns introduced after initial deploy."""
    run_migration_once(conn, "job_tracking_columns_v1", _apply_job_tracking_columns)
    run_migration_once(conn, "job_status_events_table_v1", _ensure_status_events_table)
    run_migration_once(conn, "job_status_events_backfill_v1", _backfill_job_status_events)
    run_migration_once(conn, "company_tracking_columns_v1", _migrate_company_tracking_schema)
    run_migration_once(conn, "board_pin_columns_v1", _migrate_board_pin_columns)
    run_migration_once(conn, "clear_company_board_pins_v1", _clear_company_board_pins)
    run_migration_once(conn, "fetch_runs_table_v1", _ensure_fetch_runs_table)
    run_migration_once(conn, "fetch_runs_live_state_v1", _migrate_fetch_runs_live_state)
    run_migration_once(conn, "users_admin_column_v1", _ensure_users_admin_column)
    run_migration_once(conn, "users_google_auth_v1", _ensure_users_google_auth)
    run_migration_once(conn, "users_entitlements_v1", _ensure_users_entitlements)
    run_migration_once(conn, "users_last_login_at_v1", _ensure_users_last_login_at)
    run_migration_once(conn, "user_opportunities_v1", _ensure_user_opportunities_tables)
    run_migration_once(conn, "user_preferences_confirmed_v1", _ensure_preferences_confirmed)
    run_migration_once(conn, "user_opportunities_refreshed_at_v1", _ensure_opportunities_refreshed_at)
    run_migration_once(conn, "user_preferences_drop_country_prefs_v1", _drop_user_preferences_country_columns)
    run_migration_once(conn, "user_opportunities_reveal_v1", _ensure_opportunity_reveal_columns)
    run_migration_once(conn, "position_broadcast_assignments_v1", _ensure_position_broadcast_tables)
    run_migration_once(conn, "credit_wallet_v1", _ensure_credit_wallet_tables)
    run_migration_once(conn, "credit_order_kind_v1", _ensure_credit_order_kind)
    run_migration_once(conn, "mcp_tables_v1", _ensure_mcp_tables)
    run_migration_once(conn, "mcp_master_resumes_v2", _migrate_mcp_master_resumes_v2)
    run_migration_once(conn, "mcp_master_resumes_pdf_v1", _migrate_mcp_master_resumes_pdf_v1)
    run_migration_once(conn, "mcp_applications_country_lower_v1", _migrate_mcp_applications_country_lower)
    run_migration_once(conn, "mcp_cover_letter_v1", _migrate_mcp_cover_letter_v1)
    run_migration_once(conn, "mcp_project_masters_v1", _migrate_mcp_project_masters_v1)
    run_migration_once(conn, "mcp_project_masters_pdf_v1", _migrate_mcp_project_masters_pdf_v1)
    run_migration_once(conn, "mcp_interview_notes_v1", _migrate_mcp_interview_notes_v1)
    run_migration_once(conn, "mcp_oauth_remote_v1", _ensure_mcp_oauth_remote_tables)
    run_migration_once(conn, "location_gate_override_v1", _apply_location_gate_override_column)
    run_migration_once(conn, "public_job_saves_v1", _ensure_public_job_saves_table)
    run_migration_once(conn, "v2_company_fetch_attempts_v1", _company_fetch_attempts_v1)
    run_migration_once(conn, "team_docs_v1", _team_docs_v1)
    run_migration_once(conn, "team_docs_editors_v1", _team_docs_editors_v1)
    run_migration_once(conn, "team_docs_kuchup_ownership_v1", _seed_kuchup_ownership_doc)
    run_migration_once(conn, "team_docs_us_citizenship_v1", _seed_us_citizenship_doc)
    run_migration_once(conn, "role_filter_tags_v1", _role_filter_tags_v1)
    run_migration_once(conn, "team_docs_role_filter_v1", _seed_role_filter_docs)
    run_migration_once(conn, "user_role_tags_v1", _user_role_tags_v1)
    run_migration_once(conn, "role_filter_lang_variants_v1", _role_filter_lang_variants_v1)
    run_migration_once(conn, "user_role_tags_drop_user_idx_v1", _user_role_tags_drop_user_idx_v1)


_KUCHUP_OWNERSHIP_DOC = (
    Path(__file__).resolve().parent.parent
    / "team_docs"
    / "pages"
    / "kuchup-company-ownership.md"
)
_US_CITIZENSHIP_DOC = (
    Path(__file__).resolve().parent.parent
    / "team_docs"
    / "pages"
    / "job-eligibility-us-citizenship.md"
)


def _seed_team_doc(conn, *, folder: str, slug: str, title: str, path: Path) -> None:
    existing = conn.execute(
        "SELECT id FROM team_docs WHERE folder = %s AND slug = %s",
        (folder, slug),
    ).fetchone()
    if existing:
        return
    body = path.read_text(encoding="utf-8").strip() + "\n"
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO team_docs (
            folder, slug, title, body, created_at, updated_at,
            created_by_user_id, updated_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (folder, slug, title, body, now, now, None, None),
    )


def _seed_kuchup_ownership_doc(conn) -> None:
    _seed_team_doc(
        conn,
        folder="tech",
        slug="kuchup-company-ownership",
        title="Kuchup company ownership and edit permissions",
        path=_KUCHUP_OWNERSHIP_DOC,
    )


def _seed_us_citizenship_doc(conn) -> None:
    _seed_team_doc(
        conn,
        folder="tech",
        slug="job-eligibility-us-citizenship",
        title="Job eligibility tags: US Citizenship Required",
        path=_US_CITIZENSHIP_DOC,
    )


_ROLE_FILTER_DOC = (
    Path(__file__).resolve().parent.parent
    / "team_docs"
    / "pages"
    / "role-filter-tags.md"
)


def _role_filter_tags_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_filter_tags (
            id SERIAL PRIMARY KEY,
            keyword TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('include', 'exclude')),
            UNIQUE (kind, keyword)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_role_tag_prefs (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES role_filter_tags(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, tag_id)
        )
        """
    )
    conn.execute(
        """
        ALTER TABLE matching_jobs
        ADD COLUMN IF NOT EXISTS matches_default_filter INTEGER NOT NULL DEFAULT 1
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_default_open
        ON matching_jobs (company_id)
        WHERE matches_default_filter = 1
        """
    )
    for kind, words in (
        ("include", _ROLE_FILTER_SEED_INCLUDES),
        ("exclude", _ROLE_FILTER_SEED_EXCLUDES),
    ):
        for word in words:
            conn.execute(
                """
                INSERT INTO role_filter_tags (keyword, kind)
                VALUES (%s, %s)
                ON CONFLICT (kind, keyword) DO NOTHING
                """,
                (word, kind),
            )


def _seed_role_filter_docs(conn) -> None:
    _seed_team_doc(
        conn,
        folder="tech",
        slug="role-filter-tags",
        title="Role filter tags",
        path=_ROLE_FILTER_DOC,
    )


def _user_role_tags_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_role_tags (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('include', 'exclude')),
            UNIQUE (user_id, kind, keyword)
        )
        """
    )


def _role_filter_lang_variants_v1(conn) -> None:
    for word in _ROLE_FILTER_SEED_INCLUDES:
        conn.execute(
            """
            INSERT INTO role_filter_tags (keyword, kind)
            VALUES (%s, 'include')
            ON CONFLICT (kind, keyword) DO NOTHING
            """,
            (word,),
        )


def _user_role_tags_drop_user_idx_v1(conn) -> None:
    conn.execute("DROP INDEX IF EXISTS idx_user_role_tags_user")


def _team_docs_editors_v1(conn) -> None:
    conn.execute(
        "ALTER TABLE team_docs ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER"
    )
    conn.execute(
        "ALTER TABLE team_docs ADD COLUMN IF NOT EXISTS updated_by_user_id INTEGER"
    )


def _team_docs_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS team_docs (
            id SERIAL PRIMARY KEY,
            folder TEXT NOT NULL CHECK (
                folder IN ('product', 'business', 'marketing', 'tech')
            ),
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (folder, slug)
        )
        """
    )


def _company_fetch_attempts_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS company_fetch_attempts (
            id SERIAL PRIMARY KEY,
            fetch_run_id INTEGER,
            country TEXT NOT NULL,
            company_name TEXT NOT NULL,
            careers_url TEXT,
            ats_type TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            jobs_total INTEGER,
            jobs_new INTEGER,
            jobs_preserved INTEGER,
            message TEXT,
            duration_seconds DOUBLE PRECISION
        )
        """
    )


def _ensure_public_job_saves_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public_job_saves (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id INTEGER NOT NULL,
            slug TEXT NOT NULL DEFAULT '',
            saved_on TEXT NOT NULL,
            PRIMARY KEY (user_id, job_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_public_job_saves_user_day
        ON public_job_saves (user_id, saved_on)
        """
    )


def _migrate_fetch_runs_live_state(conn) -> None:
    conn.execute(
        """
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'done';
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS ats_type TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS file_name TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS cancel_requested INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS progress_json TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS activity_json TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS activity_log_json TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS log_json TEXT;
        ALTER TABLE fetch_runs ADD COLUMN IF NOT EXISTS review_jobs_json TEXT;
        """
    )
    conn.execute(
        """
        UPDATE fetch_runs
        SET status = 'done'
        WHERE status IS NULL OR TRIM(status) = ''
        """
    )


def _ensure_users_admin_column(conn) -> None:
    conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER NOT NULL DEFAULT 0"
    )
    admin_name = os.environ.get("PANEL_ADMIN_USER", "admin").strip().lower() or "admin"
    conn.execute(
        "UPDATE users SET is_admin = 1 WHERE LOWER(username) = LOWER(%s)",
        (admin_name,),
    )


def _ensure_users_google_auth(conn) -> None:
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free'")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
        ON users (google_sub) WHERE google_sub IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
        ON users (email) WHERE email IS NOT NULL
        """
    )
    try:
        conn.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")
    except Exception:
        pass


def _ensure_users_entitlements(conn) -> None:
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free'")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_updated_at TEXT")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mcp_quota_date TEXT")
    conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mcp_quota_used INTEGER NOT NULL DEFAULT 0"
    )


def _ensure_users_last_login_at(conn) -> None:
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TEXT")


def _ensure_user_opportunities_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            target_countries_json TEXT NOT NULL DEFAULT '[]',
            seniority TEXT NOT NULL DEFAULT '',
            keywords_json TEXT NOT NULL DEFAULT '[]',
            remote_ok INTEGER NOT NULL DEFAULT 0,
            preferences_confirmed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_opportunities (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            country TEXT NOT NULL,
            company_name TEXT NOT NULL,
            newest_fetched TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, country, company_name)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_opportunities_user_country
        ON user_opportunities (user_id, country)
        """
    )


def _ensure_preferences_confirmed(conn) -> None:
    conn.execute(
        """
        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS preferences_confirmed INTEGER NOT NULL DEFAULT 0
        """
    )
    conn.execute(
        """
        UPDATE user_preferences
        SET preferences_confirmed = 1
        WHERE preferences_confirmed = 0
          AND COALESCE(target_countries_json, '[]') NOT IN ('[]', '')
        """
    )


def _ensure_opportunities_refreshed_at(conn) -> None:
    conn.execute(
        """
        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS opportunities_refreshed_at TEXT
        """
    )


def _drop_user_preferences_country_columns(conn) -> None:
    for column in (
        "target_countries_json",
        "seniority",
        "keywords_json",
        "remote_ok",
        "preferences_confirmed",
    ):
        conn.execute(f"ALTER TABLE user_preferences DROP COLUMN IF EXISTS {column}")


def _ensure_opportunity_reveal_columns(conn) -> None:
    conn.execute(
        """
        ALTER TABLE user_opportunities
        ADD COLUMN IF NOT EXISTS revealed_job_count INTEGER NOT NULL DEFAULT 0
        """
    )
    conn.execute(
        """
        ALTER TABLE user_opportunities
        ADD COLUMN IF NOT EXISTS engaged INTEGER NOT NULL DEFAULT 0
        """
    )


def _ensure_position_broadcast_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS position_broadcast_assignments (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_key TEXT NOT NULL,
            country TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_key TEXT NOT NULL,
            job_url TEXT NOT NULL,
            job_title TEXT NOT NULL DEFAULT '',
            assigned_at TEXT NOT NULL,
            consumed_at TEXT,
            action_kind TEXT,
            PRIMARY KEY (user_id, period_key, country, company_name, job_key)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_position_broadcast_user_period
        ON position_broadcast_assignments (user_id, period_key, consumed_at)
        """
    )


def _ensure_credit_wallet_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_grants (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            source_key TEXT NOT NULL,
            total_credits INTEGER NOT NULL,
            remaining_credits INTEGER NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, source_key)
        );
        CREATE INDEX IF NOT EXISTS idx_credit_grants_spend
        ON credit_grants (user_id, expires_at, created_at);

        CREATE TABLE IF NOT EXISTS credit_ledger (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            operation TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE (user_id, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created
        ON credit_ledger (user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS credit_usage_migrations (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_key TEXT NOT NULL,
            migrated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, period_key)
        );

        CREATE TABLE IF NOT EXISTS credit_orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pack_key TEXT NOT NULL,
            credits INTEGER NOT NULL,
            price_minor INTEGER NOT NULL,
            currency TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,
            provider_order_id TEXT,
            checkout_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            paid_at TEXT,
            kind TEXT NOT NULL DEFAULT 'credits',
            UNIQUE (provider, provider_order_id)
        );
        CREATE INDEX IF NOT EXISTS idx_credit_orders_user_created
        ON credit_orders (user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS payment_events (
            id SERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            provider_order_id TEXT,
            payload_json TEXT NOT NULL,
            received_at TEXT NOT NULL,
            UNIQUE (provider, event_id)
        )
        """
    )


def _ensure_credit_order_kind(conn) -> None:
    conn.execute(
        """
        ALTER TABLE credit_orders
        ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'credits'
        """
    )


def _ensure_mcp_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_user_documents (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            master_resume_tex TEXT NOT NULL DEFAULT '',
            profile_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mcp_applications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            idempotency_key TEXT NOT NULL,
            country TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_url TEXT NOT NULL,
            tailored_tex TEXT,
            pdf_bytes BYTEA,
            meta_json TEXT NOT NULL DEFAULT '{}',
            tailored_tex_updated_at TEXT,
            pdf_updated_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE (user_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_mcp_applications_user
            ON mcp_applications(user_id, updated_at DESC);
        """
    )


def _migrate_mcp_master_resumes_v2(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_master_resumes (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            slug TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, slug)
        );

        ALTER TABLE mcp_applications
        ADD COLUMN IF NOT EXISTS master_resume_slug TEXT;
        """
    )
    conn.execute(
        """
        INSERT INTO mcp_master_resumes (user_id, slug, label, content, updated_at)
        SELECT user_id, 'default', 'Default', master_resume_tex, updated_at
        FROM mcp_user_documents
        WHERE TRIM(COALESCE(master_resume_tex, '')) <> ''
        ON CONFLICT (user_id, slug) DO NOTHING
        """
    )
    conn.execute(
        "ALTER TABLE mcp_user_documents DROP COLUMN IF EXISTS master_resume_tex"
    )


def _migrate_mcp_master_resumes_pdf_v1(conn) -> None:
    conn.execute(
        """
        ALTER TABLE mcp_master_resumes
        ADD COLUMN IF NOT EXISTS pdf_bytes BYTEA;
        ALTER TABLE mcp_master_resumes
        ADD COLUMN IF NOT EXISTS pdf_updated_at TEXT;
        """
    )


def _migrate_mcp_applications_country_lower(conn) -> None:
    conn.execute(
        """
        UPDATE mcp_applications
        SET country = LOWER(TRIM(country))
        WHERE country <> LOWER(TRIM(country))
        """
    )


def _migrate_mcp_cover_letter_v1(conn) -> None:
    conn.execute(
        """
        ALTER TABLE mcp_applications
        ADD COLUMN IF NOT EXISTS cover_letter_tex TEXT;
        ALTER TABLE mcp_applications
        ADD COLUMN IF NOT EXISTS cover_letter_pdf_bytes BYTEA;
        ALTER TABLE mcp_applications
        ADD COLUMN IF NOT EXISTS cover_letter_tex_updated_at TEXT;
        ALTER TABLE mcp_applications
        ADD COLUMN IF NOT EXISTS cover_letter_pdf_updated_at TEXT;
        """
    )


def _migrate_mcp_project_masters_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_project_masters (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            slug TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, slug)
        );
        """
    )


def _migrate_mcp_project_masters_pdf_v1(conn) -> None:
    conn.execute(
        """
        ALTER TABLE mcp_project_masters
        ADD COLUMN IF NOT EXISTS pdf_bytes BYTEA;
        ALTER TABLE mcp_project_masters
        ADD COLUMN IF NOT EXISTS pdf_updated_at TEXT;
        """
    )


def _migrate_mcp_interview_notes_v1(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_interview_notes (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            slug TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            pdf_bytes BYTEA,
            pdf_updated_at TEXT,
            PRIMARY KEY (user_id, slug)
        );
        """
    )


def _ensure_mcp_oauth_remote_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
            client_id TEXT PRIMARY KEY,
            client_info_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mcp_oauth_pending (
            request_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            params_json TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mcp_oauth_auth_codes (
            code_hash TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            scopes_json TEXT NOT NULL DEFAULT '[]',
            code_challenge TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            redirect_uri_provided_explicitly INTEGER NOT NULL DEFAULT 0,
            resource TEXT,
            expires_at TEXT NOT NULL,
            consumed_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mcp_oauth_tokens (
            token_hash TEXT PRIMARY KEY,
            token_kind TEXT NOT NULL,
            client_id TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            scopes_json TEXT NOT NULL DEFAULT '[]',
            resource TEXT,
            expires_at TEXT,
            revoked_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_mcp_oauth_tokens_user
            ON mcp_oauth_tokens(user_id, token_kind);

        CREATE TABLE IF NOT EXISTS mcp_api_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_mcp_api_tokens_user
            ON mcp_api_tokens(user_id);
        """
    )


def _ensure_fetch_runs_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            country TEXT NOT NULL,
            company_name TEXT,
            scope TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            duration_seconds REAL,
            exit_code INTEGER,
            cancelled INTEGER NOT NULL DEFAULT 0,
            new_jobs INTEGER NOT NULL DEFAULT 0,
            concurrency INTEGER,
            companies_done INTEGER,
            companies_total INTEGER,
            result_line TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_fetch_runs_user_started
            ON fetch_runs(user_id, started_at DESC);
        """
    )


def _migrate_company_tracking_schema(conn) -> None:
    conn.execute(
        """
        ALTER TABLE company_tracking
        ADD COLUMN IF NOT EXISTS awaiting_response INTEGER NOT NULL DEFAULT 0
        """
    )
    conn.execute(
        """
        ALTER TABLE company_tracking
        ADD COLUMN IF NOT EXISTS awaiting_response_date TEXT
        """
    )


def _migrate_board_pin_columns(conn) -> None:
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS pinned INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE job_tracking ADD COLUMN IF NOT EXISTS pinned_at TEXT"
    )
    conn.execute(
        "ALTER TABLE company_tracking ADD COLUMN IF NOT EXISTS board_pinned INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE company_tracking ADD COLUMN IF NOT EXISTS board_pinned_at TEXT"
    )


def _clear_company_board_pins(conn) -> None:
    conn.execute(
        """
        UPDATE company_tracking
        SET board_pinned = 0, board_pinned_at = NULL
        WHERE board_pinned = 1
        """
    )


def _ensure_status_events_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_status_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            country TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_url TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK (event_type IN ('applied', 'rejected')),
            event_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_job_status_events_user
            ON job_status_events(user_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_job_status_events_job
            ON job_status_events(user_id, country, company_name, job_url)
        """
    )


def _backfill_job_status_events(conn) -> None:
    """Seed history rows from legacy single applied_date / rejected_date columns."""
    rows = conn.execute(
        """
        SELECT user_id, country, company_name, job_url, applied, applied_date,
               rejected, rejected_date
        FROM job_tracking
        WHERE applied = 1 OR rejected = 1
        """
    ).fetchall()
    now = _utc_now()
    for row in rows:
        user_id = row["user_id"]
        country = row["country"]
        company_name = row["company_name"]
        job_url = _normalize_url(row.get("job_url", ""))
        if not job_url:
            continue
        if row.get("applied") and (row.get("applied_date") or "").strip():
            exists = conn.execute(
                """
                SELECT 1 FROM job_status_events
                WHERE user_id = %s AND country = %s AND company_name = %s
                  AND job_url = %s AND event_type = 'applied'
                LIMIT 1
                """,
                (user_id, country, company_name, job_url),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO job_status_events (
                        user_id, country, company_name, job_url,
                        event_type, event_date, created_at
                    ) VALUES (%s, %s, %s, %s, 'applied', %s, %s)
                    """,
                    (
                        user_id,
                        country,
                        company_name,
                        job_url,
                        (row.get("applied_date") or "").strip(),
                        now,
                    ),
                )
        if row.get("rejected") and (row.get("rejected_date") or "").strip():
            exists = conn.execute(
                """
                SELECT 1 FROM job_status_events
                WHERE user_id = %s AND country = %s AND company_name = %s
                  AND job_url = %s AND event_type = 'rejected'
                LIMIT 1
                """,
                (user_id, country, company_name, job_url),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO job_status_events (
                        user_id, country, company_name, job_url,
                        event_type, event_date, created_at
                    ) VALUES (%s, %s, %s, %s, 'rejected', %s, %s)
                    """,
                    (
                        user_id,
                        country,
                        company_name,
                        job_url,
                        (row.get("rejected_date") or "").strip(),
                        now,
                    ),
                )
