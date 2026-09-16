# Roadmap de implementação

## Fase 0 — Golden Master
- Congelar AC10LITE-main (33) como referência.
- Criar fixtures representativas de PRE e LIVE.
- Registrar saídas: probabilidades, índices, personas, GPI, IDD, momentum, mercado e status.

## Fase 1 — Fundação
- Novo repositório.
- Novo Supabase.
- migrations.
- settings.
- async HTTP.
- async DB pool.
- observabilidade.

## Fase 2 — AC10 PRE
- catálogo de partidas.
- team profiles.
- especialistas.
- meta-motor.
- pregame_context.
- live_readiness_score.

## Fase 3 — AC10 LIVE baseline
- discovery.
- estatísticas concorrentes.
- snapshots.
- Pressure/Activity/Necessity.
- GPI/IDD/Momentum.
- Golden Master contra LivePro2.

## Fase 4 — Otimização operacional
- lanes.
- odds lazy.
- bulk writes.
- output queue/retry.
- deduplicação persistente.

## Fase 5 — AUDIT
- resultados.
- ROI/unidades.
- buckets.
- proposta de calibração versionada.

## Fase 6 — Melhorias Next
Somente após equivalência com o AC10LITE:
- Momentum 2.0.
- live readiness refinado.
- potencial explosivo.
- calibração por liga/minuto quando houver amostra suficiente.
