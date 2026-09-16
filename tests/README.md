# Estratégia de testes

1. `golden/pregame`: mesmos fixtures do AC10LITE e comparação de probabilidade/índice.
2. `golden/live`: snapshots sequenciais e comparação de GPI/IDD/mercado/status.
3. invariantes de janela 38–65.
4. primeiro scan.
5. falha parcial de uma partida não interrompe lote.
6. idempotência de snapshot e recomendação.
7. outputs externos não alteram decisão.
8. benchmark com 50 partidas usando provider fake com latência controlada.
