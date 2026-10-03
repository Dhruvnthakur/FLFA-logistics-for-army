-- Phase 5 (FR-19): route edges for map highlighting, on-time flag, one-sentence explanation.
-- Rows the fleet can't cover are still listed (vehicle_id null); an unreachable post has no origin.
alter table dispatch_plans add column if not exists edges text[] not null default '{}';
alter table dispatch_plans add column if not exists arrives_before_stockout boolean not null default false;
alter table dispatch_plans add column if not exists explanation text not null default '';
alter table dispatch_plans alter column origin drop not null;
