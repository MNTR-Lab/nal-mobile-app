import { createClient } from 'npm:@supabase/supabase-js@2.57.0';
const base = Deno.env.get('SUPABASE_URL')!;
const db = createClient(base, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {auth:{persistSession:false,autoRefreshToken:false}});
const origins = ['https://admin.nal-network.com'];
class HttpError extends Error { constructor(message:string, public status=400){super(message);} }
function check<T>(r:{data:T,error:any}):T {if(r.error)throw new Error(r.error.message);return r.data;}
function text(v:unknown,max=500){if(typeof v!=='string'||!v.trim()||v.length>max)throw new HttpError('Enter valid text (maximum '+max+' characters).');return v.trim();}
function id(v:unknown){if(!/^\d+$/.test(String(v)))throw new HttpError('Invalid record ID.');return String(v);}
function web(v:unknown){if(!v)return null;const u=new URL(String(v));if(!['http:','https:'].includes(u.protocol))throw new HttpError('Use an http or https URL.');return u.href;}
async function monday(query:string,variables:Record<string,unknown>,asset=false){
 const token=asset?(Deno.env.get('FCF_MONDAY_API_TOKEN')||Deno.env.get('MONDAY_API_TOKEN')):Deno.env.get('MONDAY_API_TOKEN');
 if(!token)throw new HttpError('Monday connection is not configured.',503);
 const r=await fetch('https://api.monday.com/v2',{method:'POST',headers:{Authorization:token,'Content-Type':'application/json','API-Version':'2026-07'},body:JSON.stringify({query,variables}),signal:AbortSignal.timeout(25000)});
 const j=await r.json();if(!r.ok||j.errors?.length){console.error(JSON.stringify({event:'monday_error',status:r.status,errors:j.errors}));throw new HttpError('Monday could not complete the request. Please try again.',502);}return j.data;
}
async function boardItems(board:string,asset=false){
 const fields='id name group { id title } column_values { id text value }';
 const j=await monday(`query($ids:[ID!]!){boards(ids:$ids){id name items_page(limit:100){cursor items{${fields}}}}}`,{ids:[board]},asset);
 const b=j.boards?.[0];if(!b)throw new HttpError('The configured Monday account cannot access this board.',503);
 const items=[...b.items_page.items];let cursor=b.items_page.cursor;
 while(cursor){const n=await monday(`query($cursor:String!){next_items_page(limit:100,cursor:$cursor){cursor items{${fields}}}}`,{cursor},asset);items.push(...n.next_items_page.items);cursor=n.next_items_page.cursor;if(items.length>10000)throw new HttpError('Board is too large to load.',413);}
 return {name:b.name,items};
}
const cv=(i:any,k:string)=>i.column_values?.find((c:any)=>c.id===k)?.text||'';
async function audit(user:string,action:string,details:string,target:string|null=null){check(await db.from('admin_activity_log').insert({admin_user_id:user,target_user_id:target,action_type:action,details}));}
Deno.serve(async req=>{
 const origin=req.headers.get('Origin');const headers:Record<string,string>={'Content-Type':'application/json','Cache-Control':'no-store','Vary':'Origin','Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS'};
 if(origin&&origins.includes(origin))headers['Access-Control-Allow-Origin']=origin;
 const reply=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers});
 if(origin&&!origins.includes(origin))return reply({error:'Origin not allowed'},403);
 if(req.method==='OPTIONS')return new Response(null,{headers});
 try{
  if(!['GET','POST'].includes(req.method))throw new HttpError('Method not allowed',405);
  const jwt=req.headers.get('Authorization')?.replace(/^Bearer\s+/i,'');if(!jwt)throw new HttpError('Sign in with your Forum account.',401);
  const {data:{user},error}=await db.auth.getUser(jwt);if(error||!user)throw new HttpError('Your session has expired. Sign in again.',401);
  const profile=check(await db.from('profiles').select('role,account_status,display_name').eq('id',user.id).maybeSingle());
  if(!profile||profile.account_status!=='active'||!['admin','moderator'].includes(profile.role))throw new HttpError('Your account does not have staff access. Ask a super admin to assign access.',403);
  const owner=check(await db.from('nal_super_admins').select('user_id').eq('user_id',user.id).eq('is_active',true).maybeSingle());
  const isSuper=!!owner;const isAdmin=profile.role==='admin';
  const url=new URL(req.url);const path=url.pathname.replace(/^.*\/nal-network-admin/,'')||'/me';
  const x=req.method==='POST'?await req.json():{};
  if(req.method==='GET'&&path==='/me')return reply({user:{id:user.id,email:user.email,name:profile.display_name,role:isSuper?'super_admin':profile.role},sections:isAdmin?['polls','friday','transactions','assets','connections',...(isSuper?['staff','activity']:[])]:['polls']});
  if(path==='/polls'&&req.method==='GET'){
   const polls=check(await db.from('polls').select('*,poll_options(*)').order('created_at',{ascending:false}).limit(100));
   const counts=new Map<string,number>();
   const ids=polls.map(p=>p.id);
   if(ids.length)for(let offset=0;;offset+=1000){
    const rows=check(await db.from('poll_votes').select('id,option_id').in('poll_id',ids).order('id').range(offset,offset+999));
    for(const v of rows)counts.set(String(v.option_id),(counts.get(String(v.option_id))||0)+1);
    if(rows.length<1000)break;
   }
   const results=polls.map(p=>({...p,options:p.poll_options.map((o:any)=>({...o,votes:counts.get(String(o.id))||0})).sort((a:any,b:any)=>a.display_order-b.display_order),poll_options:undefined}));
   return reply({polls:results});
  }
  if(path==='/polls'&&req.method==='POST'){
   if(x.action==='create'){
    const question=text(x.question);if(!Array.isArray(x.options)||x.options.length<2||x.options.length>20)throw new HttpError('Provide 2–20 choices.');
    const options=x.options.map((o:any,i:number)=>({option_name:text(o.option_name,120),image_url:web(o.image_url),display_order:i}));
    const status=x.status==='active'?'active':'draft';
    const p=check(await db.from('polls').insert({question,status:'draft'}).select('id').single());
    try{check(await db.from('poll_options').insert(options.map((o:any)=>({...o,poll_id:p.id}))));if(status==='active')check(await db.from('polls').update({status}).eq('id',p.id));}catch(e){await db.from('polls').delete().eq('id',p.id);throw e;}
    await audit(user.id,'poll_created',`Poll ${p.id}: ${question} (${status})`);return reply({success:true,id:p.id});
   }
   if(x.action==='status'){
    if(!['draft','active','closed'].includes(x.status))throw new HttpError('Invalid poll status.');
    const p=check(await db.from('polls').update({status:x.status}).eq('id',id(x.id)).select('id').maybeSingle());if(!p)throw new HttpError('Poll not found',404);
    await audit(user.id,'poll_status_changed',`Poll ${p.id}: ${x.status}`);return reply({success:true});
   }
   throw new HttpError('Unknown poll action.');
  }
  if(!isAdmin)throw new HttpError('Administrator access required.',403);
  if(path.startsWith('/friday/admin/')){
   const suffix=path.slice('/friday'.length);
   const allowed=(req.method==='GET'&&['/admin/polls','/admin/poll','/admin/library'].includes(suffix))||(req.method==='POST'&&['/admin/poll','/admin/archive'].includes(suffix));
   if(!allowed)throw new HttpError('Not found',404);
   const response=await fetch(base+'/functions/v1/fcf-api'+suffix+url.search,{method:req.method,headers:{Authorization:'Bearer '+jwt,'Content-Type':'application/json'},...(req.method==='POST'?{body:JSON.stringify(x)}:{}),signal:AbortSignal.timeout(45000)});
   const data=await response.json();if(!response.ok||data.error)throw new HttpError(data.error||'Fan Choice Friday request failed',response.status);
   if(req.method==='POST')await audit(user.id,suffix==='/admin/archive'?'fcf_poll_closed':'fcf_poll_updated','Fan Choice Friday poll '+String(data.id||x.id||''));
   return reply(data);
  }
  if(path==='/transactions'&&req.method==='GET'){
   const r=await fetch(base+'/functions/v1/nal-operations-api',{headers:{Authorization:'Bearer '+jwt},signal:AbortSignal.timeout(45000)});const j=await r.json();if(!r.ok||j.success===false)throw new HttpError('The transaction connection is unavailable. Try again or open its Monday board.',502);return reply(j);
  }
  if(path==='/assets'&&req.method==='GET'){
   const b=await boardItems('18437455062',true);
   return reply({board:b.name,items:b.items.map((i:any)=>({id:i.id,name:i.name,group:i.group?.title||'',details:cv(i,'text_mm8jjxt8'),usage:cv(i,'dropdown_mm8j7gcm'),date:cv(i,'date_mm8j3gz6'),link:(()=>{try{return JSON.parse(i.column_values.find((c:any)=>c.id==='link_mm8jkx6a')?.value||'{}').url||'';}catch{return '';}})(),attachment:cv(i,'file_mm8jsk7z'),url:'https://ai-apparel-group-inc.monday.com/boards/18437455062/pulses/'+i.id}))});
  }
  if(path==='/assets'&&req.method==='POST'){
   const itemId=id(x.id);const b=await monday('query($ids:[ID!]!){items(ids:$ids){id board{id}}}',{ids:[itemId]},true);if(b.items?.[0]?.board?.id!=='18437455062')throw new HttpError('Asset not found.',404);
   const usage=Array.isArray(x.usage)?x.usage:[];if(usage.some((s:string)=>!['Free for use','Website','Social media'].includes(s)))throw new HttpError('Invalid usage.');
   if(x.date&&!/^\d{4}-\d{2}-\d{2}$/.test(x.date))throw new HttpError('Invalid date.');
   const link=web(x.link);const values={text_mm8jjxt8:typeof x.details==='string'?x.details.slice(0,10000):'',dropdown_mm8j7gcm:{labels:usage},date_mm8j3gz6:x.date?{date:x.date}:{},link_mm8jkx6a:link?{url:link,text:'Open asset usage'}:{}};
   await monday('mutation($board:ID!,$item:ID!,$values:JSON!){change_multiple_column_values(board_id:$board,item_id:$item,column_values:$values){id}}',{board:'18437455062',item:itemId,values:JSON.stringify(values)},true);
   await audit(user.id,'asset_updated','Digital Asset Management item '+itemId);return reply({success:true});
  }
  if(!isSuper)throw new HttpError('Super admin access required.',403);
  if(path==='/roster'&&req.method==='POST'){
   const response=await fetch(base+'/functions/v1/nal-roster-admin',{method:'POST',headers:{Authorization:'Bearer '+jwt,'Content-Type':'application/json'},body:JSON.stringify(x),signal:AbortSignal.timeout(40000)});
   const data=await response.json();if(!response.ok||data.success===false)throw new HttpError(data.error||'Roster update failed',response.status);
   await audit(user.id,'roster_updated',`Player ${String(x.player?.firstName||'')} ${String(x.player?.lastName||'')}: ${String(x.rosterStatus||'')}`);
   return reply(data);
  }
  if(path==='/staff'&&req.method==='GET'){
   const p=check(await db.from('profiles').select('id,display_name,role,account_status').order('display_name'));
   const owners=check(await db.from('nal_super_admins').select('user_id').eq('is_active',true));
   // Only super admins receive account email addresses.
   const users=[];for(let page=1;;page++){const r=await db.auth.admin.listUsers({page,perPage:1000});if(r.error)throw r.error;users.push(...r.data.users);if(r.data.users.length<1000)break;}
   return reply({members:p.map(m=>({...m,email:users.find(u=>u.id===m.id)?.email||'',super_admin:owners.some(o=>o.user_id===m.id)}))});
  }
  if(path==='/staff'&&req.method==='POST'){
   const target=String(x.user_id||'');if(target===user.id)throw new HttpError('You cannot change your own access.');
   const protectedUser=check(await db.from('nal_super_admins').select('user_id').eq('user_id',target).eq('is_active',true).maybeSingle());if(protectedUser)throw new HttpError('Super admin accounts are protected.');
   if(!['fan','verified','vip','moderator','admin'].includes(x.role))throw new HttpError('Invalid role.');
   const old=check(await db.from('profiles').select('role').eq('id',target).maybeSingle());if(!old)throw new HttpError('Account not found.',404);
   check(await db.from('profiles').update({role:x.role}).eq('id',target));await audit(user.id,'role_changed',`Role ${old.role} → ${x.role}`,target);return reply({success:true});
  }
  if(path==='/activity'&&req.method==='GET')return reply({activity:check(await db.from('admin_activity_log').select('id,action_type,details,created_at').order('created_at',{ascending:false}).limit(100))});
  throw new HttpError('Not found',404);
 }catch(e){const status=e instanceof HttpError?e.status:500;console.error(JSON.stringify({event:'admin_api_error',status,message:e instanceof Error?e.message:'Unknown error'}));return reply({error:status===500?'The request could not be completed. Please try again.':(e as Error).message},status);}
});
