-- AC10 NEXT v0.4.11
-- Relógio primário do PRE: Supabase Cron -> GitHub workflow_dispatch.
--
-- Objetivo:
--   - tentar o PRE a partir das 03:00 America/Sao_Paulo;
--   - repetir o heartbeat a cada 5 min até 03:30 SOMENTE enquanto o PRE do dia
--     ainda não tiver SUCCESS;
--   - evitar sobreposição se já houver PRE RUNNING;
--   - usar o mesmo github_actions_token do scheduler LIVE v0.4.9.
--
-- Este script NÃO altera motor PRE, probabilidades, filtros, planilhas, LIVE ou auditoria.
--
-- PRÉ-REQUISITOS (já devem existir se o LIVE Supabase está funcionando):
--   1) pg_cron habilitado
--   2) pg_net habilitado
--   3) Vault secret: github_actions_token
--      PAT fine-grained limitado ao repo AC10-NEXT com Actions: Read and write.

create or replace function public.ac10_dispatch_pre_if_missing()
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, vault, net
as $$
declare
    v_token text;
    v_target_date date;
    v_local_hour integer;
    v_local_minute integer;
    v_has_success boolean;
    v_running boolean;
    v_request_id bigint;
begin
    -- Data/hora operacional sempre em Brasília.
    v_target_date := timezone('America/Sao_Paulo', now())::date;
    v_local_hour := extract(hour from timezone('America/Sao_Paulo', now()))::integer;
    v_local_minute := extract(minute from timezone('America/Sao_Paulo', now()))::integer;

    -- Segurança adicional: esta função só dispara na janela 03:00-03:30 BRT.
    if v_local_hour <> 3 or v_local_minute > 30 then
        return null;
    end if;

    -- Se o PRE do dia já concluiu, encerra sem chamar o GitHub.
    select exists (
        select 1
        from public.ac10_runs
        where run_type = 'PRE'
          and status = 'SUCCESS'
          and parameters->>'date' = v_target_date::text
    ) into v_has_success;

    if v_has_success then
        return null;
    end if;

    -- Evita dois PREs simultâneos enquanto um workflow anterior ainda trabalha.
    select exists (
        select 1
        from public.ac10_runs
        where run_type = 'PRE'
          and status = 'RUNNING'
          and parameters->>'date' = v_target_date::text
          and started_at > now() - interval '30 minutes'
    ) into v_running;

    if v_running then
        return null;
    end if;

    select decrypted_secret
      into v_token
      from vault.decrypted_secrets
     where name = 'github_actions_token'
     limit 1;

    if coalesce(v_token, '') = '' then
        raise exception 'Vault secret github_actions_token nao encontrado';
    end if;

    select net.http_post(
        url := 'https://api.github.com/repos/natanhrsilva-oss/AC10-NEXT/actions/workflows/10-pre.yml/dispatches',
        headers := jsonb_build_object(
            'Accept', 'application/vnd.github+json',
            'Authorization', 'Bearer ' || v_token,
            'X-GitHub-Api-Version', '2022-11-28',
            'User-Agent', 'AC10-Supabase-Cron',
            'Content-Type', 'application/json'
        ),
        body := jsonb_build_object(
            'ref', 'main',
            'inputs', jsonb_build_object(
                'source', 'supabase'
            )
        ),
        timeout_milliseconds := 5000
    ) into v_request_id;

    return v_request_id;
end;
$$;

revoke all on function public.ac10_dispatch_pre_if_missing() from public, anon, authenticated;

-- Idempotente: recria apenas o job PRE deste fix.
do $$
declare
    v_jobid bigint;
begin
    select jobid into v_jobid
      from cron.job
     where jobname = 'ac10-pre-primary-heartbeat'
     limit 1;

    if v_jobid is not null then
        perform cron.unschedule(v_jobid);
    end if;
end $$;

-- pg_cron usa UTC.
-- 06:00-06:30 UTC = 03:00-03:30 em Brasília (UTC-3).
-- O heartbeat de 5 min permite recuperação automática se um disparo falhar.
select cron.schedule(
    'ac10-pre-primary-heartbeat',
    '0,5,10,15,20,25,30 6 * * *',
    $cron$ select public.ac10_dispatch_pre_if_missing(); $cron$
);

-- Conferência rápida: deve retornar uma linha active=true.
select jobid, jobname, schedule, active, command
from cron.job
where jobname = 'ac10-pre-primary-heartbeat';
