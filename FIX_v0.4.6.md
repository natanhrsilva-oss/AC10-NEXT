# AC10 NEXT — Fix v0.4.6

## Automação
- PRE automático às 06:00 (Brasília).
- Checagem de segurança às 06:30; só roda se não houver PRE `SUCCESS` para o dia.
- LIVE automático duas vezes por hora, em `XX:15` e `XX:30`, dentro da janela 06h–23h.

## Filtros
- Competições domésticas de Rússia, Ucrânia e Bielorrússia são excluídas do PRE e LIVE.
- Clubes desses países continuam permitidos em competições internacionais (Champions, Europa, Conference e equivalentes).

## AC10 LIVE — Planilha
- Nova ordem de colunas com `Odd Justa` antes de `Entrada Analisada`, `Confirmações` antes do `Índice`, `Momentum Jogo` após `Probabilidade %` e GPI/IDD após `Qualidade Mercado %`.
- `Momentum Jogo = clamp(50 + Momentum Casa + Momentum Visitante, 0, 100)`.
- Status visual: `X`, `OBSERVAR`, `ENTRAR`, `INTERVALO`.
- Momentum Casa/Visitante: diferença >15 pontos destaca maior em verde e menor em vermelho; caso contrário ambos permanecem azuis.

## Discord PRE
- Duas mensagens: resumo diário + melhores jogos.
- Top selecionado por qualidade e depois apresentado em ordem de horário.
- Nota AC10 de 0–10 derivada do Precision Score.
- Ícones por mercado: 🏠 BACK CASA, ✈️ BACK VISITANTE, ⚽ gols.

## Discord LIVE
- Somente partidas em andamento; intervalo nunca é enviado.
- Recomendações (`ENTRAR`) têm prioridade na lista; depois vêm os melhores jogos em observação.
- Formato enxuto com país/liga, entrada, índice, probabilidade, confirmações, odd justa, Gol 10m e +1,5 gols.
- Intervalo também é impedido de gerar nova recomendação para auditoria.
