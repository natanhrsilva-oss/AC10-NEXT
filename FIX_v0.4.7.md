# AC10 NEXT — Fix v0.4.7 (Automação, Watchdog, Discord e Audit semanal)

Este fix altera **somente automação/observabilidade/Discord/Audit**. Não muda motores PRE/LIVE, fórmulas, probabilidades, filtros esportivos nem layout das planilhas.

## 1. PRE — uma única execução automática por dia

- 06:00 Brasília: tentativa principal.
- 06:30: watchdog 1.
- 07:00: watchdog 2.
- As três execuções automáticas usam `ac10-next pre --if-missing`.
- Se já existir `PRE / SUCCESS` para a data no `ac10_runs`, o job encerra antes de consultar a Highlightly.
- Portanto, depois de um PRE automático bem-sucedido, ele **não roda novamente automaticamente naquele dia**.
- `workflow_dispatch` continua disponível para execução manual intencional.

## 2. LIVE — slots de 15 min + watchdog de 5 min

O GitHub acorda a cada 5 minutos dentro da janela 06h–23h59, mas o código trabalha com slots oficiais:

- `XX:00`
- `XX:15`
- `XX:30`
- `XX:45`

Cada despertar consulta primeiro o Supabase. Se o slot atual já estiver `SUCCESS` ou estiver `RUNNING` recentemente, encerra sem chamar a Highlightly. Se estiver ausente, com erro ou travado por mais de 12 minutos, recupera o slot.

Cada execução registra em `ac10_runs.parameters`:

- `slot`
- `delay_minutes`
- `date`

Isso permite medir disponibilidade e recuperações do watchdog.

## 3. Discord separado

Novas variáveis/secrets:

```env
DISCORD_WEBHOOK_PRE=
DISCORD_WEBHOOK_LIVE=
```

- `DISCORD_WEBHOOK_PRE`: PRE + AUDITORIA semanal.
- `DISCORD_WEBHOOK_LIVE`: LIVE.
- `DISCORD_WEBHOOK_URL` continua funcionando como fallback para compatibilidade.

Para realmente separar os canais, crie o novo canal/webhook no Discord e adicione os dois secrets acima no GitHub.

## 4. LIVE — nova mensagem operacional

A mensagem passa a começar por um panorama:

```text
⚡ AC10 LIVE — 14:30
📡 55 jogos com dados
🎯 Índice ≥55: 8 | ✅ Entradas: 2 | 👀 Observar: 6
🏠 Back Casa ≥55: 3 | ✈️ Back Visitante ≥55: 1 | ⚽ Gols ≥55: 4
📈 Prob. ≥60%: 5 | 🚀 Momentum dominante Δ≥15: 7 | ⚡ Gol 10m ≥60%: 4

🏆 MELHORES OPORTUNIDADES
...
```

Regras anti-spam:

- `XX:00`: panorama completo é permitido mesmo se o estado for igual ao último enviado.
- `XX:15/30/45`: só envia se houver mudança relevante.
- Pequenas oscilações dentro da mesma faixa não geram nova mensagem.
- Mudanças de status, mercado, placar, faixa de índice/probabilidade/momentum ou composição do Top geram novo estado.

## 5. AUDIT — somente semanal

- Removida a agenda diária.
- Executa **terça-feira às 23:00 de Brasília** (`quarta 02:00 UTC`).
- O relatório cobre os últimos 7 dias.
- A coleta revisita também o dia de fronteira anterior para recuperar partidas que ainda não tinham terminado na auditoria passada.
- `PENDENTE_HT` pode ser reavaliado em auditoria futura.

Mensagem semanal no mesmo webhook do PRE inclui:

- jogos com recomendação;
- entradas/recomendações;
- verificadas;
- pendentes;
- acertos;
- erros;
- assertividade;
- P/L somente das entradas com odd disponível;
- resumo por mercado;
- slots LIVE concluídos/esperados;
- recuperações pelo watchdog;
- execuções LIVE com erro.

## 6. Banco / migration

**Nenhuma migration é necessária.** O fix usa `ac10_runs.parameters` e `ac10_notifications.payload`, que já são `jsonb`.

## 7. Instalação

1. Substitua os arquivos do fix no repositório.
2. Em GitHub → Settings → Secrets and variables → Actions, adicione:
   - `DISCORD_WEBHOOK_PRE`
   - `DISCORD_WEBHOOK_LIVE`
3. Rode `90 - Tests`.
4. Opcionalmente rode `00 - Infra Check`.
5. Não é necessário alterar Supabase, Apps Script ou planilhas.

## Validação

Suite local: **44 testes aprovados**.

## Versões

- pacote Python: `0.4.7`
- PRE engine: `AC10-NEXT-PRE-0.4.4` (inalterado)
- LIVE engine: `AC10-NEXT-LIVE-0.4.4` (inalterado)
- Calibration: `AC10-NEXT-CAL-0.4.4` (inalterado)
