# AC10 Next v0.4.4 — Market Balance + Odds Fallback + Discord

## 1. Recomendações PRE equilibradas

A v0.4.3 corrigiu o Draw Risk, porém revelou uma diferença de escala entre mercados: BACK CASA frequentemente produz probabilidade/índice absolutos maiores que OVER 2,5 e BACK VISITANTE. Ordenar apenas por Precision fazia um mercado dominar o TOP 10.

A v0.4.4 mantém o filtro esportivo original e adiciona uma camada exclusiva de ranking:

- `Precision Score` absoluto continua sendo a base de qualidade.
- Cada candidato recebe `market_percentile`, comparando-o apenas com candidatos do mesmo mercado.
- `ranking_score = 70% Precision + 30% market_percentile`.
- O primeiro passe usa `PRE_RECOMMENDATION_MARKET_SOFT_CAP=4` por mercado.
- O cap é **suave**: se não houver alternativas qualificadas suficientes, um segundo passe completa as vagas com os melhores sinais restantes. Não há cota fixa 3/3/4 e nenhuma recomendação fraca é criada só para “equilibrar”.

Novos diagnósticos no log:

- `qualified_by_market`
- `offered_by_market`
- `market_soft_cap`
- `market_percentile`
- `ranking_score`

## 2. Odds Highlightly — fallback real

A rota atual do projeto (`sports.highlightly.net/football/odds`) é válida para a API All Sports da Highlightly. O problema observado foi `HTTP 200` com `data=[]` quando o filtro `bookmakerName=Bet365` era aplicado.

Novo fluxo:

1. Consulta o catálogo `/football/bookmakers` uma vez por execução para verificar a bookmaker configurada.
2. Se a bookmaker existir, tenta primeiro a consulta filtrada.
3. Se a consulta filtrada vier sem mercado principal utilizável, repete o mesmo `matchId` sem `bookmakerName`.
4. O parser agrupa por bookmaker e escolhe **uma única fonte** com melhor cobertura de `Full Time Result` e `Total Goals 2.5`.
5. Nunca mistura Home de uma bookmaker com Over de outra.
6. Se nenhuma bookmaker tiver preço para o jogo, segue normalmente sem odd/EV.

Configuração nova opcional:

```env
HIGHLIGHTLY_ODDS_FALLBACK_ANY_BOOKMAKER=true
```

A bookmaker preferida continua configurável:

```env
HIGHLIGHTLY_BOOKMAKER=Bet365
```

## 3. Discord PRE

Antes:

```text
✅ 1. Bolívar x Gualberto Villarroel SJ | 21:30
BACK CASA | Prob. 93.1% | Índice 94.1 | Precision 93.8 | Odd ND | EV ND
```

Agora:

```text
✅ 1. Bolívar x Gualberto Villarroel SJ | 21:30
(Bolivia - Liga) BACK CASA | Prob. 93.1% | Índice 94.1 | Precision 93.8
```

Se houver odd:

```text
(Bolivia - Liga) BACK CASA | Prob. 93.1% | Índice 94.1 | Precision 93.8 | Odd 1.72 | EV +6.4%
```

Sem preço, `Odd` e `EV` simplesmente não aparecem.

## Instalação

Não há migration SQL nem mudança de Apps Script nesta versão. Substitua os arquivos do FIX ou use o pacote FULL e rode:

1. `90 - Tests`
2. `10 - AC10 PRE`
3. confira no log `offered_by_market` e as linhas `Odds pré fallback`.

## Validação

- Python compile: OK
- Pytest: 32 testes passando
