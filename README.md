# AC10 Next

Blueprint técnico da nova geração do AC10, redesenhada a partir do AC10LITE-main (33).

## Objetivo

Separar completamente **contexto pré-jogo** de **estado ao vivo**:

1. `AC10 PRE` prepara e persiste o contexto de cada partida.
2. `AC10 LIVE` carrega o contexto pronto e coleta somente o estado live.
3. `AC10 AUDIT` mede resultados e produz propostas versionadas de calibração.

O Supabase é a fonte de verdade operacional. Google Sheets é painel. Discord é notificação. Nenhuma saída externa bloqueia o motor.

## Princípios

- Uma única implementação oficial de PRE, LIVE e AUDIT.
- Coleta HTTP assíncrona com concorrência limitada.
- Histórico/formas nunca são reconstruídos durante o fluxo Live normal.
- Odds apenas para candidatos finais.
- Bulk upsert e pool de conexões.
- Snapshots temporais compactos e deduplicados.
- Fórmulas esportivas versionadas e testadas por Golden Master contra o AC10LITE.
- Configuração de thresholds fora do código.
- Observabilidade de tempo, requests, cache hit, erros e qualidade de dados.

Leia `docs/ARCHITECTURE.md` e `docs/MOTOR_MAP.md` antes da implementação.
