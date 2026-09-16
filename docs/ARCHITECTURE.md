# Arquitetura técnica — AC10 Next

## 1. Componentes oficiais

### AC10 PRE
Responsável por catálogo do dia, perfis de times, odds pré-jogo, especialistas e meta-motor pré-game.

### AC10 LIVE
Responsável por descoberta de partidas em andamento, estatísticas live, série temporal, decisão de mercado e price check.

### AC10 AUDIT
Responsável por resultado, ROI, precisão, análise por bucket e propostas de calibração.

Não existirão motores oficiais separados Live3, LivePro, LivePro2 ou AOViVo. As melhores capacidades deles serão componentes internos do `AC10 LIVE`.

---

## 2. Contrato PRE -> LIVE

Cada partida deve ter exatamente um `pregame_context` vigente por `match_id + model_version`.

Campos essenciais:

- identidade: match_id, kickoff, país, competição, mandante, visitante;
- qualidade: data_quality, competition_priority;
- estrutura dos times: attack, defense, weight, recent_form;
- projeções: xG casa, xG visitante, xG total;
- personas e postura;
- índices dos três especialistas;
- mercado pré selecionado, probabilidade, índice, confiança e risco de empate;
- perfil de gols, potencial explosivo e `live_readiness_score`;
- versão do modelo e timestamp de cálculo.

O LIVE nunca deve chamar histórico/forma para jogos com `pregame_context` válido. Se faltar contexto, um `EmergencyPregameBuilder` calcula apenas a partida ausente e persiste o resultado.

---

## 3. Pipeline AC10 PRE

```text
matches(day)
   -> exclusions
   -> team ids únicos
   -> team_profile cache/batch refresh
   -> pregame odds batch
   -> MatchFeatures vNext
   -> especialistas [Back Casa, Back Visitante, Gols]
   -> meta-motor
   -> live readiness
   -> bulk upsert pregame_context
   -> Sheets PRE (não bloqueante)
   -> Discord PRE (opcional)
```

### Cache de time
A invalidação preferida é por evento: novo jogo finalizado do time. TTL serve apenas como fallback de segurança.

---

## 4. Pipeline AC10 LIVE

```text
active matches
   -> exclusions + minute window
   -> batch load pregame_context
   -> emergency pregame only for missing matches
   -> scheduler classifies lanes
   -> async live stats fetch
   -> load live_latest + last snapshots in batch
   -> compute Pressure / Activity / Momentum / GPI / IDD / Goal Watch
   -> choose market + confirmations
   -> candidate shortlist
   -> odds fetch only for shortlist
   -> price validation
   -> bulk upsert live_latest
   -> append meaningful snapshots
   -> append recommendations
   -> non-blocking outputs
```

### Fast Lane
Partidas com prioridade A/B, status AQUECENDO/RECOMENDAÇÃO ou índice acima do limiar operacional.

### Discovery Lane
Demais partidas. Frequência menor até surgirem sinais que promovam o jogo para Fast Lane.

A frequência final deve respeitar o comportamento real do provider e o orçamento diário de requests; ela fica em configuração, não hardcoded.

---

## 5. Estado temporal

### `live_latest`
Uma linha por partida e scanner versionado. Serve para estado atual e acesso O(1).

### `live_snapshots`
Série temporal imutável para evolução. Só insere snapshot se:

- minuto avançou suficientemente; ou
- placar mudou; ou
- estatística-chave mudou; ou
- índice/status/mercado mudou materialmente.

O snapshot guarda métricas normalizadas, não apenas um JSON gigante.

---

## 6. Decisão LIVE

A decisão mantém as melhores regras do LivePro2 atual:

- primeiro scan geralmente não recomenda;
- comparação recente válida somente com intervalo temporal coerente;
- momentum cumulativo usa vários snapshots;
- necessidade só pesa quando há execução real;
- qualidade de mercado bloqueia recomendação com estatística insuficiente;
- 38–65 minutos é janela `BACK ONLY`;
- odds são secundárias e consultadas depois do sinal esportivo;
- divergência extrema modelo x mercado bloqueia envio;
- recomendação exige múltiplas confirmações.

### Fases propostas

- 10–37: GOL HT dominante; Back pode vencer apenas com direção excepcional.
- 38–65: somente BACK CASA / BACK VISITANTE.
- 66–88: OVER +1 GOL dominante; Back direcional ainda pode superar por convicção.

---

## 7. Concorrência e IO

### HTTP
- `httpx.AsyncClient` compartilhado;
- semáforo por provider;
- timeout por request;
- retries somente para erros transitórios;
- exponential backoff + jitter;
- circuit breaker simples;
- métricas de latência por endpoint.

### Postgres/Supabase
- `psycopg_pool.AsyncConnectionPool`;
- uma conexão por unidade de trabalho, não por linha;
- `executemany`/bulk upsert;
- índices desenhados para as consultas reais;
- migrations executadas apenas no deploy.

---

## 8. Falhas externas

- Sheets falhou: scanner conclui e registra `output_failure`.
- Discord falhou: recomendação permanece salva e pode ser reentregue.
- Odds falharam: decisão técnica permanece, mas não vira recomendação oficial se o mercado exigir price check.
- Estatística de uma partida falhou: outras partidas continuam.
- PRE ausente: emergency builder somente para aquele jogo.
- Supabase indisponível: LIVE não deve fingir comparação temporal; roda degradado e não libera recomendações dependentes de histórico.

---

## 9. Observabilidade

Toda execução grava:

- duração total;
- tempo por etapa;
- jogos encontrados/elegíveis/processados;
- requests por endpoint/provider;
- cache hit/miss;
- quantidade de emergências PRE;
- falhas por partida;
- distribuição de qualidade;
- candidatos e recomendações;
- tempo de Sheets/Discord isolado do tempo do motor.

---

## 10. Versionamento

Separar versões:

- `PRE_MODEL_VERSION`
- `LIVE_MODEL_VERSION`
- `CALIBRATION_VERSION`
- `SCHEMA_VERSION`

Toda recomendação deve guardar as quatro referências aplicáveis.

---

## 11. Regra de ouro

O LIVE deve responder à pergunta:

> O que esta partida está fazendo AGORA em relação ao cenário que o PRE já esperava?

Ele não deve redescobrir quem são os times durante cada execução.
