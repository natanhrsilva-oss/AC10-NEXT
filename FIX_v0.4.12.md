# AC10 NEXT — FIX v0.4.12

## Correção do AUDIT — ForeignKeyViolation em `ac10_results`

### Causa real
O AUDIT consultava a Highlightly para vários dias e montava a lista de **todos** os jogos finalizados retornados pelo provedor.

Em seguida, antes de verificar se havia uma recomendação AC10 para aquele jogo, executava:

`db.upsert_result(match_id, ...)`

A tabela `ac10_results` possui FK para `ac10_matches`. Portanto, qualquer partida retornada pela Highlightly que nunca tivesse sido gravada/analisada pelo AC10 podia derrubar a auditoria inteira com:

`ForeignKeyViolation: Key (match_id) is not present in table ac10_matches`

### Correção
O AUDIT agora:

1. coleta os jogos finalizados;
2. consulta quais deles possuem recomendações AC10 pendentes;
3. filtra somente esses jogos;
4. grava resultado e audita apenas os jogos realmente relevantes.

Isso elimina a gravação de milhares de resultados que não pertencem ao AC10 e impede a falha por partidas externas.

### Proteções mantidas
- PRE não alterado;
- LIVE não alterado;
- probabilidades e motores não alterados;
- planilhas não alteradas;
- scheduler não alterado;
- Discord não alterado;
- regra da auditoria semanal continua igual.

### Observabilidade
Foram adicionadas às métricas:
- `finished`: todos os finalizados vistos no provedor;
- `finished_relevant`: finalizados que realmente tinham recomendação AC10 pendente;
- `pending_recommendations`: recomendações pendentes encontradas.

### Depois de instalar
Rode manualmente `30 - AC10 AUDIT WEEKLY`. A auditoria pode ser reexecutada com segurança porque `ac10_results` e `ac10_audits` usam upsert.
