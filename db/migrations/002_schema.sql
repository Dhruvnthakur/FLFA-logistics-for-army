-- Core schema (PRD §6). Idempotent: seed.py runs every migration before loading data.
-- Depots and posts share one `locations` table so stock/alerts/routes have a single FK.

create table if not exists locations (
  id             text primary key,               -- 'BD1', 'FD1', 'P7'
  name           text not null,
  kind           text not null check (kind in ('base_depot', 'field_depot', 'post')),
  region         text not null,
  altitude_m     int  not null,
  troop_strength int,                            -- posts only
  activity_level int check (activity_level between 1 and 3),  -- posts only: 1 low, 2 normal, 3 high
  geom           geography(Point, 4326) not null
);

create table if not exists items (
  id                 text primary key,           -- 'diesel'
  name               text not null,
  class              text not null,
  unit               text not null,
  weight_kg_per_unit numeric not null,
  priority           int  not null unique        -- 1 = most urgent (ammo); single source of truth
);

create table if not exists stock_levels (
  location_id  text not null references locations(id),
  item_id      text not null references items(id),
  quantity     numeric not null check (quantity >= 0),
  safety_stock numeric not null check (safety_stock >= 0),
  updated_at   timestamptz not null default now(),
  primary key (location_id, item_id)
);

create table if not exists stock_readings (
  id          bigserial primary key,
  location_id text not null references locations(id),
  item_id     text not null references items(id),
  quantity    numeric not null check (quantity >= 0),
  ts          timestamptz not null
);

create table if not exists consumption_history (
  post_id        text not null references locations(id),
  item_id        text not null references items(id),
  date           date not null,
  qty            numeric not null,
  troop_strength int not null,
  temp_c         numeric not null,
  activity_level int not null,
  primary key (post_id, item_id, date)
);

create table if not exists route_edges (
  id                 text primary key,
  name               text not null,               -- 'Route A', 'Route B (leg 1)'
  from_node          text not null references locations(id),
  to_node            text not null references locations(id),
  distance_km        numeric not null,
  terrain_difficulty numeric not null check (terrain_difficulty between 1 and 5),
  base_speed_kmh     numeric not null,
  status             text not null default 'open' check (status in ('open', 'degraded', 'closed')),
  geom               geography(LineString, 4326) not null
);

create table if not exists weather (
  node_id     text not null references locations(id),
  ts          timestamptz not null,
  temp_c      numeric,
  snowfall_cm numeric,
  precip_mm   numeric,
  wind_kmh    numeric,
  primary key (node_id, ts)
);

create table if not exists vehicles (
  id         text primary key,
  type       text not null,
  capacity_t numeric not null,
  depot_id   text not null references locations(id),
  available  boolean not null default true
);

create table if not exists alerts (
  id          bigserial primary key,
  location_id text not null references locations(id),
  item_id     text not null references items(id),
  level       text not null check (level in ('amber', 'red')),
  message     text not null,
  created_at  timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists dispatch_plans (
  id          bigserial primary key,
  item_id     text not null references items(id),
  qty         numeric not null,
  vehicle_id  text references vehicles(id),
  origin      text not null references locations(id),
  destination text not null references locations(id),
  path        text[] not null,                    -- node ids, origin → destination
  depart_by   timestamptz,
  eta         timestamptz,
  status      text not null default 'proposed' check (status in ('proposed', 'approved', 'dispatched')),
  created_at  timestamptz not null default now()
);
