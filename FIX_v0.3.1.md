# AC10 Next — Fix v0.3.1

## O que entra neste fix

- Repositório completo PRE → LIVE → AUDIT.
- GitHub Actions: Infra, PRE, LIVE, AUDIT, Health e Tests.
- AC10 PRE persistindo o contrato pré-game no Supabase.
- AC10 LIVE assíncrono com Fast Lane / Discovery Lane.
- Janela 38–65 estritamente BACK ONLY.
- Janela 66–88 usando `OVER +1 GOL` como mercado-base; gol direcional só quando o motor encontra dominância clara.
- Odds live consultadas somente para candidatos finais `RECOMENDAÇÃO`.
- Price guard: odd mínima 1,60, EV negativo, preço incoerente e limite de EV absurdo.
- Parser de `Total Goals 2.5` corrigido quando a linha vem embutida no nome do mercado.
- Auditoria de `GOL HT` via eventos da Highlightly.
- P/L não é inventado quando uma recomendação não possui odd conhecida.
- Conversão de `Decimal` (PostgreSQL NUMERIC) para `float` na fronteira banco → domínio.
- Discord com entrada analisada, placar, índice, PRE e preço/EV quando disponível.
- Sheets opcional, sem bloquear o motor.

## Banco

Nenhuma migration nova é necessária se o `00 - Infra Check` já ficou verde com as 12 tabelas `ac10_*`.

## Como publicar

1. Substitua o conteúdo do repositório pelo conteúdo deste pacote, preservando seus GitHub Secrets.
2. Commit/push na `main`.
3. O workflow `90 - Tests` deve ficar verde.
4. Rode manualmente `10 - AC10 PRE`.
5. Verifique dados em `ac10_matches`, `ac10_team_profiles` e `ac10_pregame_context`.
6. Durante um jogo elegível, rode `20 - AC10 LIVE` com `force=true` para o primeiro teste.

## Secrets

Já existentes:

- `SUPABASE_DATABASE_URL`
- `HIGHLIGHTLY_API_KEY`
- `DISCORD_WEBHOOK_URL`

Opcionais para Sheets:

- `GOOGLE_SHEETS_WEBAPP_URL`
- `GOOGLE_SHEETS_TOKEN`

## Odds live

A falta de odds live não derruba o scanner. Por padrão o sinal esportivo continua e recebe `SEM PREÇO LIVE`.

Para exigir odd antes de qualquer recomendação, adicione o secret/variable de ambiente:

`LIVE_REQUIRE_PRICE_FOR_RECOMMENDATION=true`
