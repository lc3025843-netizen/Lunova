-- Lunova v0.1 — persistent database + RLS + private document storage
-- Run this once in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  display_name text not null default 'Usuario',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  mode text not null default 'Académico',
  level integer not null default 2 check (level between 1 and 3),
  research_mode boolean not null default true,
  options jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'Documento sin título',
  source_type text not null default 'text' check (source_type in ('text','docx')),
  original_text text not null default '',
  latest_text text not null default '',
  storage_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists documents_user_updated_idx on public.documents(user_id, updated_at desc);

create table if not exists public.revisions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  mode text not null default 'Académico',
  level integer not null default 2 check (level between 1 and 3),
  research_mode boolean not null default true,
  original_text text not null,
  revised_text text not null,
  similarity_score integer not null default 0 check (similarity_score between 0 and 100),
  passes integer not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists revisions_user_created_idx on public.revisions(user_id, created_at desc);

create table if not exists public.announcements (
  id uuid primary key default gen_random_uuid(),
  version text not null default '0.1',
  title text not null,
  message text not null,
  active boolean not null default true,
  published_at timestamptz not null default now()
);

create table if not exists public.announcement_reads (
  user_id uuid not null references auth.users(id) on delete cascade,
  announcement_id uuid not null references public.announcements(id) on delete cascade,
  read_at timestamptz not null default now(),
  primary key (user_id, announcement_id)
);

create table if not exists public.app_settings (
  key text primary key,
  value jsonb,
  updated_at timestamptz not null default now()
);

insert into public.app_settings(key, value) values
  ('maintenance_enabled', 'false'::jsonb),
  ('maintenance_message', '"Lunova está realizando mejoras. Intenta nuevamente más tarde."'::jsonb),
  ('global_banner', '""'::jsonb),
  ('editorial_instruction', '""'::jsonb)
on conflict (key) do nothing;

-- RLS is the separation between users.
alter table public.profiles enable row level security;
alter table public.preferences enable row level security;
alter table public.documents enable row level security;
alter table public.revisions enable row level security;
alter table public.announcements enable row level security;
alter table public.announcement_reads enable row level security;
alter table public.app_settings enable row level security;

-- Least-privilege grants for authenticated users.
revoke all on table public.profiles, public.preferences, public.documents, public.revisions,
  public.announcements, public.announcement_reads, public.app_settings from anon;

grant select, insert, update on table public.profiles to authenticated;
grant select, insert, update, delete on table public.preferences to authenticated;
grant select, insert, update, delete on table public.documents to authenticated;
grant select, insert, delete on table public.revisions to authenticated;
grant select on table public.announcements to authenticated;
grant select, insert, update, delete on table public.announcement_reads to authenticated;
grant select on table public.app_settings to authenticated;

grant all on table public.profiles, public.preferences, public.documents, public.revisions,
  public.announcements, public.announcement_reads, public.app_settings to service_role;

-- Drop policies first so the script is re-runnable.
drop policy if exists profiles_select_own on public.profiles;
drop policy if exists profiles_insert_own on public.profiles;
drop policy if exists profiles_update_own on public.profiles;
create policy profiles_select_own on public.profiles for select to authenticated using ((select auth.uid()) = id);
create policy profiles_insert_own on public.profiles for insert to authenticated with check ((select auth.uid()) = id);
create policy profiles_update_own on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

drop policy if exists preferences_select_own on public.preferences;
drop policy if exists preferences_insert_own on public.preferences;
drop policy if exists preferences_update_own on public.preferences;
drop policy if exists preferences_delete_own on public.preferences;
create policy preferences_select_own on public.preferences for select to authenticated using ((select auth.uid()) = user_id);
create policy preferences_insert_own on public.preferences for insert to authenticated with check ((select auth.uid()) = user_id);
create policy preferences_update_own on public.preferences for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy preferences_delete_own on public.preferences for delete to authenticated using ((select auth.uid()) = user_id);

drop policy if exists documents_select_own on public.documents;
drop policy if exists documents_insert_own on public.documents;
drop policy if exists documents_update_own on public.documents;
drop policy if exists documents_delete_own on public.documents;
create policy documents_select_own on public.documents for select to authenticated using ((select auth.uid()) = user_id);
create policy documents_insert_own on public.documents for insert to authenticated with check ((select auth.uid()) = user_id);
create policy documents_update_own on public.documents for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy documents_delete_own on public.documents for delete to authenticated using ((select auth.uid()) = user_id);

drop policy if exists revisions_select_own on public.revisions;
drop policy if exists revisions_insert_own on public.revisions;
drop policy if exists revisions_delete_own on public.revisions;
create policy revisions_select_own on public.revisions for select to authenticated using ((select auth.uid()) = user_id);
create policy revisions_insert_own on public.revisions for insert to authenticated
  with check ((select auth.uid()) = user_id and exists (
    select 1 from public.documents d where d.id = document_id and d.user_id = (select auth.uid())
  ));
create policy revisions_delete_own on public.revisions for delete to authenticated using ((select auth.uid()) = user_id);

drop policy if exists announcements_select_active on public.announcements;
create policy announcements_select_active on public.announcements for select to authenticated using (active = true);

drop policy if exists announcement_reads_select_own on public.announcement_reads;
drop policy if exists announcement_reads_insert_own on public.announcement_reads;
drop policy if exists announcement_reads_update_own on public.announcement_reads;
drop policy if exists announcement_reads_delete_own on public.announcement_reads;
create policy announcement_reads_select_own on public.announcement_reads for select to authenticated using ((select auth.uid()) = user_id);
create policy announcement_reads_insert_own on public.announcement_reads for insert to authenticated with check ((select auth.uid()) = user_id);
create policy announcement_reads_update_own on public.announcement_reads for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy announcement_reads_delete_own on public.announcement_reads for delete to authenticated using ((select auth.uid()) = user_id);

drop policy if exists app_settings_read on public.app_settings;
create policy app_settings_read on public.app_settings for select to authenticated using (true);

-- Private Word file bucket. 20 MB per file is enough for the v0.1 use case.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'lunova-documents',
  'lunova-documents',
  false,
  20971520,
  array['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Path format is: <auth.uid()>/<unique filename>.docx
-- storage.foldername(name)[1] returns the first folder.
drop policy if exists lunova_storage_select_own on storage.objects;
drop policy if exists lunova_storage_insert_own on storage.objects;
drop policy if exists lunova_storage_update_own on storage.objects;
drop policy if exists lunova_storage_delete_own on storage.objects;
create policy lunova_storage_select_own on storage.objects for select to authenticated
using (bucket_id = 'lunova-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy lunova_storage_insert_own on storage.objects for insert to authenticated
with check (bucket_id = 'lunova-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy lunova_storage_update_own on storage.objects for update to authenticated
using (bucket_id = 'lunova-documents' and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id = 'lunova-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy lunova_storage_delete_own on storage.objects for delete to authenticated
using (bucket_id = 'lunova-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
