-- Job Agent database (Supabase Postgres). Safe to re-run.
--
-- Row Level Security is on with no policies, so the public API keys can't
-- read or write anything. The tracker (GitHub Actions) and the dashboard's
-- server functions use the secret key, which bypasses RLS.

create table if not exists postings (
  id                 bigserial primary key,
  source             text not null,            -- simplify | workday | greenhouse | ...
  source_key         text not null unique,     -- stable id within the source
  company            text not null,            -- display name (config name when known)
  company_key        text not null,            -- normalised, for matching
  title              text not null,
  title_key          text not null,
  locations          text[] not null default '{}',
  url                text not null default '',
  terms              text[] not null default '{}',
  degrees            text[] not null default '{}',
  category           text not null default '',
  detail             jsonb,                    -- how to fetch the description
  posted_at          timestamptz,
  posted_approx      boolean not null default false,  -- "30+ days ago" style dates
  first_seen         timestamptz not null default now(),
  last_seen          timestamptz not null default now(),
  active             boolean not null default true,
  baseline           boolean not null default false,  -- existed before tracking started

  -- pipeline
  status             text not null default 'new',     -- new | skipped | duplicate | judged | error
  skip_reason        text,
  duplicate_of       bigint references postings(id),
  description        text,
  description_status text,                     -- ok | unavailable
  judgment           jsonb,
  verdict            text,                     -- alert | maybe | skip
  tier               text,                     -- top | strong | standard
  ai_model           text,
  judged_at          timestamptz,
  notified_at        timestamptz,

  -- you
  user_status        text,                     -- applied | not_fit
  feedback_kind      text,                     -- role | company
  feedback_reason    text,
  feedback_at        timestamptz,
  applied_at         timestamptz,

  -- coverage: for postings found on a company site, when Simplify listed it
  simplify_match_id  bigint references postings(id),
  simplify_lag_hours real
);

create index if not exists postings_company_title on postings (company_key, title_key);
create index if not exists postings_status on postings (status);
create index if not exists postings_verdict on postings (verdict, first_seen desc);
create index if not exists postings_user on postings (user_status);

create table if not exists runs (
  id          bigserial primary key,
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  summary     jsonb,
  error       text
);

create table if not exists meta (
  key   text primary key,
  value jsonb
);

alter table postings enable row level security;
alter table runs enable row level security;
alter table meta enable row level security;

-- Coverage report: postings found on a company's own site, and whether /
-- how much later Simplify listed the same role. Baseline postings are left
-- out (both sources saw them on day one, so there's no lag to measure).
create or replace view coverage with (security_invoker = true) as
select
  company,
  count(*)                                              as direct_postings,
  count(simplify_match_id)                              as on_simplify,
  round(100.0 * count(simplify_match_id) / nullif(count(*), 0)) as pct_on_simplify,
  round(avg(simplify_lag_hours)::numeric, 1)            as avg_lag_hours,
  max(first_seen)                                       as last_found
from postings
where source <> 'simplify' and not baseline and status in ('judged', 'duplicate')
group by company;

-- Only the server-side secret key (service_role) may use the API.
grant usage on schema public to service_role;
grant select, insert, update, delete on postings, runs, meta to service_role;
grant select on coverage to service_role;
grant usage, select on all sequences in schema public to service_role;
revoke all on postings, runs, meta, coverage from anon, authenticated;

-- Added after launch.
alter table postings add column if not exists posted_approx boolean not null default false;
