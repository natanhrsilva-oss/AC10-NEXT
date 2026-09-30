# AC10 NEXT — Fix v0.4.8 (LIVE rolling automation)

Este fix altera **somente a automação/controle de execução do LIVE**. Não muda motor PRE, motor LIVE, probabilidades, filtros esportivos, planilhas, mercados ou fórmulas.

## O que mudou

### LIVE sem slots fixos

O LIVE não depende mais de `XX:00 / XX:15 / XX:30 / XX:45`.

O workflow do GitHub funciona como um **heartbeat** aproximadamente a cada 5 minutos. Em cada heartbeat, o código consulta primeiro o Supabase:

1. existe um LIVE `RUNNING` recente? → encerra;
2. qual foi o último LIVE `SUCCESS` (manual ou automático)?
3. passaram menos de 15 minutos desde o início dele? → encerra sem Highlightly;
4. passaram 15 minutos ou mais? → executa um novo LIVE;
5. se a execução falhar, ela não reinicia o relógio; o próximo heartbeat tenta novamente.

### Execução manual reinicia o relógio

Exemplo:

- 12:07 → LIVE manual `SUCCESS`;
- heartbeats seguintes apenas consultam o Supabase;
- o primeiro heartbeat que encontrar `>=15 min` dispara o próximo LIVE;
- a partir desse novo `SUCCESS`, começa outro intervalo de 15 minutos.

Como o GitHub Actions trabalha com cron de no mínimo 5 minutos e pode iniciar jobs com atraso, a execução automática ocorre **no primeiro heartbeat disponível depois dos 15 minutos**, não há garantia de segundo/minuto exato.

### Cron deslocado

O heartbeat foi deslocado dos minutos `00/05/10/...` para:

`02/07/12/17/22/27/32/37/42/47/52/57`

Isso reduz a dependência dos minutos mais congestionados do scheduler do GitHub, especialmente `XX:00`. O workflow usa `timezone: America/Sao_Paulo`, evitando conversões manuais para UTC.

### Segurança

- `concurrency: ac10-live` continua impedindo sobreposição no GitHub.
- O Supabase também bloqueia quando encontra LIVE `RUNNING` recente.
- `RUNNING` antigo não bloqueia indefinidamente; após 12 minutos é tratado como stale.
- Nenhuma chamada à Highlightly é feita nos heartbeats em que ainda não completaram 15 minutos.
- A auditoria semanal passa a chamar a métrica operacional de **ciclos LIVE**; recuperação tardia significa que o controlador só conseguiu executar com >=20 min desde o último sucesso.
- Nenhuma migration é necessária.
- Nenhum secret novo é necessário.

## Arquivos alterados

- `.github/workflows/20-live.yml`
- `README.md`
- `src/ac10next/pipelines/live.py`
- `src/ac10next/repositories/database.py`
- `src/ac10next/cli.py`
- `src/ac10next/utils.py`
- `src/ac10next/outputs/discord.py`
- `src/ac10next/__init__.py`
- `pyproject.toml`
- `tests/test_live_scheduler_v048.py`
- `tests/test_discord.py`

## Instalação

Substitua os arquivos do FIX no repositório e faça commit na branch `main`. Depois rode `90 - Tests` e faça uma execução manual do `20 - AC10 LIVE`. Essa execução manual passa a ser o marco inicial do relógio de 15 minutos.
