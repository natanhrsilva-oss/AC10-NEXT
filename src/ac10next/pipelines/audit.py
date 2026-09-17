from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ac10next.engines.audit import evaluate_recommendation
from ac10next.outputs import sheets
from ac10next.providers.highlightly import HighlightlyClient
from ac10next.providers.parsers import FINISHED_STATES, first_half_goal_count, match_record, normalize_state, parse_score
from ac10next.repositories.database import Database
from ac10next.settings import Settings


async def run_audit(settings: Settings, target_date: str | None = None) -> dict:
    local=ZoneInfo(settings.app_timezone); target_date=target_date or (datetime.now(local).date()-timedelta(days=1)).isoformat(); started=time.perf_counter()
    async with Database(settings.supabase_database_url) as db, HighlightlyClient(settings) as provider:
        run_id=await db.create_run("AUDIT",settings.calibration_version,{"date":target_date})
        try:
            raws=await provider.matches_all(target_date,settings.app_timezone); finished=[]
            for raw in raws:
                m=match_record(raw,settings.app_timezone)
                if m and normalize_state(m.state) in FINISHED_STATES:finished.append((m,raw))
            ids=[m.match_id for m,_ in finished]; pending=await db.pending_audits(ids); by_match={}
            for r in pending:by_match.setdefault(str(r["match_id"]),[]).append(r)
            audited=greens=reds=pending_ht=0
            for m,raw in finished:
                fh,fa=parse_score(raw); await db.upsert_result(m.match_id,fh,fa,raw)
                recs=by_match.get(m.match_id,[])
                ht_goals=None
                if any(str(r.get("market") or "")=="GOL HT" for r in recs):
                    try:ht_goals=first_half_goal_count(await provider.events(m.match_id))
                    except Exception:ht_goals=None
                for rec in recs:
                    result,pnl,detail=evaluate_recommendation(rec,fh,fa,ht_goals=ht_goals); await db.insert_audit(str(rec["id"]),result,pnl,detail); audited+=1; greens+=result=="GREEN"; reds+=result=="RED"; pending_ht+=result=="PENDENTE_HT"
            output_errors=[]
            if settings.sheets_enabled and settings.google_sheets_webapp_url and settings.google_sheets_token:
                try:
                    pre_history=await db.fetch_recommendation_history("PRE",settings.sheet_history_limit)
                    live_history=await db.fetch_recommendation_history("LIVE",settings.sheet_history_limit)
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"PRE",pre_history,settings.app_timezone)
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"LIVE",live_history,settings.app_timezone)
                except Exception as exc:
                    output_errors.append(f"sheets:{exc}")
            await db.upsert_api_usage("highlightly","AUDIT",provider.usage()); metrics={"finished":len(finished),"audited":audited,"green":greens,"red":reds,"pending_ht":pending_ht,"output_errors":output_errors,"api":provider.usage()}; await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics); return metrics
        except Exception as exc:
            await db.finish_run(run_id,status="ERROR",duration_ms=int((time.perf_counter()-started)*1000),metrics={},error={"type":type(exc).__name__,"message":str(exc)}); raise
