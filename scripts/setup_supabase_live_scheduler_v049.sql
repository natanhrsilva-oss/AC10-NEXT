-- AC10 NEXT v0.4.9
-- Relogio primario do LIVE: Supabase Cron -> GitHub workflow_dispatch.
--
-- PRE-REQUISITOS (fazer no Dashboard antes de rodar este arquivo):
--   1) Habilitar as extensoes pg_cron e pg_net.
--   2) Criar no Vault um secret chamado exatamente: github_actions_token
--      contendo um Fine-grained PAT do GitHub limitado ao repo AC10-NEXT
--      com Repository permission: Actions = Read and write.
--
-- Este script NAO altera motor, probabilidades, planilhas ou tabelas de analise.

-- 1) Funcao de decisao/disparo.
-- Ela evita chamar o GitHub quando:
--   - estamos fora da janela 06:00-23:59 America/Sao_Paulo;
--   - ha LIVE RUNNING recente;
--   - ainda nao passaram 15 minutos desde o ultimo LIVE SUCCESS.
create or replace function public.ac10_dispatch_live_if_due()
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, vault, net
as $$
declare
    v_token text;
    v_last_success timestamptz;
    v_request_id bigint;
    v_local_hour integer;
    v_running boolean;
begin
    v_local_hour := extract(hour from timezone('America/Sao_Paulo', now()))::integer;

    -- Mesma janela operacional do LIVE atual.
    if v_local_hour < 6 or v_local_hour > 23 then
        return null;
    end if;

    -- Segunda protecao contra sobreposicao (alem do concurrency do GitHub).
    select exists (
        select 1
        from public.ac10_runs
        where run_type = 'LIVE'
          and status = 'RUNNING'
          and started_at > now() - interval '12 minutes'
    ) into v_running;

    if v_running then
        return null;
    end if;

    -- Usa started_at para ficar IDENTICO ao controlador Python v0.4.8+.
    select max(started_at)
      into v_last_success
      from public.ac10_runs
     where run_type = 'LIVE'
       and status = 'SUCCESS';

    if v_last_success is not null
       and v_last_success > now() - interval '15 minutes' then
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

    -- force=false e o ponto central: o GitHub NAO forca coleta.
    -- O workflow chama "ac10-next live --scheduled", que revalida os 15 min.
    select net.http_post(
        url := 'https://api.github.com/repos/natanhrsilva-oss/AC10-NEXT/actions/workflows/20-live.yml/dispatches',
        headers := jsonb_build_object(
            'Accept', 'application/vnd.github+json',
            'Authorization', 'Bearer ' || v_token,
            'X-GitHub-Api-Version', '2026-03-10',
            'User-Agent', 'AC10-Supabase-Cron',
            'Content-Type', 'application/json'
        ),
        body := jsonb_build_object(
            'ref', 'main',
            'inputs', jsonb_build_object(
                'force', false,
                'source', 'supabase'
            )
        ),
        timeout_milliseconds := 5000
    ) into v_request_id;

    return v_request_id;
end;
$$;

-- O cron roda como owner; usuarios da Data API nao precisam executar a funcao.
revoke all on function public.ac10_dispatch_live_if_due() from public, anon, authenticated;

-- 2) Job idempotente: remove somente o job AC10 de mesmo nome, se existir,
--    e cria novamente a verificacao a cada 5 minutos.
do $$
declare
    v_jobid bigint;
begin
    select jobid into v_jobid
      from cron.job
     where jobname = 'ac10-live-primary-heartbeat'
     limit 1;

    if v_jobid is not null then
        perform cron.unschedule(v_jobid);
    end if;
end $$;

select cron.schedule(
    'ac10-live-primary-heartbeat',
    '*/5 * * * *',
    $cron$ select public.ac10_dispatch_live_if_due(); $cron$
);

-- 3) Conferencia rapida. Deve retornar uma linha active=true.
select jobid, jobname, schedule, active
from cron.job
where jobname = 'ac10-live-primary-heartbeat';
