-- FR-9: at most one open alert per location × item. The DB enforces de-duplication, not app code.
create unique index if not exists alerts_one_open on alerts (location_id, item_id) where resolved_at is null;
