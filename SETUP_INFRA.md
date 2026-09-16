# AC10 Next — Infra Check

1. Execute `000_reconcile_dev_schema.sql` no SQL Editor do Supabase.
2. Confirme que aparecem as 12 tabelas `ac10_*`.
3. Copie as pastas `.github` e `scripts` deste patch para a raiz do repositório.
4. Commit no GitHub.
5. Abra `Actions`.
6. Selecione **00 - Infra Check**.
7. Clique em **Run workflow**.

Resultado esperado:

- SUPABASE_DATABASE_URL configurado
- HIGHLIGHTLY_API_KEY configurado
- conexão PostgreSQL OK
- 12/12 tabelas encontradas
- escrita validada e revertida
- `AC10 Next: GitHub ↔ Supabase está pronto`
