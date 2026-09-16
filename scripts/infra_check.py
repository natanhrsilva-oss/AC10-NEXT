from __future__ import annotations

import os
import sys
from contextlib import closing

import psycopg


EXPECTED_TABLES = [
    "ac10_runs",
    "ac10_matches",
    "ac10_team_profiles",
    "ac10_pregame_context",
    "ac10_live_latest",
    "ac10_live_snapshots",
    "ac10_recommendations",
    "ac10_results",
    "ac10_audits",
    "ac10_calibration_versions",
    "ac10_api_usage",
    "ac10_notifications",
]


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"❌ Secret ausente: {name}")
        sys.exit(2)
    print(f"✅ Secret configurado: {name}")
    return value


def main() -> int:
    db_url = require_env("SUPABASE_DATABASE_URL")

    # These are checked for presence only. They are not used or printed here.
    require_env("HIGHLIGHTLY_API_KEY")
    if os.getenv("DISCORD_WEBHOOK_URL", "").strip():
        print("✅ Secret configurado: DISCORD_WEBHOOK_URL")
    else:
        print("⚠️ DISCORD_WEBHOOK_URL ainda não configurado (não bloqueia este teste).")

    print("\nConectando ao Supabase...")
    try:
        with closing(psycopg.connect(db_url, connect_timeout=15)) as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database(), current_user, current_setting('TimeZone')")
                database, user, timezone = cur.fetchone()
                print(f"✅ PostgreSQL conectado | database={database} | timezone={timezone}")

                cur.execute(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = 'public'
                      and table_name = any(%s)
                    order by table_name
                    """,
                    (EXPECTED_TABLES,),
                )
                found = {row[0] for row in cur.fetchall()}
                missing = [t for t in EXPECTED_TABLES if t not in found]

                if missing:
                    print("\n❌ Schema incompleto. Tabelas ausentes:")
                    for table in missing:
                        print(f"   - {table}")
                    return 3

                print(f"✅ Schema oficial encontrado: {len(found)}/{len(EXPECTED_TABLES)} tabelas")

                # Verify write permission without leaving test data.
                # End the read transaction first, then perform a test insert and rollback it.
                conn.rollback()
                cur.execute(
                    """
                    insert into ac10_runs (run_type, model_version, status, parameters)
                    values ('INFRA_CHECK', '0.1.0', 'RUNNING', '{"source":"github-actions"}'::jsonb)
                    returning id
                    """
                )
                test_id = cur.fetchone()[0]
                cur.execute("select id from ac10_runs where id = %s", (test_id,))
                assert cur.fetchone() is not None
                conn.rollback()
                print("✅ Escrita no banco validada (transação revertida; nenhum dado de teste ficou salvo)")

    except Exception as exc:
        print(f"\n❌ Falha de infraestrutura: {type(exc).__name__}: {exc}")
        return 10

    print("\n🎉 AC10 Next: GitHub ↔ Supabase está pronto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
