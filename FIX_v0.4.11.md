# AC10 NEXT — FIX v0.4.11

## PRE automático às 03:00 via Supabase

Este fix troca o relógio primário do PRE para o Supabase Cron, seguindo a mesma arquitetura já usada no LIVE.

### Fluxo
Supabase Cron (03:00 BRT) → verifica `ac10_runs` → se não existe `PRE SUCCESS` para o dia → dispara `10-pre.yml` → workflow executa `ac10-next pre --if-missing`.

O Supabase faz heartbeats às 03:00, 03:05, 03:10, 03:15, 03:20, 03:25 e 03:30. Assim, se um disparo isolado falhar, o próximo tenta novamente. Se o PRE já estiver `RUNNING` ou já tiver `SUCCESS`, nada é disparado.

### GitHub
O `10-pre.yml` agora aceita `source=supabase`. Disparos vindos do Supabase usam `--if-missing`. Execução manual continua igual: manual sem data executa normalmente; manual com data executa a data informada.

O scheduler nativo do GitHub permanece apenas como backup às 03:15 e 03:30 de Brasília.

### Não alterado
Motor PRE, probabilidades, filtros, recomendações, planilhas, LIVE, auditoria, Supabase LIVE e Discord permanecem com a lógica existente.

### Instalação
1. Suba os arquivos deste fix para o repositório.
2. No Supabase SQL Editor, execute `scripts/setup_supabase_pre_scheduler_v0411.sql`.
3. Não é necessário criar novo token: o script reutiliza o Vault secret `github_actions_token`.
4. Confira `cron.job` para `ac10-pre-primary-heartbeat` com `active=true`.
