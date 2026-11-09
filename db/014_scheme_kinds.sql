-- VoicePath -- jobs, training and schemes as three kinds of record.
-- Apply BEFORE deploying the code that reads these columns. Safe to re-run.
--
-- Decided 2026-11-09: one table, a kind, kind-specific details, and weights per
-- kind (backend/app/services/kinds.py). Everything was a "scheme" with a
-- free-text type, so a job and a course were told apart only by that label.
--
-- 1. schemes.kind -- job, training or scheme, following from type exactly as
--    kinds.kind_for_type does (Full-time/Part-time -> job; Training and
--    Apprenticeship -> training; everything else -> scheme). Admin writes set
--    it from the type the same way, so the two cannot disagree.
-- 2. schemes.details -- the facts of that kind the listing states, and only
--    those. Generated from catalogue.DETAILS, where each sits beside the words
--    it comes from; tests/test_kinds.py checks the two agree.

alter table schemes add column if not exists kind text not null default 'scheme';
alter table schemes add column if not exists details jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'schemes_kind_allowed') then
    alter table schemes add constraint schemes_kind_allowed
      check (kind in ('job', 'training', 'scheme'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'schemes_details_is_object') then
    alter table schemes add constraint schemes_details_is_object
      check (jsonb_typeof(details) = 'object');
  end if;
end $$;

update schemes
   set kind = case
     when type in ('Full-time', 'Part-time') then 'job'
     when type in ('Training', 'Apprenticeship') then 'training'
     else 'scheme'
   end;

comment on column schemes.kind is
  'job, training or scheme; follows from type (services/kinds.py).';
comment on column schemes.details is
  'Facts of this kind the listing states (services/kinds.DETAIL_FIELDS).';

with stated (source_reference, details) as (values
  ('OGD/TN/SLM/AUTO/2024/0117', '{"days_per_week": 6}'),
  ('PMAJAY/SKILL/TN/SLM/ITI/2024/0042', '{"duration_months": 4, "stipend_monthly": 3000}'),
  ('PMAJAY/LIV/TN/SLM/2024/0008', '{"benefit_max": 200000, "installments": 2}'),
  ('PMAJAY/SKILL/TN/SLM/ITI/2024/0051', '{"duration_months": 3, "stipend_monthly": 2500}'),
  ('OGD/TN/ERD/TEX/2024/0402', '{"shift_work": true}'),
  ('PMAJAY/LIV/TN/SLM/2024/0011', '{"benefit_max": 100000}'),
  ('PMAJAY/SKILL/TN/SLM/DSC/2024/0027', '{"duration_months": 2, "stipend_monthly": 2000}'),
  ('PMAJAY/LIV/TN/SLM/2024/0019', '{"benefit_max": 150000}'),
  ('GOI/PMVISHWAKARMA/2023-09-20', '{"benefit_max": 300000, "how_to_apply": "Enrolment of beneficiaries shall be done through Common Service Centres with Aadhaar-based biometric authentication on PM Vishwakarma portal.", "installments": 2}'),
  ('GOI/PMSVANIDHI/2026-05-30', '{"benefit_max": 50000, "installments": 3}')
)
update schemes s
   set details = stated.details::jsonb
  from stated
 where s.source_reference = stated.source_reference;
