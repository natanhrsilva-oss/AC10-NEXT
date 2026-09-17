# FIX AC10 Next v0.4.1

## Objetivo

Corrigir dois comportamentos da v0.4.0:

1. o PRE ficou restritivo demais e podia terminar frequentemente com zero recomendações mesmo havendo bons candidatos;
2. o LIVE não deve depender de odd para liberar uma entrada.

## PRE — recomendação possível, mas ainda seletiva

O `Precision Score` continua sendo a camada de alta confiança, com máximo de 10 recomendações e possibilidade de zero quando realmente não houver candidato adequado.

Na v0.4.1, **confiança, probabilidade e margem deixam de ser travas absolutas isoladas**. Elas continuam pesando fortemente no Precision Score e aparecem como `soft_flags` quando ficam abaixo dos valores de referência.

As travas duras passam a ser:

- especialista não pode estar `REJEITADO`;
- qualidade dos dados >= 55;
- índice PRE >= 58;
- Precision Score >= 63;
- risco de empate <= 62 para mercados BACK;
- odd PRE >= 1.60;
- EV >= 0;
- coerência modelo x mercado dentro do limite configurado.

O status `OBSERVAÇÃO` do especialista pode chegar à recomendação quando o conjunto completo é forte; ele recebe penalidade no Precision Score.

O log PRE agora inclui `pre_funnel`, mostrando contagem de rejeições e até 5 `near_misses`. Isso permite calibrar com evidência.

## LIVE — odd ignorada por padrão

`LIVE_REQUIRE_PRICE_FOR_RECOMMENDATION=false` agora é o padrão.

Quando o motor esportivo chega a `SINAL`, ele é promovido diretamente para `RECOMENDAÇÃO`, sem chamada à API de odds e sem filtro por odd/EV.

A recomendação fica com:

- `Odd Live`: vazio;
- `EV`: vazio;
- `Preço`: `ODD NÃO EXIGIDA`.

O histórico e a auditoria continuam funcionando. Como a entrada não tem preço salvo, P/L monetário/unidades não é inventado; o resultado esportivo continua sendo auditado como GREEN/RED.

A lógica antiga de preço continua disponível caso `LIVE_REQUIRE_PRICE_FOR_RECOMMENDATION=true` seja explicitamente configurado no futuro.

## Banco / planilha

Não exige migration SQL nova nem alteração no Apps Script da v0.4.0.
