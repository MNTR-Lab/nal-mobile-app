-- Activity data is served only through the owner-checked admin API.
-- Keep service-role reads/writes for the existing audited backend.
revoke select on table public.admin_activity_log from anon, authenticated;
alter policy "Admins can view activity log" on public.admin_activity_log
using (
 lower(coalesce((select auth.jwt()->>'email'),'')) = 'brandon@thenationalarenaleague.com'
 and exists (
  select 1 from public.profiles
  where profiles.id = (select auth.uid())
  and profiles.role = 'admin'
  and profiles.account_status = 'active'
 )
);