# FIX AC10 Next v0.4.0

## Implementado

1. PRE Precision Score independente do Live Readiness.
2. PRE envia 0–10 recomendações; nunca completa vagas artificialmente.
3. Filtro PRE exige especialista aprovado, qualidade, confiança, índice, margem, odd mínima, EV e coerência preço/modelo.
4. Odds PRE reduzidas de até 60 para até 20 chamadas por execução.
5. PRE Discord ativado por padrão.
6. Recomendações PRE persistidas em `ac10_recommendations`.
7. LIVE separa `SINAL` de `RECOMENDAÇÃO`; apenas preço válido promove a entrada.
8. Pós-gol reduz probabilidade de novo gol por até 10 minutos.
9. Novo gol nos últimos 0–2 minutos impede novo sinal de gol.
10. Cartão vermelho recente cria Event Reset curto.
11. Proteção contra estatísticas estagnadas por scans consecutivos.
12. Planilha LIVE com zebra azul, semáforo 55/45 e linha verde para entrada ofertada.
13. Nova aba `HISTÓRICO PRE`.
14. Nova aba `HISTÓRICO LIVE`.
15. AUDIT atualiza históricos com GREEN/RED e P/L.
16. Novas colunas operacionais no LIVE: Gol Recente, Min Desde Gol, Fator Pós-Gol e Dados Frescos.
17. Testes ampliados para PRE Precision, cooldown, stale data e promoção SINAL→RECOMENDAÇÃO.

## Banco

Nenhuma migration adicional obrigatória.

## Apps Script

Substitua o código atual pelo novo `google-apps-script/Code.gs` e faça:

`Deploy → Manage deployments → Edit → New version → Deploy`

Mantenha o mesmo `AC10_TOKEN`. Em geral a URL do Web App permanece a mesma, portanto os secrets do GitHub não precisam ser alterados.

## Observação de versão

PRE e LIVE mudaram para `0.4.0`. Por isso, após o deploy, rode o PRE antes do LIVE. O primeiro scan LIVE da versão nova será base inicial; o segundo começa a recuperar delta/momentum.
