# AC10 NEXT v0.4.10 — canal LIVE ALERTAS

Escopo isolado de saída/Discord. Nenhuma regra de motor, probabilidade, índice, planilha, auditoria ou scheduler foi alterada.

## Novo canal

Crie um webhook para um canal dedicado e salve no GitHub Actions Secret:

`DISCORD_WEBHOOK_LIVE_ALERTS`

O canal recebe somente jogos que satisfaçam ao menos uma condição:

- status `RECOMENDAÇÃO`, independentemente do índice; ou
- `Índice >= 60`, mesmo sem status de recomendação.

## Ícones

- `✅ RECOMENDAÇÃO` = recomendação do motor AC10.
- `🔥 ÍNDICE ALTO` = jogo ainda não recomendado, mas com índice >= 60.

Se um jogo já estava como `🔥 ÍNDICE ALTO` e depois vira `✅ RECOMENDAÇÃO`, uma nova notificação é enviada.

## Anti-spam

O canal não repete a mesma oportunidade a cada ciclo por pequenas oscilações de minuto/métrica. Uma nova mensagem é liberada quando muda o conjunto de alertas, categoria (alto índice -> recomendação), mercado ou placar. Quando não há mais alertas, o estado vazio é salvo silenciosamente, permitindo alertar novamente se o jogo voltar à zona forte.

## Configuração opcional

- `LIVE_ALERTS_MIN_INDEX=60`
- `LIVE_ALERTS_LIMIT=8`
- `LIVE_ALERTS_DISCORD_ENABLED=true`

## Instalação

1. Sobrescreva os arquivos do FIX no repositório.
2. Crie `DISCORD_WEBHOOK_LIVE_ALERTS` em GitHub > Settings > Secrets and variables > Actions.
3. Rode `90 - Tests`.
4. Rode um LIVE manual para testar o novo canal, ou aguarde o próximo ciclo automático.

Sem migration de banco e sem mudança no Supabase Cron.
