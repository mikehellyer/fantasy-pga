-- Fantasy PGA online leagues.
--
-- Paste all of this into Supabase: your project -> SQL Editor -> New query -> Run.
-- Running it again is safe (it replaces the functions and keeps existing leagues).
--
-- The game only ever calls the functions at the bottom. The tables have row level
-- security switched on with no policies, so nobody can read or change them directly:
-- every change goes through a function that checks the player's secret token.

create table if not exists leagues (
    code text primary key,
    name text not null,
    commissioner_token text not null,
    status text not null default 'lobby',        -- lobby (friends joining) / active
    game_version text not null,
    version integer not null default 0,           -- goes up by one every time the state is saved
    state jsonb,                                  -- the whole game, uploaded by the commissioner
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists players (
    league_code text not null references leagues (code) on delete cascade,
    player_id integer not null,                   -- 0 = the commissioner
    token text not null,
    manager text not null,
    team text not null,
    joined_at timestamptz not null default now(),
    primary key (league_code, player_id)
);

create table if not exists lineups (
    league_code text not null references leagues (code) on delete cascade,
    player_id integer not null,
    season integer not null,
    event_index integer not null,
    round integer not null,                       -- the round it's for: 0 = before round 1
    lineup jsonb not null,
    submitted_at timestamptz not null default now(),
    primary key (league_code, player_id)
);

alter table leagues enable row level security;
alter table players enable row level security;
alter table lineups enable row level security;
revoke all on leagues, players, lineups from anon, authenticated;


-- A new league. Returns {"code", "token"} - the token proves you're the commissioner.
create or replace function fpga_create_league(p_name text, p_manager text, p_team text, p_game_version text)
returns json language plpgsql security definer set search_path = public as $$
declare
    v_code text;
    v_token text := gen_random_uuid()::text;
    v_letters text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';  -- no 0/O or 1/I mix-ups
begin
    loop
        v_code := '';
        for i in 1..6 loop
            v_code := v_code || substr(v_letters, 1 + floor(random() * length(v_letters))::int, 1);
        end loop;
        exit when not exists (select 1 from leagues where code = v_code);
    end loop;
    insert into leagues (code, name, commissioner_token, game_version)
        values (v_code, left(coalesce(nullif(trim(p_name), ''), 'Fantasy League'), 40), v_token, p_game_version);
    insert into players (league_code, player_id, token, manager, team)
        values (v_code, 0, v_token, left(p_manager, 30), left(p_team, 30));
    return json_build_object('code', v_code, 'token', v_token);
end $$;


-- Join a league that hasn't started yet. Returns {"player_id", "token"}.
create or replace function fpga_join_league(p_code text, p_manager text, p_team text)
returns json language plpgsql security definer set search_path = public as $$
declare
    v_league leagues;
    v_id integer;
    v_token text := gen_random_uuid()::text;
begin
    select * into v_league from leagues where code = upper(trim(p_code)) for update;
    if not found then
        raise exception 'No league with the code %', upper(trim(p_code));
    end if;
    if v_league.status <> 'lobby' then
        raise exception 'That league has already started';
    end if;
    select coalesce(max(player_id), -1) + 1 into v_id from players where league_code = v_league.code;
    if v_id >= 12 then
        raise exception 'That league is full (12 managers)';
    end if;
    insert into players (league_code, player_id, token, manager, team)
        values (v_league.code, v_id, v_token, left(p_manager, 30), left(p_team, 30));
    update leagues set updated_at = now() where code = v_league.code;
    return json_build_object('player_id', v_id, 'token', v_token);
end $$;


-- Everything anyone in the league can see: the managers, the state's version number and
-- who has sent in a lineup (but not the lineups themselves).
create or replace function fpga_league_info(p_code text)
returns json language sql security definer set search_path = public as $$
    select json_build_object(
        'code', l.code,
        'name', l.name,
        'status', l.status,
        'version', l.version,
        'game_version', l.game_version,
        'updated_at', l.updated_at,
        'players', coalesce((select json_agg(json_build_object(
                'player_id', p.player_id, 'manager', p.manager, 'team', p.team) order by p.player_id)
            from players p where p.league_code = l.code), '[]'::json),
        'lineups', coalesce((select json_agg(json_build_object(
                'player_id', x.player_id, 'season', x.season, 'event_index', x.event_index,
                'round', x.round, 'submitted_at', x.submitted_at))
            from lineups x where x.league_code = l.code), '[]'::json)
    )
    from leagues l where l.code = upper(trim(p_code));
$$;


-- The whole game, as last saved by the commissioner.
create or replace function fpga_get_state(p_code text)
returns json language sql security definer set search_path = public as $$
    select json_build_object('version', version, 'state', state)
    from leagues where code = upper(trim(p_code));
$$;


-- Send in (or replace) your lineup for a round.
create or replace function fpga_submit_lineup(
    p_code text, p_player integer, p_token text, p_season integer, p_event integer, p_round integer, p_lineup jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
    if not exists (select 1 from players where league_code = upper(trim(p_code))
                   and player_id = p_player and token = p_token) then
        raise exception 'Not a manager in this league';
    end if;
    insert into lineups (league_code, player_id, season, event_index, round, lineup, submitted_at)
        values (upper(trim(p_code)), p_player, p_season, p_event, p_round, p_lineup, now())
    on conflict (league_code, player_id) do update
        set season = excluded.season, event_index = excluded.event_index, round = excluded.round,
            lineup = excluded.lineup, submitted_at = now();
end $$;


-- Commissioner only: everyone's lineups, to play the round with.
create or replace function fpga_get_lineups(p_code text, p_token text)
returns json language plpgsql security definer set search_path = public as $$
begin
    if not exists (select 1 from leagues where code = upper(trim(p_code)) and commissioner_token = p_token) then
        raise exception 'Only the commissioner can do that';
    end if;
    return coalesce((select json_agg(json_build_object(
            'player_id', player_id, 'season', season, 'event_index', event_index,
            'round', round, 'lineup', lineup))
        from lineups where league_code = upper(trim(p_code))), '[]'::json);
end $$;


-- Commissioner only: upload the game. p_expected is the version you downloaded, so two
-- computers can't overwrite each other. Returns the new version number.
create or replace function fpga_save_state(p_code text, p_token text, p_state jsonb, p_expected integer)
returns integer language plpgsql security definer set search_path = public as $$
declare
    v_version integer;
begin
    update leagues set state = p_state, version = version + 1, status = 'active', updated_at = now()
        where code = upper(trim(p_code)) and commissioner_token = p_token and version = p_expected
        returning version into v_version;
    if v_version is null then
        if not exists (select 1 from leagues where code = upper(trim(p_code)) and commissioner_token = p_token) then
            raise exception 'Only the commissioner can do that';
        end if;
        raise exception 'The league was changed somewhere else - reload it first';
    end if;
    return v_version;
end $$;


revoke all on function fpga_create_league, fpga_join_league, fpga_league_info, fpga_get_state,
    fpga_submit_lineup, fpga_get_lineups, fpga_save_state from public;
grant execute on function fpga_create_league, fpga_join_league, fpga_league_info, fpga_get_state,
    fpga_submit_lineup, fpga_get_lineups, fpga_save_state to anon, authenticated;
