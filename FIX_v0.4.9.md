# AC10 NEXT — FIX v0.4.9

## Objetivo

Tornar a automacao LIVE independente da pontualidade do scheduler do GitHub Actions.

## O que mudou

- Supabase Cron passa a ser o **relogio primario** do LIVE.
- GitHub `schedule` permanece como **backup**.
- `workflow_dispatch(force=false)` agora usa obrigatoriamente `ac10-next live --scheduled`.
- `workflow_dispatch(force=true)` continua sendo coleta manual imediata.
- Qualquer `LIVE SUCCESS`, inclusive manual, reinicia a janela de 15 minutos.
- Dupla protecao de concorrencia: `concurrency` no GitHub + `LIVE RUNNING` no Supabase.
- O Supabase checa o ultimo `LIVE SUCCESS` antes de disparar GitHub; portanto nao chama Highlightly a cada 5 minutos.
- O workflow exibe `event`, `source` e `force` no log para diagnostico.

## Arquivos alterados

- `.github/workflows/20-live.yml`
- `pyproject.toml` (versao 0.4.9)

## Arquivos adicionados

- `scripts/setup_supabase_live_scheduler_v049.sql`
- `FIX_v0.4.9.md`
- `CHANGED_v0.4.9.txt`
- `tests/test_live_scheduler_v049.py`

## Nao alterado

Motores PRE/LIVE, probabilidades, indices, filtros esportivos, Sheets, mensagens Discord e auditoria.

## Fluxo final

1. Supabase Cron acorda a cada 5 min.
2. Funcao SQL consulta `ac10_runs`.
3. Se `<15 min` desde ultimo LIVE SUCCESS: encerra sem chamar GitHub.
4. Se `>=15 min`: envia `workflow_dispatch(force=false, source=supabase)`.
5. GitHub executa `ac10-next live --scheduled` e revalida a janela.
6. Se devido, LIVE roda e grava SUCCESS.
7. Novo SUCCESS reinicia o relogio de 15 min.
8. GitHub cron continua como fallback.

## Instalacao

1. Subir os arquivos do FIX para `main`.
2. Rodar `90 - Tests`.
3. Criar Fine-grained PAT GitHub com Actions read/write somente para AC10-NEXT.
4. Guardar o PAT no Supabase Vault como `github_actions_token`.
5. Habilitar `pg_cron` e `pg_net` no Supabase.
6. Rodar `scripts/setup_supabase_live_scheduler_v049.sql` no SQL Editor.
7. Testar a funcao e conferir Actions.

Nunca grave o PAT no repositorio ou em SQL literal.
