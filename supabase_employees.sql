-- Staff list for the parking app, kept by the manager at /mngr.
-- Run once in the Supabase SQL editor, after supabase_setup.sql.
--
-- One row holds the list: employees = [{"name": "...", "password": "..."}, ...].
-- The app generates each password (8 random letters and digits); nothing
-- checks them yet.

create table if not exists settings (
  id int primary key default 1 check (id = 1),
  employees jsonb not null default '[]'::jsonb
);

-- No policies: only the app's secret key can read or write the list.
alter table settings enable row level security;

insert into settings (id) values (1) on conflict (id) do nothing;
