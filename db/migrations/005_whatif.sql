-- Phase 7 (FR-23): what-if scenario state. Keys: baseline_routes, storms, troops (see services/whatif.py).
create table if not exists whatif_state (
  key   text primary key,
  value jsonb not null
);
