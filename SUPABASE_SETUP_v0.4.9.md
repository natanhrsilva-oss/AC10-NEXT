# AC10 NEXT v0.4.9 — passo a passo Supabase Cron

Este setup cria um segundo relógio independente para o LIVE. O Supabase verifica a cada 5 minutos se já passaram pelo menos 15 minutos desde o último `LIVE SUCCESS`. Só quando estiver vencido ele dispara o workflow `20-live.yml` no GitHub.

## 0. Antes de começar

Suba primeiro o FIX v0.4.9 para a branch `main` e rode o workflow `90 - Tests`.

Não cole o token do GitHub em chat, arquivo, commit ou print público.

## 1. Criar um Fine-grained Personal Access Token no GitHub

No GitHub:

1. Clique na sua foto de perfil.
2. Abra **Settings**.
3. Vá em **Developer settings**.
4. Abra **Personal access tokens** > **Fine-grained tokens**.
5. Clique em **Generate new token**.
6. Nome sugerido: `AC10 Supabase Scheduler`.
7. Em **Repository access**, escolha **Only select repositories** e marque apenas `AC10-NEXT`.
8. Em **Repository permissions**, defina **Actions = Read and write**.
9. Gere o token e copie-o uma única vez.

O endpoint `workflow_dispatch` exige permissão Actions (write) para Fine-grained PAT.

## 2. Habilitar extensões no Supabase

No projeto do AC10 no Supabase:

1. Vá em **Database** > **Extensions**.
2. Procure e habilite `pg_cron`.
3. Procure e habilite `pg_net`.

O `pg_cron` executa o relógio e o `pg_net` faz o POST HTTPS para a API do GitHub.

## 3. Guardar o token no Vault

No Supabase, abra **Vault** e crie um secret:

- Name: `github_actions_token`
- Secret: cole o Fine-grained PAT criado no GitHub
- Description (opcional): `AC10 LIVE GitHub workflow dispatcher`

Se preferir SQL, use o SQL Editor e substitua SOMENTE o texto `COLE_O_TOKEN_AQUI` localmente:

```sql
select vault.create_secret(
  'COLE_O_TOKEN_AQUI',
  'github_actions_token',
  'AC10 LIVE GitHub workflow dispatcher'
);
```

Depois apague o token do histórico/editor se ele tiver ficado exposto. A opção pelo Vault UI é preferível.

### Conferir sem revelar o token

```sql
select name, created_at, updated_at
from vault.decrypted_secrets
where name = 'github_actions_token';
```

Deve retornar uma linha. Não faça `select *` em prints porque a view também possui a coluna descriptografada.

## 4. Instalar o scheduler AC10

Abra **SQL Editor** no Supabase.

Copie TODO o conteúdo de:

`scripts/setup_supabase_live_scheduler_v049.sql`

Cole no SQL Editor e clique em **Run**.

No final, a consulta deve retornar uma linha parecida com:

- `jobname = ac10-live-primary-heartbeat`
- `schedule = */5 * * * *`
- `active = true`

## 5. Conferir se o job existe

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'ac10-live-primary-heartbeat';
```

O esperado é `active = true`.

## 6. Conferir se o Supabase está acordando a cada 5 minutos

Depois de 5 a 10 minutos:

```sql
select
  jobid,
  runid,
  status,
  return_message,
  start_time,
  end_time
from cron.job_run_details
where jobid = (
  select jobid
  from cron.job
  where jobname = 'ac10-live-primary-heartbeat'
  limit 1
)
order by start_time desc
limit 10;
```

O normal é aparecer `status = succeeded` mesmo quando nenhum GitHub run é disparado. Isso significa que o heartbeat executou e decidiu que ainda não estava na hora.

## 7. Testar a função manualmente

```sql
select public.ac10_dispatch_live_if_due();
```

Possíveis resultados:

- `NULL`: ainda não passaram 15 minutos, existe LIVE RUNNING ou estamos fora da janela 06h-23h.
- Um número (request id): o Supabase colocou uma requisição HTTP para o GitHub na fila.

`pg_net` é assíncrono; o número retornado significa que a solicitação foi enfileirada, não que o GitHub já respondeu.

## 8. Conferir a resposta HTTP ao GitHub

Após um disparo que retornou request id:

```sql
select
  id,
  status_code,
  error_msg,
  created
from net._http_response
order by created desc
limit 10;
```

Uma resposta 2xx indica que a API do GitHub aceitou a chamada. Se houver `401`, revise o token. Se houver `403`, revise a permissão `Actions: Read and write` e o acesso ao repositório. Se houver `404`, confira owner/repo/workflow.

## 9. Conferir no GitHub

Abra:

**Actions > 20 - AC10 LIVE**

Os disparos do Supabase ficam fáceis de identificar pelo nome do run:

`LIVE | workflow_dispatch | supabase`

No log, a etapa **Show trigger** deve mostrar:

```text
event=workflow_dispatch
source=supabase
force=false
```

E a etapa seguinte deve usar o controlador `--scheduled`, nunca `--force`.

## 10. Como o relógio se comporta

Exemplo: LIVE manual começa e termina com sucesso por volta de 16:43.

- 16:45: Supabase acorda; <15 min -> não dispara.
- 16:50: <15 min -> não dispara.
- 16:55: <15 min -> não dispara.
- 17:00: >=15 min -> dispara GitHub.
- GitHub revalida os 15 min.
- LIVE executa e grava novo `SUCCESS`.
- O relógio reinicia.

Se o LIVE falhar, não existe novo `SUCCESS`; no próximo heartbeat elegível o Supabase tenta novamente.

## 11. Consultar o último LIVE SUCCESS

```sql
select id, started_at, finished_at, status, parameters, metrics
from public.ac10_runs
where run_type = 'LIVE'
  and status = 'SUCCESS'
order by started_at desc
limit 5;
```

## 12. Desativar o scheduler do Supabase, se necessário

```sql
select cron.unschedule('ac10-live-primary-heartbeat');
```

Isso para somente o relógio do Supabase. O schedule de backup do GitHub continua no repositório.

## 13. Reativar

Rode novamente o arquivo:

`scripts/setup_supabase_live_scheduler_v049.sql`

Ele remove um job AC10 antigo de mesmo nome e recria o scheduler ativo.
