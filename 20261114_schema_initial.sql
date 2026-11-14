-- Schéma initial : patients, mesures, lectures + accès patient / médecin.
-- Une mesure est enregistrée UNE seule fois, déjà complète
-- (1 lecture, ou 2 si une confirmation a été nécessaire).

create table patients (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,     -- compte du patient
  medecin_id uuid references auth.users(id) on delete set null,  -- compte de son médecin
  nom text not null
);

create table mesures (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references patients(id) on delete cascade,
  date_heure timestamptz not null,
  mal_de_tete smallint not null check (mal_de_tete between 0 and 5),
  vertige smallint not null check (vertige between 0 and 5),
  vision_floue smallint not null check (vision_floue between 0 and 5),
  essoufflement smallint not null check (essoufflement between 0 and 5),
  saignement_de_nez smallint not null check (saignement_de_nez between 0 and 5),
  fatigue smallint not null check (fatigue between 0 and 5),
  confusion smallint not null check (confusion between 0 and 5),
  perte_de_balan smallint not null check (perte_de_balan between 0 and 5),
  points_inquietude numeric(4,1) not null
);

create table lectures (
  id uuid primary key default gen_random_uuid(),
  mesure_id uuid not null references mesures(id) on delete cascade,
  ordre smallint not null check (ordre in (0, 1)),  -- 0 = première, 1 = confirmation
  systolique smallint not null,
  diastolique smallint not null,
  pouls smallint not null,
  pulsee smallint generated always as (systolique - diastolique) stored,
  unique (mesure_id, ordre)
);

create index on mesures (patient_id, date_heure desc);
create index on patients (user_id);
create index on patients (medecin_id);

-- ---------------------------------------------------------------
-- Accès : le patient voit/écrit ses données, le médecin LIT celles
-- de ses patients.
-- ---------------------------------------------------------------
alter table patients enable row level security;
alter table mesures  enable row level security;
alter table lectures enable row level security;

create policy patients_lecture on patients for select
  using (user_id = auth.uid() or medecin_id = auth.uid());

create policy mesures_lecture on mesures for select
  using (patient_id in (
    select id from patients
    where user_id = auth.uid() or medecin_id = auth.uid()));

create policy mesures_ecriture_patient on mesures for insert
  with check (patient_id in (select id from patients where user_id = auth.uid()));

create policy lectures_lecture on lectures for select
  using (mesure_id in (
    select m.id from mesures m join patients p on p.id = m.patient_id
    where p.user_id = auth.uid() or p.medecin_id = auth.uid()));

create policy lectures_ecriture_patient on lectures for insert
  with check (mesure_id in (
    select m.id from mesures m join patients p on p.id = m.patient_id
    where p.user_id = auth.uid()));

-- ---------------------------------------------------------------
-- Enregistrement atomique : mesure + lectures en UNE transaction.
-- Appelée depuis Python avec client.rpc("enregistrer_mesure", {...}).
-- security invoker : les politiques RLS ci-dessus s'appliquent.
-- ---------------------------------------------------------------
create or replace function enregistrer_mesure(
  p_patient_id uuid,
  p_date_heure timestamptz,
  p_symptomes jsonb,
  p_points_inquietude numeric,
  p_lectures jsonb
) returns uuid
language plpgsql
security invoker
as $$
declare
  v_mesure_id uuid;
begin
  insert into mesures (
    patient_id, date_heure, mal_de_tete, vertige, vision_floue, essoufflement,
    saignement_de_nez, fatigue, confusion, perte_de_balan, points_inquietude
  ) values (
    p_patient_id,
    p_date_heure,
    (p_symptomes->>'mal_de_tete')::smallint,
    (p_symptomes->>'vertige')::smallint,
    (p_symptomes->>'vision_floue')::smallint,
    (p_symptomes->>'essoufflement')::smallint,
    (p_symptomes->>'saignement_de_nez')::smallint,
    (p_symptomes->>'fatigue')::smallint,
    (p_symptomes->>'confusion')::smallint,
    (p_symptomes->>'perte_de_balan')::smallint,
    p_points_inquietude
  ) returning id into v_mesure_id;

  insert into lectures (mesure_id, ordre, systolique, diastolique, pouls)
  select v_mesure_id, l.ordre, l.systolique, l.diastolique, l.pouls
  from jsonb_to_recordset(p_lectures)
    as l(ordre smallint, systolique smallint, diastolique smallint, pouls smallint);

  return v_mesure_id;
end;
$$;
