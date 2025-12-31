-- ============================================
-- MADAGASCAR FC - SUPABASE DATABASE SCHEMA
-- ============================================
-- Ejecuta este script completo en tu panel de Supabase:
-- 1. Ve a tu proyecto en supabase.com
-- 2. Abre SQL Editor (barra lateral izquierda)
-- 3. Pega TODO este código
-- 4. Click en "RUN" 
-- ============================================

-- ============================================
-- TABLA: user_progress (ya la tienes, verificamos)
-- ============================================
create table if not exists public.user_progress (
    user_id uuid primary key references auth.users(id) on delete cascade,
    progress jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

alter table public.user_progress enable row level security;

-- Políticas (por si no existen)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'select_own_progress' AND tablename = 'user_progress') THEN
        CREATE POLICY select_own_progress ON public.user_progress FOR SELECT USING (auth.uid() = user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'insert_own_progress' AND tablename = 'user_progress') THEN
        CREATE POLICY insert_own_progress ON public.user_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'update_own_progress' AND tablename = 'user_progress') THEN
        CREATE POLICY update_own_progress ON public.user_progress FOR UPDATE USING (auth.uid() = user_id);
    END IF;
END $$;

-- ============================================
-- TABLA: players (Plantilla del equipo)
-- ============================================
create table if not exists public.players (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    nickname text,
    jersey_number integer,
    position text check (position in ('Portero', 'Defensa', 'Centrocampista', 'Delantero')),
    is_active boolean default true,
    photo_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

alter table public.players enable row level security;

-- Todos los usuarios autenticados pueden ver jugadores
create policy if not exists "players_select_authenticated" 
    on public.players for select 
    to authenticated 
    using (true);

-- Cualquier autenticado puede insertar/actualizar/borrar (para el equipo)
create policy if not exists "players_insert_authenticated" 
    on public.players for insert 
    to authenticated 
    with check (true);

create policy if not exists "players_update_authenticated" 
    on public.players for update 
    to authenticated 
    using (true);

create policy if not exists "players_delete_authenticated" 
    on public.players for delete 
    to authenticated 
    using (true);

-- ============================================
-- TABLA: matches (Partidos)
-- ============================================
create table if not exists public.matches (
    id uuid primary key default gen_random_uuid(),
    opponent text not null,
    match_date date not null,
    match_time time,
    location text,
    competition text,
    is_home boolean default true,
    goals_for integer,
    goals_against integer,
    notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

alter table public.matches enable row level security;

create policy if not exists "matches_select_authenticated" 
    on public.matches for select 
    to authenticated 
    using (true);

create policy if not exists "matches_insert_authenticated" 
    on public.matches for insert 
    to authenticated 
    with check (true);

create policy if not exists "matches_update_authenticated" 
    on public.matches for update 
    to authenticated 
    using (true);

create policy if not exists "matches_delete_authenticated" 
    on public.matches for delete 
    to authenticated 
    using (true);

-- ============================================
-- TABLA: player_stats (Estadísticas por partido)
-- ============================================
create table if not exists public.player_stats (
    id uuid primary key default gen_random_uuid(),
    player_id uuid references public.players(id) on delete cascade,
    match_id uuid references public.matches(id) on delete cascade,
    goals integer default 0,
    assists integer default 0,
    yellow_cards integer default 0,
    red_cards integer default 0,
    minutes_played integer default 0,
    rating decimal(3,1),
    created_at timestamptz default now(),
    unique(player_id, match_id)
);

alter table public.player_stats enable row level security;

create policy if not exists "player_stats_select_authenticated" 
    on public.player_stats for select 
    to authenticated 
    using (true);

create policy if not exists "player_stats_insert_authenticated" 
    on public.player_stats for insert 
    to authenticated 
    with check (true);

create policy if not exists "player_stats_update_authenticated" 
    on public.player_stats for update 
    to authenticated 
    using (true);

create policy if not exists "player_stats_delete_authenticated" 
    on public.player_stats for delete 
    to authenticated 
    using (true);

-- ============================================
-- TABLA: standings (Clasificación de la liga)
-- ============================================
create table if not exists public.standings (
    id uuid primary key default gen_random_uuid(),
    team_name text not null,
    position integer not null,
    matches_played integer default 0,
    wins integer default 0,
    draws integer default 0,
    losses integer default 0,
    goals_for integer default 0,
    goals_against integer default 0,
    goal_difference integer generated always as (goals_for - goals_against) stored,
    points integer default 0,
    season text default '2024-25',
    updated_at timestamptz default now()
);

alter table public.standings enable row level security;

create policy if not exists "standings_select_authenticated" 
    on public.standings for select 
    to authenticated 
    using (true);

create policy if not exists "standings_all_authenticated" 
    on public.standings for all
    to authenticated 
    using (true);

-- ============================================
-- TABLA: announcements (Anuncios del equipo)
-- ============================================
create table if not exists public.announcements (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    content text,
    author_name text,
    is_pinned boolean default false,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz default now()
);

alter table public.announcements enable row level security;

create policy if not exists "announcements_select_authenticated" 
    on public.announcements for select 
    to authenticated 
    using (true);

create policy if not exists "announcements_insert_authenticated" 
    on public.announcements for insert 
    to authenticated 
    with check (true);

create policy if not exists "announcements_delete_own" 
    on public.announcements for delete 
    to authenticated 
    using (auth.uid() = created_by);

-- ============================================
-- TABLA: activity_feed (Feed de actividad)
-- ============================================
create table if not exists public.activity_feed (
    id uuid primary key default gen_random_uuid(),
    activity_type text not null check (activity_type in ('trophy_unlock', 'match_result', 'announcement', 'player_added', 'glagascar_vote')),
    title text not null,
    description text,
    user_id uuid references auth.users(id) on delete set null,
    user_name text,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

alter table public.activity_feed enable row level security;

create policy if not exists "activity_feed_select_authenticated" 
    on public.activity_feed for select 
    to authenticated 
    using (true);

create policy if not exists "activity_feed_insert_authenticated" 
    on public.activity_feed for insert 
    to authenticated 
    with check (true);

-- ============================================
-- TABLA: glagascar_settings (Configuración Glagascar)
-- ============================================
create table if not exists public.glagascar_settings (
    id uuid primary key default gen_random_uuid(),
    edition_year integer not null default extract(year from now()),
    ceremony_date timestamptz,
    voting_open boolean default false,
    results_visible boolean default false,
    theme_name text default 'Road to Glagascar',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

alter table public.glagascar_settings enable row level security;

create policy if not exists "glagascar_settings_select_authenticated" 
    on public.glagascar_settings for select 
    to authenticated 
    using (true);

create policy if not exists "glagascar_settings_all_authenticated" 
    on public.glagascar_settings for all
    to authenticated 
    using (true);

-- Insertar configuración por defecto
INSERT INTO public.glagascar_settings (edition_year, ceremony_date, voting_open)
VALUES (2026, '2026-06-01 20:00:00+00', true)
ON CONFLICT DO NOTHING;

-- ============================================
-- TABLA: glagascar_categories (Categorías de premios)
-- ============================================
create table if not exists public.glagascar_categories (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    icon text default '🏆',
    display_order integer default 0,
    is_active boolean default true,
    created_at timestamptz default now()
);

alter table public.glagascar_categories enable row level security;

create policy if not exists "glagascar_categories_select_authenticated" 
    on public.glagascar_categories for select 
    to authenticated 
    using (true);

create policy if not exists "glagascar_categories_insert_authenticated" 
    on public.glagascar_categories for insert 
    to authenticated 
    with check (true);

create policy if not exists "glagascar_categories_update_authenticated" 
    on public.glagascar_categories for update 
    to authenticated 
    using (true);

-- ============================================
-- TABLA: glagascar_nominations (Nominaciones)
-- ============================================
create table if not exists public.glagascar_nominations (
    id uuid primary key default gen_random_uuid(),
    category_id uuid references public.glagascar_categories(id) on delete cascade,
    nominee_name text not null,
    reason text,
    nominated_by uuid references auth.users(id) on delete set null,
    created_at timestamptz default now()
);

alter table public.glagascar_nominations enable row level security;

create policy if not exists "glagascar_nominations_select_authenticated" 
    on public.glagascar_nominations for select 
    to authenticated 
    using (true);

create policy if not exists "glagascar_nominations_insert_authenticated" 
    on public.glagascar_nominations for insert 
    to authenticated 
    with check (true);

-- ============================================
-- TABLA: glagascar_votes (Votos)
-- ============================================
create table if not exists public.glagascar_votes (
    id uuid primary key default gen_random_uuid(),
    nomination_id uuid references public.glagascar_nominations(id) on delete cascade,
    user_id uuid references auth.users(id) on delete cascade,
    created_at timestamptz default now(),
    unique(nomination_id, user_id)  -- Un usuario = un voto por nominación
);

alter table public.glagascar_votes enable row level security;

create policy if not exists "glagascar_votes_select_authenticated" 
    on public.glagascar_votes for select 
    to authenticated 
    using (true);

create policy if not exists "glagascar_votes_insert_authenticated" 
    on public.glagascar_votes for insert 
    to authenticated 
    with check (auth.uid() = user_id);

-- ============================================
-- ÍNDICES PARA RENDIMIENTO
-- ============================================
create index if not exists idx_matches_date on public.matches(match_date);
create index if not exists idx_player_stats_player on public.player_stats(player_id);
create index if not exists idx_player_stats_match on public.player_stats(match_id);
create index if not exists idx_activity_feed_created on public.activity_feed(created_at desc);
create index if not exists idx_announcements_created on public.announcements(created_at desc);
create index if not exists idx_glagascar_nominations_category on public.glagascar_nominations(category_id);
create index if not exists idx_glagascar_votes_nomination on public.glagascar_votes(nomination_id);

-- ============================================
-- ¡LISTO! 
-- Tu base de datos está configurada.
-- Ahora ve a tu app y disfruta de Madagascar FC 🦁
-- ============================================
