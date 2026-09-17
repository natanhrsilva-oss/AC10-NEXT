# AC10 Next v0.4.2

## PRE: odds opcionais
- Odd não é mais requisito para recomendação PRE.
- Se a odd existir, ela continua registrada na planilha/histórico e o EV é calculado.
- Ausência de odd, odd abaixo de 1.60, EV negativo e divergência modelo/mercado não bloqueiam a recomendação.
- O filtro final passa a ser esportivo: especialista, confiança mínima de segurança, probabilidade mínima de segurança, qualidade, índice, Precision Score e risco de empate para BACK.
- Continua limitado a no máximo 10 recomendações e pode enviar zero se nenhum sinal esportivo passar.

## LIVE
- Continua sem exigir ou considerar odd para liberar recomendação, como na v0.4.1.

Sem migration SQL e sem mudança obrigatória no Apps Script.
