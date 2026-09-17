from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from ac10next.competition_priority import competition_priority_score
from ac10next.domain.mappers import team_profile_from_row
from ac10next.domain.models import MatchRecord, PregameContext, TeamProfile
from ac10next.engines.pregame.meta import build_context
from ac10next.engines.pregame.profiles import build_features, make_team_profile
from ac10next.engines.pregame.precision import decorate_precision, precision_score, select_pre_recommendations
from ac10next.engines.pregame.strategies import evaluate_all
from ac10next.filters import exclusion_reason
from ac10next.outputs import discord, sheets
from ac10next.providers.highlightly import HighlightlyClient
from ac10next.providers.parsers import extract_highlightly_main_odds, match_record
from ac10next.repositories.database import Database
from ac10next.settings import Settings

LOGGER = logging.getLogger(__name__)


class PregameBuilder:
    def __init__(self, settings: Settings, db: Database, provider: HighlightlyClient):
        self.settings=settings; self.db=db; self.provider=provider

    async def _refresh_profile(self, team_id: str, team_name: str, from_date: str) -> TeamProfile:
        recent_task=self.provider.last_five(team_id)
        history_task=self.provider.team_statistics(team_id,from_date,self.settings.app_timezone)
        recent,history=await asyncio.gather(recent_task,history_task)
        return make_team_profile(team_id,team_name,recent,history,self.settings.team_profile_cache_hours)

    async def ensure_profiles(self, records: Iterable[MatchRecord]) -> dict[str,TeamProfile]:
        teams:dict[str,str]={}
        for m in records:
            if m.home_team_id:teams[m.home_team_id]=m.home_team
            if m.away_team_id:teams[m.away_team_id]=m.away_team
        cached=await self.db.fetch_team_profiles(list(teams))
        now=datetime.now(timezone.utc); profiles={tid:team_profile_from_row(row) for tid,row in cached.items()}
        refresh=[]
        for tid,name in teams.items():
            p=profiles.get(tid)
            valid=p and p.valid_until and (p.valid_until if p.valid_until.tzinfo else p.valid_until.replace(tzinfo=timezone.utc))>now
            if not valid:refresh.append((tid,name))
        refresh=refresh[:self.settings.pre_max_teams_refresh]
        from_date=(date.today()-timedelta(days=self.settings.history_lookback_days)).isoformat()
        async def one(tid,name):
            try:return await self._refresh_profile(tid,name,from_date)
            except Exception as exc:
                LOGGER.warning("Perfil indisponível %s (%s): %s",name,tid,exc)
                return profiles.get(tid) or TeamProfile(team_id=tid,team_name=name,data_quality=20,source="fallback")
        refreshed=await asyncio.gather(*(one(tid,name) for tid,name in refresh)) if refresh else []
        for p in refreshed:profiles[p.team_id]=p
        await self.db.upsert_team_profiles(refreshed)
        for tid,name in teams.items():
            profiles.setdefault(tid,TeamProfile(team_id=tid,team_name=name,data_quality=20,source="fallback"))
        return profiles

    def _base_context(self, m: MatchRecord, profiles: dict[str,TeamProfile]) -> tuple[PregameContext, object]:
        f=build_features(m,profiles[m.home_team_id],profiles[m.away_team_id],self.settings.recent_weight,self.settings.historical_weight)
        f.competition_priority=competition_priority_score(m.country,m.competition)
        c=build_context(f,evaluate_all(f),self.settings.pre_model_version)
        return c,f

    async def build_for_records(self, records: list[MatchRecord], *, allow_odds: bool = True) -> list[PregameContext]:
        if not records:return []
        profiles=await self.ensure_profiles(records)
        pairs=[self._base_context(m,profiles) for m in records]
        contexts=[c for c,_ in pairs]
        features={c.match_id:f for c,f in pairs}
        if allow_odds:
            shortlist=sorted(
                [c for c in contexts if c.selected_index>=self.settings.pre_odds_min_index],
                key=lambda c:(precision_score(c),c.confidence,c.selected_index),
                reverse=True,
            )[:self.settings.pre_max_odds_requests]
            async def odds_one(c:PregameContext):
                try:return c.match_id,extract_highlightly_main_odds(await self.provider.prematch_odds(c.match_id),self.settings.highlightly_bookmaker)
                except Exception as exc:
                    LOGGER.info("Odds pré indisponíveis %s: %s",c.match_id,exc); return c.match_id,{}
            odds=dict(await asyncio.gather(*(odds_one(c) for c in shortlist))) if shortlist else {}
            rebuilt=[]
            for c in contexts:
                f=features[c.match_id]; o=odds.get(c.match_id) or {}
                if o:
                    f.home_odd=float(o.get("home") or 0); f.draw_odd=float(o.get("draw") or 0); f.away_odd=float(o.get("away") or 0); f.over25_odd=float(o.get("over25") or 0)
                    c=build_context(f,evaluate_all(f),self.settings.pre_model_version)
                rebuilt.append(c)
            contexts=rebuilt
        for c in contexts:
            decorate_precision(c,self.settings)
        await self.db.upsert_pregame(contexts)
        return contexts


