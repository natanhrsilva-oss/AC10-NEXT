# AC10 NEXT v0.4.5 — AUDIT Decimal serialization fix

## Problema corrigido

O workflow `30 - AUDIT` falhava ao gravar `ac10_audits.payload` quando uma recomendação tinha odd armazenada em coluna PostgreSQL `NUMERIC`. O psycopg retorna esse valor como `Decimal`, e o serializer JSON usado por `Jsonb` não serializa `Decimal` diretamente.

Erro observado:

```text
TypeError: Object of type Decimal is not JSON serializable
```

## Correções

- `evaluate_recommendation()` converte `market_odd` para `float | None` antes de montar o detalhe da auditoria.
- `_profit()` sempre retorna `float`, inclusive quando a odd veio do PostgreSQL como `Decimal`.
- `Database.insert_audit()` aplica `json_safe()` ao payload antes do `Jsonb`, criando uma segunda barreira de segurança.
- `json_safe()` converte recursivamente `Decimal`, datas/datetimes, UUIDs, listas, tuplas, sets e dicionários para tipos JSON compatíveis.
- Foram adicionados testes de regressão específicos para odds `Decimal`.

## Importante

Não há migration SQL e não há alteração no Apps Script. As versões dos motores PRE/LIVE/CAL permanecem `0.4.4`, pois este fix não muda cálculo, seleção ou calibração; muda apenas a serialização do AUDIT.

Após subir o fix, rode novamente o workflow `30 - AUDIT`. Auditorias já gravadas continuam intactas; recomendações ainda sem auditoria serão processadas normalmente.
