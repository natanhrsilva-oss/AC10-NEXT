from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ac10next.engines.audit import evaluate_recommendation
from ac10next.outputs import discord, sheets
from ac10next.providers.highlightly import HighlightlyClient
from ac10next.providers.parsers import FINISHED_STATES, first_half_goal_count, match_record, normalize_state, parse_score
from ac10next.repositories.database import Database
from ac10next.settings import Settings


def _date_range(start: date, end: date) -> list[date]:
    days=(end-start).days
    return [start+timedelta(days=i) for i in range(days+1)]


def _finished_with_pending_recommendations(
    finished: list[tuple[object, dict]],
    by_match: dict[str, list[dict]],
) -> list[tuple[object, dict]]:
    """Keep only provider matches that actually have AC10 recommendations to audit.

    Highlightly returns every finished fixture in the requested date range. Persisting
    all of them to ac10_results is both unnecessary and unsafe because ac10_results
    references ac10_matches. Only matches with pending AC10 recommendations need a
    final result persisted/evaluated.
    """
    return [
        (match, raw)
        for match, raw in finished
        if str(getattr(match, "match_id", "")) in by_match
    ]


async def run_audit(settings: Settings, target_date: str | None = None) -> dict:
    """Run the weekly PRE/LIVE audit and publish one consolidated report.

    The report window is seven local calendar days ending on ``target_date`` (or
    today). Collection intentionally also revisits the previous boundary day so
    late Tuesday matches that were unfinished at the prior 23:00 audit can still
    be settled without bringing the old daily audit back.
    """
    local=ZoneInfo(settings.app_timezone)
    end_date=date.fromisoformat(target_date) if target_date else datetime.now(local).date()
    report_start=end_date-timedelta(days=6)
    recovery_start=end_date-timedelta(days=7)
    started=time.perf_counter()

    async with Database(settings.supabase_database_url) as db, HighlightlyClient(settings) as provider:
        run_id=await db.create_run(
            "AUDIT",
            settings.calibration_version,
            {
                "date":end_date.isoformat(),
                "start_date":report_start.isoformat(),
                "end_date":end_date.isoformat(),
                "recovery_start":recovery_start.isoformat(),
                "mode":"WEEKLY",
            },
        )
        try:
            finished_by_id:dict[str,tuple[object,dict]]={}
            for audit_day in _date_range(recovery_start,end_date):
                raws=await provider.matches_all(audit_day.isoformat(),settings.app_timezone)
                for raw in raws:
                    m=match_record(raw,settings.app_timezone)
                    if m and normalize_state(m.state) in FINISHED_STATES:
                        finished_by_id[m.match_id]=(m,raw)

            finished=list(finished_by_id.values())
            ids=list(finished_by_id)

            # First discover which finished fixtures actually have pending AC10
            # recommendations. Do not persist results for unrelated provider games.
            pending=await db.pending_audits(ids)
            by_match:dict[str,list[dict]]={}
            for rec in pending:
                by_match.setdefault(str(rec["match_id"]),[]).append(rec)

            relevant_finished=_finished_with_pending_recommendations(finished,by_match)

            audited=greens=reds=pending_ht=0
            for m,raw in relevant_finished:
                recs=by_match.get(str(m.match_id),[])
                if not recs:
                    continue

                fh,fa=parse_score(raw)

                # Safe now: a recommendation can only reference an AC10 match, so
                # ac10_results' FK is satisfied. Unrelated Highlightly fixtures never
                # reach this write.
                await db.upsert_result(m.match_id,fh,fa,raw)

                ht_goals=None
                if any(str(r.get("market") or "")=="GOL HT" for r in recs):
                    try:
                        ht_goals=first_half_goal_count(await provider.events(m.match_id))
                    except Exception:
                        ht_goals=None

                for rec in recs:
                    result,pnl,detail=evaluate_recommendation(rec,fh,fa,ht_goals=ht_goals)
                    await db.insert_audit(str(rec["id"]),result,pnl,detail)
                    audited+=1
                    greens+=result=="GREEN"
                    reds+=result=="RED"
                    pending_ht+=result=="PENDENTE_HT"

            output_errors=[]
            if settings.sheets_enabled and settings.google_sheets_webapp_url and settings.google_sheets_token:
                try:
                    pre_history=await db.fetch_recommendation_history("PRE",settings.sheet_history_limit)
                    live_history=await db.fetch_recommendation_history("LIVE",settings.sheet_history_limit)
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"PRE",pre_history,settings.app_timezone)
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"LIVE",live_history,settings.app_timezone)
                except Exception as exc:
                    output_errors.append(f"sheets:{exc}")

            stats=await db.weekly_audit_stats(report_start.isoformat(),end_date.isoformat())
            reliability=await db.live_run_reliability(report_start.isoformat(),end_date.isoformat())
            hours_per_day=max(0,settings.app_hour_end-settings.app_hour_start+1)
            expected_live_slots=7*hours_per_day*4

            if settings.pre_discord_enabled and settings.pre_discord_webhook:
                text=discord.weekly_audit_summary(stats,reliability,expected_live_slots=expected_live_slots)
                key=f"audit-weekly:{report_start.isoformat()}:{end_date.isoformat()}"
                if await db.claim_notification(key,"discord-audit",{"content":text,"start_date":report_start.isoformat(),"end_date":end_date.isoformat()}):
                    try:
                        await discord.send(settings.pre_discord_webhook,text)
                        await db.mark_notification(key,sent=True)
                    except Exception as exc:
                        await db.mark_notification(key,sent=False,error=str(exc))
                        output_errors.append(f"discord:{exc}")

            await db.upsert_api_usage("highlightly","AUDIT",provider.usage())
            metrics={
                "mode":"WEEKLY",
                "report_start":report_start.isoformat(),
                "report_end":end_date.isoformat(),
                "recovery_start":recovery_start.isoformat(),
                "finished":len(finished),
                "finished_relevant":len(relevant_finished),
                "pending_recommendations":len(pending),
                "audited":audited,
                "green":greens,
                "red":reds,
                "pending_ht":pending_ht,
                "weekly_stats":stats,
                "live_reliability":reliability,
                "expected_live_slots":expected_live_slots,
                "output_errors":output_errors,
                "api":provider.usage(),
            }
            await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics)
            return metrics
        except Exception as exc:
            await db.upsert_api_usage("highlightly","AUDIT",provider.usage())
            await db.finish_run(
                run_id,status="ERROR",duration_ms=int((time.perf_counter()-started)*1000),metrics={"api":provider.usage()},
                error={"type":type(exc).__name__,"message":str(exc)},
            )
            raise