async def run_pre(settings: Settings, target_date: str | None = None) -> dict:
    started=time.perf_counter(); local=ZoneInfo(settings.app_timezone); target_date=target_date or datetime.now(local).date().isoformat()
    async with Database(settings.supabase_database_url) as db, HighlightlyClient(settings) as provider:
        run_id=await db.create_run("PRE",settings.pre_model_version,{"date":target_date})
        try:
            raw=await provider.matches_all(target_date,settings.app_timezone); records=[]
            for item in raw:
                m=match_record(item,settings.app_timezone)
                if not m or not m.match_id:continue
                reason=exclusion_reason(m.country,m.competition,m.home_team,m.away_team)
                m.is_excluded=bool(reason); m.exclusion_reason=reason or ""; records.append(m)
            await db.upsert_matches(records)
            eligible=[m for m in records if not m.is_excluded and m.home_team_id and m.away_team_id]
            builder=PregameBuilder(settings,db,provider); contexts=await builder.build_for_records(eligible,allow_odds=True)
            match_map={m.match_id:m for m in eligible}

            # PRE recommendation is a high-precision layer, deliberately separate
            # from Live Readiness. All contexts still feed LIVE; only the strongest
            # priced candidates are offered as standalone PRE recommendations.
            pre_recommendations=select_pre_recommendations(contexts,settings)
            new_pre_recommendations=await db.insert_pre_recommendations(
                pre_recommendations,
                pre_model_version=settings.pre_model_version,
                calibration_version=settings.calibration_version,
            )

            # Outputs are deliberately non-blocking for the sporting pipeline.
            output_errors=[]
            if settings.sheets_enabled and settings.google_sheets_webapp_url and settings.google_sheets_token:
                try:
                    await sheets.send_pre(settings.google_sheets_webapp_url,settings.google_sheets_token,match_map,contexts)
                    pre_history=await db.fetch_recommendation_history("PRE",settings.sheet_history_limit) if new_pre_recommendations else []
                    await sheets.send_history(settings.google_sheets_webapp_url,settings.google_sheets_token,"PRE",pre_history,settings.app_timezone)
                except Exception as exc:output_errors.append(f"sheets:{exc}")
            if settings.pre_discord_enabled and settings.discord_webhook_url:
                summary=discord.pre_summary(match_map,pre_recommendations,total_prepared=len(contexts),limit=settings.pre_recommendation_limit)
                if summary:
                    key,text=summary
                    if await db.claim_notification(key,"discord",{"content":text}):
                        try:await discord.send(settings.discord_webhook_url,text); await db.mark_notification(key,sent=True)
                        except Exception as exc:await db.mark_notification(key,sent=False,error=str(exc)); output_errors.append(f"discord:{exc}")
            await db.upsert_api_usage("highlightly","PRE",provider.usage())
            metrics={"matches_found":len(records),"eligible":len(eligible),"contexts":len(contexts),"priority_A":sum(c.live_priority=="A" for c in contexts),"priority_B":sum(c.live_priority=="B" for c in contexts),"pre_recommendations":len(pre_recommendations),"new_pre_recommendations":new_pre_recommendations,"output_errors":output_errors,"api":provider.usage()}
            await db.finish_run(run_id,status="SUCCESS",duration_ms=int((time.perf_counter()-started)*1000),metrics=metrics)
            return metrics
        except Exception as exc:
            await db.upsert_api_usage("highlightly","PRE",provider.usage())
            await db.finish_run(run_id,status="ERROR",duration_ms=int((time.perf_counter()-started)*1000),metrics={"api":provider.usage()},error={"type":type(exc).__name__,"message":str(exc)})
            raise
