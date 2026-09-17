from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ac10next.domain.mappers import pregame_from_row
from ac10next.domain.models import LiveInput, MatchRecord, PregameContext
from ac10next.engines.live.engine import analyze
from ac10next.engines.live.pricing import apply_price
from ac10next.filters import exclusion_reason
from ac10next.outputs import discord, sheets
from ac10next.pipelines.pre import PregameBuilder
from ac10next.providers.highlightly import HighlightlyClient
from ac10next.providers.parsers import LIVE_STATES, extract_highlightly_live_market_odd, live_stats, match_record, normalize_state
from ac10next.repositories.database import Database
from ac10next.settings import Settings

LOGGER=logging.getLogger(__name__)


def _due(now: datetime, previous: dict | None, fast: bool, settings: Settings) -> bool:
    if not previous:return True
    captured=previous.get("captured_at")
    if not captured:return True
    if captured.tzinfo is None:captured=captured.replace(tzinfo=timezone.utc)
    seconds=(now-captured).total_seconds(); required=settings.live_fast_lane_seconds if fast else settings.live_discovery_lane_seconds
    return seconds>=required*.85


def _row_context(row: dict) -> PregameContext:
    return pregame_from_row(row)


async def run_live(settings: Settings, *, force: bool = False) -> dict:
    started=time.perf_counter(); local=ZoneInfo(settings.app_timezone); now_local=datetime.now(local)
    if not force and not (settings.app_hour_start<=now_local.hour<=settings.app_hour_end):
        return {"skipped":True,"reason":"fora da janela operacional","hour":now_local.hour}
    target=now_local.date().isoformat(); now_utc=datetime.now(timezone.utc)
    async with Database(settings.supabase_database_url) as db, HighlightlyClient(settings) as provider:
        run_id=await db.create_run("LIVE",settings.live_model_version,{"date":target,"force":force})
        try:
            raw=await provider.matches_all(target,settings.app_timezone); live_records=[]
            for item in raw:
                m=match_record(item,settings.app_timezone)
                if not m or not m.match_id:continue
                state=normalize_state(m.state)
                if state not in LIVE_STATES:continue
                if not (settings.live_minute_start<=m.minute<=settings.live_minute_end):continue
                reason=exclusion_reason(m.country,m.competition,m.home_team,m.away_team,live=True)
                if reason:continue
                live_records.append(m)
            await db.upsert_matches(live_records)
            if not live_records:
                await db.upsert_api_usage("highlightly","LIVE",provider.usage()); metrics={"active":0,"processed":0,"api":provider.usage()}; await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics); return metrics
            ids=[m.match_id for m in live_records]; pre_rows=await db.fetch_pregame(ids,settings.pre_model_version); missing=[m for m in live_records if m.match_id not in pre_rows]
            emergency=0
            if missing:
                builder=PregameBuilder(settings,db,provider); built=await builder.build_for_records(missing,allow_odds=False); emergency=len(built); pre_rows=await db.fetch_pregame(ids,settings.pre_model_version)
            pre={mid:_row_context(row) for mid,row in pre_rows.items()}; live_records=[m for m in live_records if m.match_id in pre]
            ids=[m.match_id for m in live_records]; latest=await db.fetch_live_latest(ids,settings.live_model_version)
            due=[]
            for m in live_records:
                p=pre[m.match_id]; prev=latest.get(m.match_id); fast=p.live_priority in {"A","B"} or (prev and (prev.get("status") in {"AQUECENDO","SINAL","RECOMENDAÇÃO"} or float(prev.get("market_index") or 0)>=50))
                if force or _due(now_utc,prev,fast,settings):due.append((0 if fast else 1,-p.live_readiness_score,m))
            due=[x[2] for x in sorted(due,key=lambda x:(x[0],x[1]))[:settings.live_max_stats_requests_per_run]]
            if not due:
                await db.upsert_api_usage("highlightly","LIVE",provider.usage()); metrics={"active":len(live_records),"due":0,"processed":0,"emergency_pre":emergency,"api":provider.usage()}; await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics); return metrics
            async def stats_one(m:MatchRecord):
                try:return m.match_id,live_stats(await provider.statistics(m.match_id),m.home_team_id,m.away_team_id)
                except Exception as exc:
                    LOGGER.warning("Stats live falharam %s: %s",m.match_id,exc); return m.match_id,live_stats([],m.home_team_id,m.away_team_id)
            stats=dict(await asyncio.gather(*(stats_one(m) for m in due)))
            due_ids=[m.match_id for m in due]; history=await db.fetch_live_history(due_ids,settings.live_model_version,6); latest_due={mid:latest.get(mid) for mid in due_ids}
            analyses=[]
            for m in due:
                inp=LiveInput(match=m,pre=pre[m.match_id],stats=stats[m.match_id],captured_at=now_utc)
                analyses.append(analyze(inp,latest_due.get(m.match_id),history.get(m.match_id,[])))

            # Odds live are intentionally fetched only after the sporting engine
            # has produced genuine recommendation candidates. This keeps the
            # expensive/slow odds endpoint out of the normal scan path.
            price_candidates=sorted(
                [a for a in analyses if a.status=="SINAL"],
                key=lambda a:(a.market_index,a.confirmation_count,a.selected_probability),
                reverse=True,
            )[:settings.live_max_odds_requests_per_run]
            async def price_one(a):
                try:
                    payload=await provider.live_odds(a.match_id)
                    odd=extract_highlightly_live_market_odd(
                        payload,a.selected_market,a.home_score,a.away_score,settings.highlightly_bookmaker
                    )
                    return a.match_id,odd
                except Exception as exc:
                    LOGGER.info("Odds live indisponíveis %s (%s): %s",a.match_id,a.selected_market,exc)
                    return a.match_id,0.0
            live_prices=dict(await asyncio.gather(*(price_one(a) for a in price_candidates))) if price_candidates else {}
            for a in analyses:
                if a.match_id in live_prices:
                    apply_price(a,float(live_prices[a.match_id] or 0),settings)

            await db.upsert_live_latest(analyses,settings.live_model_version); await db.insert_snapshots(analyses,settings.live_model_version)
            rec_count=await db.insert_recommendations(analyses,live_model_version=settings.live_model_version,pre_model_version=settings.pre_model_version,calibration_version=settings.calibration_version)
            match_map={m.match_id:m for m in due}; pre_due={m.match_id:pre[m.match_id] for m in due}; output_errors=[]
            if settings.sheets_enabled and settings.google_sheets_webapp_url and settings.google_sheets_token:
                try:
                    await sheets.send_live(settings.google_sheets_webapp_url,settings.google_sheets_token,match_map,analyses,pre_due)
                    live_history=await db.fetch_recommendation_history("LIVE",settings.sheet_history_limit) if rec_count else []
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"LIVE",live_history,settings.app_timezone)
                except Exception as exc:output_errors.append(f"sheets:{exc}")
            if settings.live_discord_enabled and settings.discord_webhook_url:
                summary=discord.live_summary(match_map,analyses,pre_due,min_index=settings.live_summary_min_index,limit=settings.live_summary_limit)
                if summary:
                    key,text=summary
                    if await db.claim_notification(key,"discord",{"content":text}):
                        try:await discord.send(settings.discord_webhook_url,text); await db.mark_notification(key,sent=True)
                        except Exception as exc:await db.mark_notification(key,sent=False,error=str(exc)); output_errors.append(f"discord:{exc}")
            await db.upsert_api_usage("highlightly","LIVE",provider.usage())
            metrics={"active":len(live_records),"due":len(due),"processed":len(analyses),"above_55":sum(a.market_index>=settings.live_summary_min_index for a in analyses),"sporting_candidates":len(price_candidates),"signals_unpriced":sum(a.status=="SINAL" for a in analyses),"recommendations":sum(a.status=="RECOMENDAÇÃO" for a in analyses),"new_recommendations":rec_count,"odds_candidates":len(price_candidates),"priced":sum(a.market_odd is not None for a in analyses),"post_goal_cooldowns":sum(bool((a.raw.get("event_state") or {}).get("post_goal_active")) for a in analyses),"stale_blocks":sum(bool((a.raw.get("data_freshness") or {}).get("stale_block")) for a in analyses),"emergency_pre":emergency,"output_errors":output_errors,"api":provider.usage()}
            await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics); return metrics
        except Exception as exc:
            await db.upsert_api_usage("highlightly","LIVE",provider.usage()); await db.finish_run(run_id,status="ERROR",duration_ms=int((time.perf_counter()-started)*1000),metrics={"api":provider.usage()},error={"type":type(exc).__name__,"message":str(exc)}); raise
