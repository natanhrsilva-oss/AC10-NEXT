# AC10 Next v0.3.1

Nova geração do AC10, estruturada em **PRE → LIVE → AUDIT** e independente do AC10LITE.

## Estado atual

- **AC10 PRE**: coleta jogos, filtros estruturais, perfis recentes/históricos, especialistas pré-game e `pregame_context`.
- **AC10 LIVE**: usa o PRE persistido, coleta estatísticas de forma assíncrona, trabalha com Fast/Discovery Lane, snapshots incrementais e motor GPI/IDD/pressão/momentum.
- **Janelas**: 10–37 `GOL HT`; 38–65 **BACK ONLY**; 66–88 `OVER +1 GOL`, com gol direcional apenas quando há dominância clara.
- **Odds live**: consultadas somente para candidatos `RECOMENDAÇÃO`; BACK usa Full Time Result e `OVER +1 GOL` usa Total Goals no placar atual + 0,5. Mercados sem equivalente oficial ficam `SEM PREÇO LIVE`.
- **Price guard**: nunca recomenda odd disponível abaixo de 1,60; rejeita EV negativo e preços claramente inconsistentes.
- **AUDIT**: resultado final + auditoria de `GOL HT` por eventos; não inventa P/L de sinais sem odd.
- **Supabase**: fonte operacional de verdade. Sheets e Discord são saídas não bloqueantes.

## Secrets já usados

Obrigatórios:

```text
SUPABASE_DATABASE_URL
HIGHLIGHTLY_API_KEY
```

Discord:

```text
DISCORD_WEBHOOK_URL
```

Sheets (opcional):

```text
GOOGLE_SHEETS_WEBAPP_URL
GOOGLE_SHEETS_TOKEN
```

## GitHub Actions

- `00 - Infra Check` — diagnóstico manual.
- `10 - AC10 PRE` — 06:05, 10:05, 14:05 e 18:05 (São Paulo), além de manual.
- `20 - AC10 LIVE` — a cada 5 minutos na janela 06:00–23:59, com controle interno Fast/Discovery Lane.
- `30 - AC10 AUDIT` — diariamente, auditando por padrão o dia anterior.
- `40 - Health` — saúde da infraestrutura.
- `90 - Tests` — testes.

## Primeiro uso

1. Confirme o `00 - Infra Check` verde.
2. Rode manualmente `10 - AC10 PRE`.
3. Verifique `ac10_matches`, `ac10_team_profiles` e `ac10_pregame_context` no Supabase.
4. Rode `20 - AC10 LIVE` com `force=true` durante uma partida elegível.
5. Só depois conecte Google Sheets, se desejar. O Discord já funciona apenas com seu secret.

> A API de odds live da Highlightly depende de cobertura/plano. Se não estiver disponível, o motor continua funcionando e marca o candidato como `SEM PREÇO LIVE`. Defina `LIVE_REQUIRE_PRICE_FOR_RECOMMENDATION=true` se quiser bloquear recomendações sem odd.
