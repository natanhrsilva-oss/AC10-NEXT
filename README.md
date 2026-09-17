# AC10 Next v0.4.4

Nova geração do AC10 estruturada em **PRE → LIVE → AUDIT**, com Supabase como fonte operacional de verdade, Google Sheets como visualização e Discord como canal de alerta.

## v0.4.4

Esta versão corrige três pontos do PRE:

- **equilíbrio de mercados**: o TOP 10 não é mais ordenado apenas pela escala absoluta de Precision; usa também posição relativa dentro do próprio mercado e um cap suave de 4 recomendações por mercado;
- **odds resilientes**: Bet365 continua preferida, mas se a Highlightly não devolver preço para ela o robô tenta o mesmo jogo sem filtro de bookmaker e escolhe uma única bookmaker com melhor cobertura;
- **Discord PRE**: passa a mostrar `(PAÍS - LIGA) MERCADO` e só inclui Odd/EV quando realmente existem.

Não existe cota fixa por mercado. O cap é suave: se não houver mercados alternativos qualificados, as vagas restantes voltam para os sinais esportivos mais fortes.

## PRE

O PRE prepara todos os jogos elegíveis para servir de contexto ao LIVE, mas recomenda no máximo 10 entradas ao usuário.

A recomendação é decidida pela leitura esportiva e pelo `Precision Score`. Odds são **informativas**, não são requisito para aprovar ou reprovar uma entrada. Quando existem, são armazenadas e o EV é calculado; quando não existem, o fluxo segue normalmente.

O funil de log inclui:

- `qualified_before_limit`
- `qualified_by_market`
- `offered_by_market`
- `market_soft_cap`
- `market_percentile`
- `ranking_score`
- `near_misses`

## Odds Highlightly

Fluxo PRE da v0.4.4:

1. Verifica uma vez por execução se `HIGHLIGHTLY_BOOKMAKER` existe no catálogo da Highlightly.
2. Tenta a bookmaker preferida quando disponível.
3. Se não vier `Full Time Result` ou `Total Goals` utilizável, repete a consulta do mesmo `matchId` sem `bookmakerName`.
4. Escolhe uma única bookmaker com melhor cobertura dos mercados suportados.
5. Nunca mistura preços de bookmakers diferentes na mesma leitura.
6. Se nenhuma odd existir, segue sem preço.

Configuração:

```env
HIGHLIGHTLY_BOOKMAKER=Bet365
HIGHLIGHTLY_ODDS_FALLBACK_ANY_BOOKMAKER=true
```

## LIVE

Por padrão o LIVE decide exclusivamente por dados esportivos:

```env
LIVE_REQUIRE_PRICE_FOR_RECOMMENDATION=false
```

Portanto odd/EV não bloqueiam recomendação LIVE.

Janelas principais:

- 10–37: `GOL HT` / gol direcional;
- 38–65: BACK;
- 66–88: `OVER +1 GOL`, com direcional quando houver dominância clara.

O motor também preserva cooldown pós-gol, tratamento de cartão vermelho, proteção contra dados estagnados, momentum, GPI, IDD, pressão recente, chance de gol em 10 minutos e probabilidade de +1,5 gols.

## Discord PRE

Exemplo sem odd:

```text
✅ 1. Bolívar x Gualberto Villarroel SJ | 21:30
(Bolivia - División Profesional) BACK CASA | Prob. 93.1% | Índice 94.1 | Precision 93.8
```

Exemplo com odd:

```text
✅ 1. Bolívar x Gualberto Villarroel SJ | 21:30
(Bolivia - División Profesional) BACK CASA | Prob. 93.1% | Índice 94.1 | Precision 93.8 | Odd 1.72 | EV +6.4%
```

## Google Sheets

Abas operacionais:

- `AC10 PRE`
- `AC10 LIVE`
- `HISTÓRICO PRE`
- `HISTÓRICO LIVE`

No LIVE, as métricas usam a regra visual já definida: >55 verde, 45–55 amarelo, <45 vermelho; a linha inteira fica verde somente em `RECOMENDAÇÃO`.

## GitHub Actions

- `00 - Infra Check`
- `10 - AC10 PRE`
- `20 - AC10 LIVE`
- `30 - AC10 AUDIT`
- `40 - Health`
- `90 - Tests`

## Instalação do v0.4.4

Não há migration SQL nem alteração obrigatória no Apps Script nesta versão.

Ordem recomendada:

1. Suba os arquivos do FIX ou substitua pelo pacote FULL.
2. Rode `90 - Tests`.
3. Rode `10 - AC10 PRE`.
4. Confira no log `offered_by_market` e, para odds, `Highlightly bookmaker` / `Odds pré fallback`.
5. Rode o LIVE normalmente.

## Versões

- PRE: `AC10-NEXT-PRE-0.4.4`
- LIVE: `AC10-NEXT-LIVE-0.4.4`
- Calibration: `AC10-NEXT-CAL-0.4.4`
- pacote Python: `0.4.4`
