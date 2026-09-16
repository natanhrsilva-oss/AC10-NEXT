# Mapa de migração dos motores — AC10LITE -> AC10 Next

## PRESERVAR como base

### Scanner Diário / Diário Pro
- `MatchFeatures` estruturais: ataque, defesa, peso, forma, qualidade, xG e ambiente de gols.
- Especialistas Back Casa, Back Visitante e Gols.
- Personas pré-game.
- Contextos de mercado.
- risco de empate.
- escolha pelo índice combinado especialista + contexto.
- margem para segundo mercado.
- confiança derivada de qualidade + índice + margem.

### LivePro2
- pressão por lado;
- activity score;
- necessity score condicionado à execução;
- personas histórico + recente;
- GPI;
- índice direcional/IDD;
- comparação com snapshot anterior;
- momentum cumulativo multi-snapshot;
- evolução e delta recente;
- Chance Gol 10 min;
- Over +1,5 gols adicionais;
- market data quality;
- confirmações;
- primeiro scan excepcional;
- BACK ONLY 38–65;
- odds apenas após formar candidato;
- deduplicação de recomendações.

## MELHORAR

### MatchFeatures
Trocar o dataclass gigante compartilhado por modelos separados:
- `TeamProfile`
- `PregameContext`
- `LiveObservation`
- `LiveDerivedMetrics`
- `Decision`

### GPI
Preservar pesos atuais como baseline Golden Master, depois permitir calibração por bucket de minuto e mercado.

### Momentum
Evoluir de média ponderada de movimentos para uma estrutura explícita com:
- nível;
- inclinação;
- aceleração;
- persistência;
- número de amostras.

### Chance Gol
Separar claramente:
- probabilidade temporal/base;
- ajuste por pressão;
- ajuste por aceleração;
- ajuste por contexto pré-game.

### Prioridade Diário
Converter A/B/C em `live_readiness_score` contínuo 0–100, mantendo A/B/C apenas como visualização.

### Persistência
Campos usados em filtros/ordenação viram colunas tipadas. JSONB fica para payload bruto, debug e compatibilidade.

### Saídas
Sheets e Discord recebem DTOs próprios; não conhecem objetos do domínio.

## DESCARTAR como motores independentes

- Live3
- LivePro antigo
- AOViVo como scanner separado
- múltiplas versões do Diário
- lógica de bootstrap/migration dentro do scan
- dependência operacional da planilha para calibração

As funções úteis desses motores migram para componentes internos versionados.

## TRAVAS QUE VIRAM INVARIANTES TESTADAS

1. Back nunca é recomendado para o time que já está vencendo quando a regra de mercado não permite.
2. 38–65 não libera GOL HT ou OVER +1 GOL.
3. Primeiro scan sem comparação não recomenda, exceto exceção explicitamente parametrizada.
4. Sem estatística live suficiente, não existe recomendação oficial.
5. Odds não participam da geração inicial do sinal esportivo.
6. Outputs externos nunca alteram o resultado esportivo.
7. Reprocessar o mesmo snapshot deve ser idempotente.
