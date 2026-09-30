from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from ac10next.pipelines.audit import run_audit
from ac10next.pipelines.live import run_live, run_live_scheduled
from ac10next.pipelines.pre import run_pre
from ac10next.repositories.database import Database
from ac10next.settings import Settings


def _configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _validate_core(settings: Settings, *, need_highlightly: bool = True) -> None:
    missing: list[str] = []
    if not settings.supabase_database_url.strip():
        missing.append("SUPABASE_DATABASE_URL")
    if need_highlightly and not settings.highlightly_api_key.strip():
        missing.append("HIGHLIGHTLY_API_KEY")
    if missing:
        raise SystemExit("Secrets/variáveis obrigatórios ausentes: " + ", ".join(missing))


async def _health(settings: Settings) -> dict:
    _validate_core(settings, need_highlightly=False)
    expected = {
        "ac10_runs", "ac10_matches", "ac10_team_profiles", "ac10_pregame_context",
        "ac10_live_latest", "ac10_live_snapshots", "ac10_recommendations", "ac10_results",
        "ac10_audits", "ac10_calibration_versions", "ac10_api_usage", "ac10_notifications",
    }
    async with Database(settings.supabase_database_url) as db:
        async with db.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "select table_name from information_schema.tables where table_schema='public' and table_name like 'ac10_%'"
                )
                found = {str(row["table_name"]) for row in await cur.fetchall()}
                await cur.execute("select count(*) as n from ac10_runs")
                runs = int((await cur.fetchone())["n"])
    missing = sorted(expected - found)
    return {
        "ok": not missing,
        "database": "connected",
        "schema": f"{len(expected & found)}/{len(expected)}",
        "missing_tables": missing,
        "runs": runs,
        "pre_model_version": settings.pre_model_version,
        "live_model_version": settings.live_model_version,
        "timezone": settings.app_timezone,
        "local_time": datetime.now(ZoneInfo(settings.app_timezone)).isoformat(timespec="seconds"),
        "discord_configured": bool(settings.pre_discord_webhook or settings.live_discord_webhook),
        "discord_pre_configured": bool(settings.pre_discord_webhook),
        "discord_live_configured": bool(settings.live_discord_webhook),
        "sheets_configured": bool(settings.google_sheets_webapp_url.strip() and settings.google_sheets_token.strip()),
    }


async def _async_main(args: argparse.Namespace) -> dict:
    settings = Settings()
    if args.command == "health":
        return await _health(settings)
    _validate_core(settings)
    if args.command == "pre":
        return await run_pre(settings, target_date=args.date, skip_if_success=args.if_missing)
    if args.command == "live":
        if args.scheduled:
            return await run_live_scheduled(settings)
        return await run_live(settings, force=args.force)
    if args.command == "audit":
        return await run_audit(settings, target_date=args.date)
    raise SystemExit(f"Comando desconhecido: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ac10-next", description="AC10 Next — PRE, LIVE e AUDIT")
    parser.add_argument("--verbose", action="store_true", help="Logs detalhados")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Valida conexão e schema do Supabase")
    health.set_defaults(command="health")

    pre = sub.add_parser("pre", help="Executa o AC10 PRE")
    pre.add_argument("--date", help="Data YYYY-MM-DD. Padrão: hoje em America/Sao_Paulo")
    pre.add_argument("--if-missing", action="store_true", help="Executa somente se não houver PRE SUCCESS para a data")

    live = sub.add_parser("live", help="Executa o AC10 LIVE")
    live.add_argument("--force", action="store_true", help="Ignora janela operacional e controle de frequência")
    live.add_argument("--scheduled", action="store_true", help="Controlador: executa LIVE quando passaram >=15 min desde o último LIVE SUCCESS")

    audit = sub.add_parser("audit", help="Executa a auditoria semanal PRE + LIVE")
    audit.add_argument("--date", help="Data final YYYY-MM-DD da janela semanal. Padrão: hoje em America/Sao_Paulo")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)
    try:
        result = asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        raise SystemExit(130)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if isinstance(result, dict) and result.get("ok") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
