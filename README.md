# AC10 Next v0.4.1

Nova geração do AC10, estruturada em **PRE → LIVE → AUDIT**, com Supabase como fonte operacional de verdade.

## Ajuste v0.4.1

- PRE menos engessado: Precision Score continua seletivo, mas confiança/probabilidade/margem não eliminam isoladamente um bom jogo.
- PRE mantém odd mínima 1.60 e EV >= 0.
- LIVE não consulta nem exige odds por padrão: sinal esportivo aprovado vira RECOMENDAÇÃO.
- Log PRE inclui `pre_funnel` com motivos de rejeição e near misses.


## O que mudou na v0.4.1

### PRE de alta confiança

O PRE continua preparando **todos os jogos elegíveis** para o LIVE, mas recomenda ao usuário somente uma camada de alta precisão:

- `PRE Precision Score` separado do `Live Readiness`;
- no máximo **10 recomendações PRE**;
- pode enviar menos de 10 ou **nenhuma**;
- exige qualidade, confiança, índice, margem entre mercados, especialista aprovado, odd >= 1,60 e preço coerente;
- odds PRE são consultadas apenas para a shortlist de até 20 candidatos, reduzindo consumo;
- recomendações PRE são gravadas em `ac10_recommendations` e auditadas normalmente.

### LIVE: SINAL → PREÇO → RECOMENDAÇÃO

O motor esportivo agora produz `SINAL` quando os critérios estão completos. A entrada só vira `RECOMENDAÇÃO` depois de encontrar preço real aceitável:

```text
sinal esportivo + odd >= 1,60 + EV >= 0 + preço coerente = RECOMENDAÇÃO
```

Sem preço, fica `SINAL`; odd baixa/EV negativo bloqueiam a entrada.

### Pós-gol e mudança de estado

Quando o placar aumenta entre scans, o AC10 aplica cooldown na chance de outro gol:

- 0–2 min: fator 0,75 e bloqueio de novo sinal de gol;
- 3–5 min: fator 0,85;
- 6–8 min: fator 0,92;
- 9–10 min: fator 0,96;
- depois de 10 min: normal.

Cartão vermelho novo também cria uma curta janela de reconstrução do estado do jogo.

### Proteção contra dados estagnados

Se o minuto avança mas as principais estatísticas permanecem idênticas por scans sucessivos, a qualidade é reduzida. A partir do segundo scan estagnado, um novo `SINAL` é bloqueado até chegar dado fresco.

## Google Sheets

A planilha passa a ter quatro abas:

- `AC10 PRE` — panorama completo do dia;
- `AC10 LIVE` — estado atual;
- `HISTÓRICO PRE` — recomendações PRE, resultado e P/L;
- `HISTÓRICO LIVE` — recomendações LIVE, resultado e P/L.

No LIVE:

- linhas alternadas em azul claro / azul mais escuro;
- métricas >55 em verde;
- 45–55 em amarelo;
- <45 em vermelho;
- linha inteira verde somente quando `Status = RECOMENDAÇÃO`.

Os históricos fazem upsert pelo UUID da recomendação e o AUDIT atualiza `GREEN`, `RED` e P/L.

> Após atualizar `google-apps-script/Code.gs`, é obrigatório publicar uma **nova versão do Web App** no Apps Script. A URL pode permanecer a mesma.

## Janelas LIVE

- 10–37: `GOL HT` / gol direcional;
- 38–65: **BACK ONLY**;
- 66–88: `OVER +1 GOL`, com gol direcional apenas quando há dominância clara.

## GitHub Actions

- `00 - Infra Check`
- `10 - AC10 PRE`
- `20 - AC10 LIVE`
- `30 - AC10 AUDIT`
- `40 - Health`
- `90 - Tests`

## Ordem recomendada após instalar a v0.4.1

1. Atualize o repositório.
2. Atualize e redeploy o `google-apps-script/Code.gs`.
3. Rode `90 - Tests`.
4. Rode `10 - AC10 PRE` manualmente.
5. Aguarde pelo menos dois scans LIVE para reconstruir momentum na nova versão.
6. Rode `20 - AC10 LIVE` normalmente.

Não há migration SQL obrigatória nesta versão; as tabelas atuais já suportam os novos dados via `raw/payload` e `ac10_recommendations`.
