
create table public.player_chat_rooms (
 id uuid primary key default gen_random_uuid(), scope text not null check(length(scope) between 1 and 180),
 title text not null check(length(trim(title)) between 1 and 120), opened_at timestamptz not null default now(),
 closes_at timestamptz not null, closed_at timestamptz, created_by uuid references auth.users(id) on delete set null
);
create unique index player_chat_one_open_scope on public.player_chat_rooms(scope) where closed_at is null;
create table public.player_chat_messages (
 id bigint generated always as identity primary key, room_id uuid not null references public.player_chat_rooms(id) on delete cascade,
 user_id uuid references auth.users(id) on delete set null, display_name text not null,
 body text not null check(length(trim(body)) between 1 and 500), created_at timestamptz not null default now(),
 removed_at timestamptz
);
create index player_chat_messages_room_time on public.player_chat_messages(room_id,created_at desc);
create index player_chat_messages_user_time on public.player_chat_messages(user_id,created_at desc);
create table public.player_chat_mutes (
 room_id uuid references public.player_chat_rooms(id) on delete cascade,
 user_id uuid references auth.users(id) on delete cascade, primary key(room_id,user_id)
);
alter table public.player_chat_rooms enable row level security;
alter table public.player_chat_messages enable row level security;
alter table public.player_chat_mutes enable row level security;
create policy chat_rooms_read on public.player_chat_rooms for select to anon,authenticated using(true);
create policy chat_messages_read on public.player_chat_messages for select to anon,authenticated using(removed_at is null);
grant select on public.player_chat_rooms,public.player_chat_messages to anon,authenticated;
revoke all on public.player_chat_mutes from anon,authenticated;
revoke insert,update,delete on public.player_chat_rooms,public.player_chat_messages from anon,authenticated;

create function public.player_chat_manage(p_scope text,p_title text default null,p_hours integer default 4)
returns uuid language plpgsql security definer set search_path=public,pg_temp as $$
declare rid uuid;
begin
 if not exists(select 1 from profiles where id=auth.uid() and role in ('admin','moderator') and account_status='active') then raise exception 'Admin access required'; end if;
 if p_scope <> 'live-channel' and p_scope !~ '^game:[A-Za-z0-9:_-]{1,160}$' then raise exception 'Invalid event'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_scope,0));
 update player_chat_rooms set closed_at=now() where scope=p_scope and closed_at is null;
 if p_title is null then return null; end if;
 if length(trim(p_title)) not between 1 and 120 or p_hours not between 1 and 12 then raise exception 'Enter an event title and duration from 1 to 12 hours'; end if;
 insert into player_chat_rooms(scope,title,closes_at,created_by) values(p_scope,trim(p_title),now()+make_interval(hours=>p_hours),auth.uid()) returning id into rid;
 return rid;
end $$;
create function public.player_chat_post(p_room uuid,p_body text)
returns void language plpgsql security definer set search_path=public,pg_temp as $$
declare author text;
begin
 if auth.uid() is null then raise exception 'Sign in to join the chat'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text,1));
 select coalesce(nullif(trim(display_name),''),'NAL Fan') into author from profiles where id=auth.uid() and account_status='active';
 if author is null then raise exception 'An active fan account is required'; end if;
 if not exists(select 1 from player_chat_rooms where id=p_room and closed_at is null and closes_at>now()) then raise exception 'This event chat is closed'; end if;
 if exists(select 1 from player_chat_mutes where room_id=p_room and user_id=auth.uid()) then raise exception 'You are muted for this event'; end if;
 if exists(select 1 from player_chat_messages where user_id=auth.uid() and created_at>now()-interval '5 seconds') then raise exception 'Please wait five seconds between messages'; end if;
 if length(trim(p_body)) not between 1 and 500 then raise exception 'Messages must contain 1–500 characters'; end if;
 insert into player_chat_messages(room_id,user_id,display_name,body) values(p_room,auth.uid(),left(author,80),trim(p_body));
end $$;
create function public.player_chat_moderate(p_message bigint,p_mute boolean default false)
returns void language plpgsql security definer set search_path=public,pg_temp as $$
declare msg player_chat_messages;
begin
 if not exists(select 1 from profiles where id=auth.uid() and role in ('admin','moderator') and account_status='active') then raise exception 'Admin access required'; end if;
 select * into msg from player_chat_messages where id=p_message;
 if not found then raise exception 'Message not found'; end if;
 update player_chat_messages set removed_at=now() where id=p_message;
 if p_mute and msg.user_id is not null then insert into player_chat_mutes(room_id,user_id) values(msg.room_id,msg.user_id) on conflict do nothing; end if;
end $$;
revoke all on function public.player_chat_manage(text,text,integer),public.player_chat_post(uuid,text),public.player_chat_moderate(bigint,boolean) from public,anon;
grant execute on function public.player_chat_manage(text,text,integer),public.player_chat_post(uuid,text),public.player_chat_moderate(bigint,boolean) to authenticated;
alter publication supabase_realtime add table public.player_chat_rooms,public.player_chat_messages;
