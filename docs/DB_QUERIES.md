# Consultas críticas que o schema precisa resolver rápido

## LIVE: carregar PRE de todos os jogos ativos
```sql
select * from ac10_pregame_context
where match_id = any($1) and model_version = $2;
```

## LIVE: carregar último estado
```sql
select * from ac10_live_latest
where match_id = any($1) and live_model_version = $2;
```

## LIVE: carregar janela temporal
```sql
select * from ac10_live_snapshots
where match_id = any($1) and live_model_version = $2
order by match_id, captured_at desc;
```

## Painel: melhores jogos agora
```sql
select * from ac10_live_latest
where market_index > 55
order by market_index desc, confirmation_count desc
limit 5;
```
