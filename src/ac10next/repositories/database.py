from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ac10next.domain.models import LiveAnalysis, MatchRecord, PregameContext, TeamProfile
from ac10next.utils import json_safe


class Database:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 5):
        self.pool = AsyncConnectionPool(conninfo=dsn, min_size=min_size, max_size=max_size, open=False)

    async def __aenter__(self):
        await self.pool.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.pool.close()

    async def create_run(self, run_type: str, model_version: str, parameters: dict[str, Any] | None = None) -> str:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "insert into ac10_runs(run_type,model_version,status,parameters) values(%s,%s,'RUNNING',%s) returning id",
                    (run_type, model_version, Jsonb(parameters or {})),
                )
                row = await cur.fetchone()
                await conn.commit()
                return str(row[0])

    async def finish_run(self, run_id: str, *, status: str, duration_ms: int, metrics: dict[str, Any], error: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "update ac10_runs set status=%s,finished_at=now(),duration_ms=%s,metrics=%s,error=%s where id=%s",
                (status, duration_ms, Jsonb(metrics), Jsonb(error) if error else None, run_id),
            )
            await conn.commit()

    async def upsert_matches(self, matches: Iterable[MatchRecord]) -> None:
        rows = list(matches)
        if not rows:
            return
        sql = """
        insert into ac10_matches(match_id,kickoff,match_date,country,competition_id,competition,season,home_team_id,home_team,away_team_id,away_team,state,is_excluded,exclusion_reason,provider_payload,updated_at)
        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
        on conflict(match_id) do update set kickoff=excluded.kickoff,match_date=excluded.match_date,country=excluded.country,competition_id=excluded.competition_id,competition=excluded.competition,season=excluded.season,home_team_id=excluded.home_team_id,home_team=excluded.home_team,away_team_id=excluded.away_team_id,away_team=excluded.away_team,state=excluded.state,is_excluded=excluded.is_excluded,exclusion_reason=excluded.exclusion_reason,provider_payload=excluded.provider_payload,updated_at=now()
        """
        params = [
            (m.match_id,m.kickoff,m.match_date,m.country,m.competition_id,m.competition,m.season,m.home_team_id,m.home_team,m.away_team_id,m.away_team,m.state,m.is_excluded,m.exclusion_reason,Jsonb(m.raw))
            for m in rows
        ]
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql, params)
            await conn.commit()

    async def fetch_team_profiles(self, team_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not team_ids:
            return {}
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("select * from ac10_team_profiles where team_id = any(%s)", (team_ids,))
                return {str(r["team_id"]): dict(r) for r in await cur.fetchall()}

    async def upsert_team_profiles(self, profiles: Iterable[TeamProfile]) -> None:
        rows=list(profiles)
        if not rows: return
        sql="""
        insert into ac10_team_profiles(team_id,team_name,recent_matches,history_matches,recent_form,attack,defense,weight,avg_gf,avg_ga,over25_rate,competition_history_strength,opponent_strength,data_quality,source,last_match_id,valid_until,raw,calculated_at,updated_at)
        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now())
        on conflict(team_id) do update set team_name=excluded.team_name,recent_matches=excluded.recent_matches,history_matches=excluded.history_matches,recent_form=excluded.recent_form,attack=excluded.attack,defense=excluded.defense,weight=excluded.weight,avg_gf=excluded.avg_gf,avg_ga=excluded.avg_ga,over25_rate=excluded.over25_rate,competition_history_strength=excluded.competition_history_strength,opponent_strength=excluded.opponent_strength,data_quality=excluded.data_quality,source=excluded.source,last_match_id=excluded.last_match_id,valid_until=excluded.valid_until,raw=excluded.raw,calculated_at=now(),updated_at=now()
        """
        params=[(p.team_id,p.team_name,p.recent_matches,p.history_matches,p.recent_form,p.attack,p.defense,p.weight,p.avg_gf,p.avg_ga,p.over25_rate,p.competition_history_strength,p.opponent_strength,p.data_quality,p.source,p.last_match_id,p.valid_until,Jsonb(p.raw)) for p in rows]
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur: await cur.executemany(sql,params)
            await conn.commit()

    async def upsert_pregame(self, contexts: Iterable[PregameContext]) -> None:
        rows=list(contexts)
        if not rows: return
        cols = [
            "match_id","model_version","calculated_at","data_quality","competition_priority","home_attack","home_defense","home_weight","home_recent_form","away_attack","away_defense","away_weight","away_recent_form","expected_home_goals","expected_away_goals","expected_total_goals","league_avg_goals","league_over25_rate","home_persona","away_persona","home_posture","away_posture","game_profile","back_home_probability","back_away_probability","goals_probability","back_home_index","back_away_index","goals_index","selected_market","selected_probability","selected_index","market_margin","confidence","draw_risk","goals_profile","explosive_score","live_readiness_score","live_priority","home_odd","draw_odd","away_odd","over25_odd","raw"
        ]
        placeholders=",".join(["%s"]*len(cols))
        update=",".join(f"{c}=excluded.{c}" for c in cols[2:])
        sql=f"insert into ac10_pregame_context({','.join(cols)}) values({placeholders}) on conflict(match_id,model_version) do update set {update}"
        params=[]
        for c in rows:
            vals=[getattr(c,k) for k in cols[:-1]]+[Jsonb(c.raw)]
            params.append(tuple(vals))
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur: await cur.executemany(sql,params)
            await conn.commit()

    async def fetch_pregame(self, match_ids: list[str], model_version: str) -> dict[str, dict[str, Any]]:
        if not match_ids:return {}
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("select * from ac10_pregame_context where match_id=any(%s) and model_version=%s",(match_ids,model_version))
                return {str(r["match_id"]):dict(r) for r in await cur.fetchall()}

    async def fetch_live_latest(self, match_ids: list[str], live_model_version: str) -> dict[str, dict[str, Any]]:
        if not match_ids:return {}
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("select * from ac10_live_latest where match_id=any(%s) and live_model_version=%s",(match_ids,live_model_version))
                return {str(r["match_id"]):dict(r) for r in await cur.fetchall()}

    async def fetch_live_history(self, match_ids: list[str], live_model_version: str, limit_per_match: int = 6) -> dict[str,list[dict[str,Any]]]:
        if not match_ids:return {}
        sql="""
        select * from (
          select s.*, row_number() over(partition by match_id order by captured_at desc) rn
          from ac10_live_snapshots s where match_id=any(%s) and live_model_version=%s
        ) q where rn<=%s order by match_id,captured_at
        """
        out:dict[str,list[dict[str,Any]]]={}
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql,(match_ids,live_model_version,limit_per_match))
                for row in await cur.fetchall():
                    d=dict(row); d.pop("rn",None); out.setdefault(str(d["match_id"]),[]).append(d)
        return out

    async def upsert_live_latest(self, analyses: Iterable[LiveAnalysis], live_model_version: str) -> None:
        rows=list(analyses)
        if not rows:return
        cols=["match_id","live_model_version","captured_at","minute","home_score","away_score","state","live_data_mode","data_quality","home_shots","away_shots","home_sot","away_sot","home_corners","away_corners","home_dangerous","away_dangerous","home_possession","away_possession","home_red_cards","away_red_cards","home_pressure","away_pressure","home_recent_pressure","away_recent_pressure","home_momentum","away_momentum","home_momentum_slope","away_momentum_slope","activity","gpi","gpi_delta","home_idd","away_idd","idd_delta","home_need","away_need","chance_goal_10","over15_more_probability","movement_score","movement_trend","selected_market","selected_probability","market_index","market_quality","confirmation_count","status","fair_odd","market_odd","ev_percent","price_status","raw"]
        ph=",".join(["%s"]*len(cols)); update=",".join(f"{c}=excluded.{c}" for c in cols[2:])
        sql=f"insert into ac10_live_latest({','.join(cols)}) values({ph}) on conflict(match_id,live_model_version) do update set {update}"
        params=[]
        for a in rows:
            vals=[]
            for c in cols:
                if c=="live_model_version":vals.append(live_model_version)
                elif c=="raw":vals.append(Jsonb(a.raw))
                else:vals.append(getattr(a,c))
            params.append(tuple(vals))
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur: await cur.executemany(sql,params)
            await conn.commit()

    async def insert_snapshots(self, analyses: Iterable[LiveAnalysis], live_model_version: str) -> None:
        rows=list(analyses)
        if not rows:return
        sql="""
        insert into ac10_live_snapshots(match_id,live_model_version,captured_at,minute,home_score,away_score,home_shots,away_shots,home_sot,away_sot,home_corners,away_corners,home_dangerous,away_dangerous,home_pressure,away_pressure,home_recent_pressure,away_recent_pressure,home_momentum,away_momentum,gpi,home_idd,away_idd,chance_goal_10,over15_more_probability,movement_score,selected_market,market_index,selected_probability,market_quality,confirmation_count,status,fingerprint,raw)
        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict(match_id,live_model_version,fingerprint) do nothing
        """
        params=[(a.match_id,live_model_version,a.captured_at,a.minute,a.home_score,a.away_score,a.home_shots,a.away_shots,a.home_sot,a.away_sot,a.home_corners,a.away_corners,a.home_dangerous,a.away_dangerous,a.home_pressure,a.away_pressure,a.home_recent_pressure,a.away_recent_pressure,a.home_momentum,a.away_momentum,a.gpi,a.home_idd,a.away_idd,a.chance_goal_10,a.over15_more_probability,a.movement_score,a.selected_market,a.market_index,a.selected_probability,a.market_quality,a.confirmation_count,a.status,a.fingerprint,Jsonb(a.raw)) for a in rows]
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur: await cur.executemany(sql,params)
            await conn.commit()


    async def insert_pre_recommendations(self, contexts: Iterable[PregameContext], *, pre_model_version: str, calibration_version: str) -> int:
        rows=list(contexts)
        if not rows:return 0
        sql="""
        insert into ac10_recommendations(match_id,source,market,minute,probability,market_index,confidence,market_odd,fair_odd,ev_percent,status,pre_model_version,live_model_version,calibration_version,dedupe_key,payload)
        values(%s,'PRE',%s,null,%s,%s,%s,%s,%s,%s,'RECOMENDAÇÃO',%s,null,%s,%s,%s)
        on conflict(dedupe_key) do nothing
        """
        params=[]
        for c in rows:
            precision=dict(c.raw.get("precision") or {})
            odd=precision.get("odd")
            fair=precision.get("fair_odd")
            ev=precision.get("ev_percent")
            dedupe=f"PRE:{pre_model_version}:{c.match_id}:{c.selected_market}"
            payload={
                "precision_score":precision.get("score"),
                "model_confidence":c.confidence,
                "data_quality":c.data_quality,
                "market_margin":c.market_margin,
                "draw_risk":c.draw_risk,
                "live_priority":c.live_priority,
                "live_readiness_score":c.live_readiness_score,
                "entry_home_score":0,
                "entry_away_score":0,
                "precision":precision,
            }
            params.append((c.match_id,c.selected_market,c.selected_probability,c.selected_index,c.confidence,odd,fair,ev,pre_model_version,calibration_version,dedupe,Jsonb(payload)))
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                before=0
                for param in params:
                    await cur.execute(sql,param)
                    if cur.rowcount and cur.rowcount>0:before+=cur.rowcount
            await conn.commit()
        return before

    async def fetch_recommendation_history(self, source: str, limit: int = 1000) -> list[dict[str,Any]]:
        sql="""
        select r.id,r.source,r.match_id,r.market,r.minute,r.probability,r.market_index,r.confidence,
               r.market_odd,r.fair_odd,r.ev_percent,r.status,r.pre_model_version,r.live_model_version,
               r.calibration_version,r.payload,r.created_at,
               m.match_date,m.kickoff,m.country,m.competition,m.home_team,m.away_team,
               a.result,a.profit_units,a.evaluated_at,a.payload as audit_payload
        from ac10_recommendations r
        join ac10_matches m on m.match_id=r.match_id
        left join ac10_audits a on a.recommendation_id=r.id
        where r.source=%s
        order by r.created_at desc
        limit %s
        """
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql,(source,int(limit)))
                return [dict(row) for row in await cur.fetchall()]

    async def insert_recommendations(self, analyses: Iterable[LiveAnalysis], *, live_model_version: str, pre_model_version: str, calibration_version: str) -> int:
        rows=[a for a in analyses if a.status=="RECOMENDAÇÃO"]
        if not rows:return 0
        sql="""
        insert into ac10_recommendations(match_id,source,market,minute,probability,market_index,confidence,market_odd,fair_odd,ev_percent,status,pre_model_version,live_model_version,calibration_version,dedupe_key,payload)
        values(%s,'LIVE',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict(dedupe_key) do nothing
        """
        params=[]
        for a in rows:
            dedupe=f"LIVE:{live_model_version}:{a.match_id}:{a.selected_market}:{a.home_score}-{a.away_score}:{a.minute//5}"
            params.append((a.match_id,a.selected_market,a.minute,a.selected_probability,a.market_index,a.market_quality,a.market_odd,a.fair_odd,a.ev_percent,a.status,pre_model_version,live_model_version,calibration_version,dedupe,Jsonb({**a.raw,"entry_home_score":a.home_score,"entry_away_score":a.away_score,"confirmation_count":a.confirmation_count,"chance_goal_10":a.chance_goal_10,"over15_more_probability":a.over15_more_probability,"market_quality":a.market_quality,"price_status":a.price_status})))
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql,params)
                count=cur.rowcount if cur.rowcount and cur.rowcount>0 else 0
            await conn.commit()
        return count

    async def claim_notification(self, dedupe_key: str, channel: str, payload: dict[str, Any]) -> bool:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("insert into ac10_notifications(dedupe_key,channel,status,attempts,payload) values(%s,%s,'PENDING',0,%s) on conflict do nothing returning dedupe_key",(dedupe_key,channel,Jsonb(payload)))
                row=await cur.fetchone()
            await conn.commit()
        return row is not None

    async def mark_notification(self, dedupe_key: str, *, sent: bool, error: str | None = None) -> None:
        async with self.pool.connection() as conn:
            await conn.execute("update ac10_notifications set status=%s,attempts=attempts+1,last_error=%s,sent_at=case when %s then now() else sent_at end where dedupe_key=%s",("SENT" if sent else "ERROR",error,sent,dedupe_key))
            await conn.commit()

    async def upsert_api_usage(self, provider: str, workflow: str, usage: dict[str,dict[str,int]]) -> None:
        requests=usage.get("requests",{}); errors=usage.get("errors",{}); latency=usage.get("latency_ms",{})
        rows=[(provider,ep,workflow,int(count),int(errors.get(ep,0)),int(latency.get(ep,0))) for ep,count in requests.items()]
        if not rows:return
        sql="""
        insert into ac10_api_usage(usage_date,provider,endpoint,workflow,request_count,error_count,latency_ms_sum,updated_at)
        values(current_date,%s,%s,%s,%s,%s,%s,now())
        on conflict(usage_date,provider,endpoint,workflow) do update set request_count=ac10_api_usage.request_count+excluded.request_count,error_count=ac10_api_usage.error_count+excluded.error_count,latency_ms_sum=ac10_api_usage.latency_ms_sum+excluded.latency_ms_sum,updated_at=now()
        """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur: await cur.executemany(sql,rows)
            await conn.commit()

    async def upsert_result(self, match_id: str, home: int, away: int, payload: dict[str,Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute("insert into ac10_results(match_id,final_home_score,final_away_score,finalized_at,provider_payload,updated_at) values(%s,%s,%s,now(),%s,now()) on conflict(match_id) do update set final_home_score=excluded.final_home_score,final_away_score=excluded.final_away_score,finalized_at=excluded.finalized_at,provider_payload=excluded.provider_payload,updated_at=now()",(match_id,home,away,Jsonb(payload)))
            await conn.commit()

    async def pending_audits(self, match_ids: list[str]) -> list[dict[str,Any]]:
        if not match_ids:return []
        sql="""
        select r.* from ac10_recommendations r left join ac10_audits a on a.recommendation_id=r.id
        where r.match_id=any(%s) and a.recommendation_id is null order by r.created_at
        """
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql,(match_ids,)); return [dict(x) for x in await cur.fetchall()]

    async def insert_audit(self, recommendation_id: str, result: str, profit_units: float, payload: dict[str,Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute("insert into ac10_audits(recommendation_id,result,profit_units,payload) values(%s,%s,%s,%s) on conflict(recommendation_id) do nothing",(recommendation_id,result,float(profit_units),Jsonb(json_safe(payload))))
            await conn.commit()
