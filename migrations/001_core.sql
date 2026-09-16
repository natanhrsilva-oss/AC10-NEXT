-- AC10 Next — core schema v1
create extension if not exists pgcrypto;

create table if not exists ac10_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null,
  model_version text,
  status text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  duration_ms integer,
  parameters jsonb not null default '{}'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  error jsonb
);
create index if not exists idx_ac10_runs_type_started on ac10_runs(run_type, started_at desc);

create table if not exists ac10_matches (
  match_id text primary key,
  kickoff timestamptz not null,
  match_date date not null,
  country text not null default '',
  competition_id text not null default '',
  competition text not null default '',
  season integer,
  home_team_id text not null,
  home_team text not null,
  away_team_id text not null,
  away_team text not null,
  state text not null default '',
  is_excluded boolean not null default false,
  exclusion_reason text not null default '',
  provider_payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
create index if not exists idx_ac10_matches_date on ac10_matches(match_date, kickoff);
create index if not exists idx_ac10_matches_state on ac10_matches(state, kickoff);

create table if not exists ac10_team_profiles (
  team_id text primary key,
  team_name text not null default '',
  recent_matches integer not null default 0,
  history_matches integer not null default 0,
  recent_form numeric not null default 50,
  attack numeric not null default 50,
  defense numeric not null default 50,
  weight numeric not null default 50,
  avg_gf numeric not null default 1.25,
  avg_ga numeric not null default 1.25,
  over25_rate numeric not null default 50,
  competition_history_strength numeric not null default 50,
  opponent_strength numeric not null default 50,
  data_quality numeric not null default 0,
  source text not null default '',
  last_match_id text,
  valid_until timestamptz,
  raw jsonb not null default '{}'::jsonb,
  calculated_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_ac10_team_profiles_valid on ac10_team_profiles(valid_until);

create table if not exists ac10_pregame_context (
  match_id text not null references ac10_matches(match_id) on delete cascade,
  model_version text not null,
  calculated_at timestamptz not null default now(),
  data_quality numeric not null default 0,
  competition_priority numeric not null default 50,

  home_attack numeric not null,
  home_defense numeric not null,
  home_weight numeric not null,
  home_recent_form numeric not null,
  away_attack numeric not null,
  away_defense numeric not null,
  away_weight numeric not null,
  away_recent_form numeric not null,

  expected_home_goals numeric not null,
  expected_away_goals numeric not null,
  expected_total_goals numeric not null,
  league_avg_goals numeric not null default 2.5,
  league_over25_rate numeric not null default 50,

  home_persona text not null default '',
  away_persona text not null default '',
  home_posture text not null default '',
  away_posture text not null default '',
  game_profile text not null default '',

  back_home_probability numeric not null default 0,
  back_away_probability numeric not null default 0,
  goals_probability numeric not null default 0,
  back_home_index numeric not null default 0,
  back_away_index numeric not null default 0,
  goals_index numeric not null default 0,

  selected_market text not null default '',
  selected_probability numeric not null default 0,
  selected_index numeric not null default 0,
  market_margin numeric not null default 0,
  confidence numeric not null default 0,
  draw_risk numeric not null default 0,

  goals_profile numeric not null default 0,
  explosive_score numeric not null default 0,
  live_readiness_score numeric not null default 0,
  live_priority text not null default 'C',

  home_odd numeric,
  draw_odd numeric,
  away_odd numeric,
  over25_odd numeric,
  raw jsonb not null default '{}'::jsonb,
  primary key (match_id, model_version)
);
create index if not exists idx_ac10_pregame_live_priority on ac10_pregame_context(live_priority, live_readiness_score desc);
create index if not exists idx_ac10_pregame_selected on ac10_pregame_context(selected_market, selected_index desc);

create table if not exists ac10_live_latest (
  match_id text not null references ac10_matches(match_id) on delete cascade,
  live_model_version text not null,
  captured_at timestamptz not null,
  minute integer not null,
  home_score integer not null default 0,
  away_score integer not null default 0,
  state text not null default '',
  live_data_mode text not null default '',
  data_quality numeric not null default 0,

  home_shots numeric not null default 0,
  away_shots numeric not null default 0,
  home_sot numeric not null default 0,
  away_sot numeric not null default 0,
  home_corners numeric not null default 0,
  away_corners numeric not null default 0,
  home_dangerous numeric not null default 0,
  away_dangerous numeric not null default 0,
  home_possession numeric not null default 50,
  away_possession numeric not null default 50,
  home_red_cards numeric not null default 0,
  away_red_cards numeric not null default 0,

  home_pressure numeric not null default 0,
  away_pressure numeric not null default 0,
  home_recent_pressure numeric not null default 0,
  away_recent_pressure numeric not null default 0,
  home_momentum numeric not null default 0,
  away_momentum numeric not null default 0,
  home_momentum_slope numeric not null default 0,
  away_momentum_slope numeric not null default 0,
  activity numeric not null default 0,
  gpi numeric not null default 0,
  gpi_delta numeric,
  home_idd numeric not null default 0,
  away_idd numeric not null default 0,
  idd_delta numeric not null default 0,
  home_need numeric not null default 0,
  away_need numeric not null default 0,
  chance_goal_10 numeric not null default 0,
  over15_more_probability numeric not null default 0,
  movement_score numeric not null default 0,
  movement_trend text not null default '',

  selected_market text not null default '',
  selected_probability numeric not null default 0,
  market_index numeric not null default 0,
  market_quality numeric not null default 0,
  confirmation_count integer not null default 0,
  status text not null default 'SEM ENTRADA',
  fair_odd numeric,
  market_odd numeric,
  ev_percent numeric,
  price_status text not null default '',
  raw jsonb not null default '{}'::jsonb,
  primary key (match_id, live_model_version)
);
create index if not exists idx_ac10_live_latest_status on ac10_live_latest(status, market_index desc);
create index if not exists idx_ac10_live_latest_captured on ac10_live_latest(captured_at desc);

create table if not exists ac10_live_snapshots (
  id bigint generated always as identity primary key,
  match_id text not null references ac10_matches(match_id) on delete cascade,
  live_model_version text not null,
  captured_at timestamptz not null,
  minute integer not null,
  home_score integer not null default 0,
  away_score integer not null default 0,
  home_shots numeric not null default 0,
  away_shots numeric not null default 0,
  home_sot numeric not null default 0,
  away_sot numeric not null default 0,
  home_corners numeric not null default 0,
  away_corners numeric not null default 0,
  home_dangerous numeric not null default 0,
  away_dangerous numeric not null default 0,
  home_pressure numeric not null default 0,
  away_pressure numeric not null default 0,
  home_recent_pressure numeric not null default 0,
  away_recent_pressure numeric not null default 0,
  home_momentum numeric not null default 0,
  away_momentum numeric not null default 0,
  gpi numeric not null default 0,
  home_idd numeric not null default 0,
  away_idd numeric not null default 0,
  chance_goal_10 numeric not null default 0,
  over15_more_probability numeric not null default 0,
  movement_score numeric not null default 0,
  selected_market text not null default '',
  market_index numeric not null default 0,
  selected_probability numeric not null default 0,
  market_quality numeric not null default 0,
  confirmation_count integer not null default 0,
  status text not null default '',
  fingerprint text not null,
  raw jsonb not null default '{}'::jsonb,
  unique (match_id, live_model_version, fingerprint)
);
create index if not exists idx_ac10_live_snapshots_match_time on ac10_live_snapshots(match_id, live_model_version, captured_at desc);

create table if not exists ac10_recommendations (
  id uuid primary key default gen_random_uuid(),
  match_id text not null references ac10_matches(match_id) on delete cascade,
  source text not null check (source in ('PRE','LIVE')),
  market text not null,
  minute integer,
  probability numeric not null,
  market_index numeric not null,
  confidence numeric,
  market_odd numeric,
  fair_odd numeric,
  ev_percent numeric,
  status text not null,
  pre_model_version text,
  live_model_version text,
  calibration_version text,
  snapshot_id bigint references ac10_live_snapshots(id) on delete set null,
  dedupe_key text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (dedupe_key)
);
create index if not exists idx_ac10_recommendations_match on ac10_recommendations(match_id, created_at desc);
create index if not exists idx_ac10_recommendations_created on ac10_recommendations(created_at desc);

create table if not exists ac10_results (
  match_id text primary key references ac10_matches(match_id) on delete cascade,
  final_home_score integer,
  final_away_score integer,
  finalized_at timestamptz,
  provider_payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists ac10_audits (
  recommendation_id uuid primary key references ac10_recommendations(id) on delete cascade,
  result text not null,
  profit_units numeric not null default 0,
  evaluated_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb
);

create table if not exists ac10_calibration_versions (
  version text primary key,
  model_scope text not null,
  status text not null check (status in ('DRAFT','APPROVED','ACTIVE','RETIRED')),
  config jsonb not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  activated_at timestamptz
);

create table if not exists ac10_api_usage (
  usage_date date not null,
  provider text not null,
  endpoint text not null,
  workflow text not null,
  request_count bigint not null default 0,
  error_count bigint not null default 0,
  latency_ms_sum bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (usage_date, provider, endpoint, workflow)
);

create table if not exists ac10_notifications (
  dedupe_key text primary key,
  channel text not null,
  status text not null,
  attempts integer not null default 0,
  last_error text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
