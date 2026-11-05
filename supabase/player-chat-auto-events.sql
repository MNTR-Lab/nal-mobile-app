
alter table public.player_chat_rooms add column event_key text, add column live_verified_until timestamptz;
create unique index player_chat_event_identity on public.player_chat_rooms(scope,event_key);
create function public.player_chat_sync_event(p_scope text,p_event_key text,p_title text,p_end timestamptz)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare room player_chat_rooms;
begin
 if p_scope <> 'live-channel' and p_scope !~ '^game:[0-9]+::[0-9]+$' then raise exception 'Invalid event scope'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_scope,0));
 if p_event_key is null then
  update player_chat_rooms set closed_at=now(),live_verified_until=now() where scope=p_scope and closed_at is null;
  return null;
 end if;
 if p_end is null or p_end<=now() or p_event_key !~ '^[0-9]+::[0-9]+$' then raise exception 'Event is not live'; end if;
 update player_chat_rooms set closed_at=now(),live_verified_until=now() where scope=p_scope and closed_at is null and event_key is distinct from p_event_key;
 insert into player_chat_rooms(scope,event_key,title,closes_at,live_verified_until)
 values(p_scope,p_event_key,left(coalesce(nullif(trim(p_title),''),'NAL Live Event'),120),p_end,least(p_end,now()+interval '45 seconds'))
 on conflict(scope,event_key) do update set title=excluded.title,closes_at=excluded.closes_at,closed_at=null,live_verified_until=excluded.live_verified_until
 returning * into room;
 return jsonb_build_object('id',room.id,'title',room.title,'closes_at',room.closes_at,'live_verified_until',room.live_verified_until,'event_key',room.event_key);
end $$;
revoke all on function public.player_chat_sync_event(text,text,text,timestamptz) from public,anon,authenticated;
grant execute on function public.player_chat_sync_event(text,text,text,timestamptz) to service_role;
revoke execute on function public.player_chat_manage(text,text,integer) from authenticated;
update public.player_chat_rooms set closed_at=now() where event_key is null and closed_at is null;

CREATE OR REPLACE FUNCTION public.player_chat_post(p_room uuid, p_body text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
declare author text;
begin
 if auth.uid() is null then raise exception 'Sign in to join the chat'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text,1));
 select coalesce(nullif(trim(display_name),''),'NAL Fan') into author from profiles where id=auth.uid() and account_status='active';
 if author is null then raise exception 'An active fan account is required'; end if;
 if not exists(select 1 from player_chat_rooms where id=p_room and closed_at is null and closes_at>now() and live_verified_until>now() and event_key is not null) then raise exception 'This event chat is closed'; end if;
 if exists(select 1 from player_chat_mutes where room_id=p_room and user_id=auth.uid()) then raise exception 'You are muted for this event'; end if;
 if exists(select 1 from player_chat_messages where user_id=auth.uid() and created_at>now()-interval '5 seconds') then raise exception 'Please wait five seconds between messages'; end if;
 if length(trim(p_body)) not between 1 and 500 then raise exception 'Messages must contain 1–500 characters'; end if;
 insert into player_chat_messages(room_id,user_id,display_name,body) values(p_room,auth.uid(),left(author,80),trim(p_body));
end $function$
