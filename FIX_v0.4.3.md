# AC10 Next v0.4.3 — Draw Risk + Odds diagnostics

- Corrige a fórmula de Draw Risk que estava inflada (pesos somavam 200%).
- Sem odds 1X2, usa prior neutro de 28% em vez de 50%.
- Draw Risk deixa de ser veto absoluto para BACK; vira penalidade leve e progressiva no Precision Score.
- Alerta de draw risk passa a ser soft flag a partir de 58.
- Odds continuam 100% opcionais no PRE e LIVE.
- Parser de odds aceita aliases adicionais e payloads sem campo `type`.
- Quando Highlightly responde sem odd utilizável, o log mostra mercados, bookmakers e tier/plano retornados, sem expor credenciais.
