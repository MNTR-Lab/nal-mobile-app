import { createClient } from 'npm:@supabase/supabase-js@2.57.0';
import { handleMondayWorkspace } from './workspace.ts';
const base = Deno.env.get('SUPABASE_URL')!;
const db = createClient(base, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {auth:{persistSession:false,autoRefreshToken:false}});
const origins = ['https://admin.nal-network.com'];
const ACTIVITY_START='2026-11-06T05:00:00.000Z';
const STAFF_ROLES=['verified','moderator','admin'];
const CONTENT_SECTIONS=['polls','friday','transactions','assets','connections','activity'];
const ALL_SECTIONS=[...CONTENT_SECTIONS,'staff'];
function validateSections(value:unknown){if(!Array.isArray(value)||value.some(k=>typeof k!=='string'||!CONTENT_SECTIONS.includes(k)))throw new HttpError('Choose valid dashboard sections.');return [...new Set(value)] as string[];}
function sectionsFor(user:any,profile:any,isSuper=false){if(isSuper)return ALL_SECTIONS;if(Array.isArray(user.app_metadata?.nal_network_sections))return user.app_metadata.nal_network_sections.filter((k:string)=>CONTENT_SECTIONS.includes(k));return profile.role==='admin'?CONTENT_SECTIONS.filter(k=>k!=='activity'):profile.role==='moderator'?['polls']:[];}
const STAFF_EMAIL_DOMAINS=['mntrlab.com','thenationalarenaleague.com'];
const isStaffEmail=(email:unknown)=>typeof email==='string'&&STAFF_EMAIL_DOMAINS.some(domain=>email.trim().toLowerCase().endsWith('@'+domain));
async function allUsers(){const users=[];for(let page=1;;page++){const r=await db.auth.admin.listUsers({page,perPage:1000});if(r.error)throw r.error;users.push(...r.data.users);if(r.data.users.length<1000)break;}return users;}
class HttpError extends Error { constructor(message:string, public status=400){super(message);} }
function check<T>(r:{data:T,error:any}):T {if(r.error)throw new Error(r.error.message);return r.data;}
function text(v:unknown,max=500){if(typeof v!=='string'||!v.trim()||v.length>max)throw new HttpError('Enter valid text (maximum '+max+' characters).');return v.trim();}
function pathFor(req:Request){return new URL(req.url).pathname.replace(/^.*\/nal-network-admin/,'')||'/me';}
function id(v:unknown){if(!/^\d+$/.test(String(v)))throw new HttpError('Invalid record ID.');return String(v);}
function web(v:unknown){if(!v)return null;const u=new URL(String(v));if(!['http:','https:'].includes(u.protocol))throw new HttpError('Use an http or https URL.');return u.href;}
async function monday(query:string,variables:Record<string,unknown>,asset=false){
 const token=asset?(Deno.env.get('FCF_MONDAY_API_TOKEN')||Deno.env.get('MONDAY_API_TOKEN')):Deno.env.get('MONDAY_API_TOKEN');
 if(!token)throw new HttpError('Monday connection is not configured.',503);
 const r=await fetch('https://api.monday.com/v2',{method:'POST',headers:{Authorization:token,'Content-Type':'application/json','API-Version':'2026-07'},body:JSON.stringify({query,variables}),signal:AbortSignal.timeout(25000)});
 const j=await r.json();if(!r.ok||j.errors?.length){console.error(JSON.stringify({event:'monday_error',status:r.status,errors:j.errors}));throw new HttpError('Monday could not complete the request. Please try again.',502);}return j.data;
}
async function boardItems(board:string,asset=false){
 const itemFields='id name group { id title } column_values { id text value }';
 let fields=itemFields;
 if(asset)for(let depth=0;depth<5;depth++)fields=itemFields+' subitems { '+fields+' }';
 const j=await monday(`query($ids:[ID!]!){boards(ids:$ids){id name items_page(limit:100){cursor items{${fields}}}}}`,{ids:[board]},asset);
 const b=j.boards?.[0];if(!b)throw new HttpError('The configured Monday account cannot access this board.',503);
 const items=[...b.items_page.items];let cursor=b.items_page.cursor;
 while(cursor){const n=await monday(`query($cursor:String!){next_items_page(limit:100,cursor:$cursor){cursor items{${fields}}}}`,{cursor},asset);items.push(...n.next_items_page.items);cursor=n.next_items_page.cursor;if(items.length>10000)throw new HttpError('Board is too large to load.',413);}
 const flattened:any[]=[];const seen=new Set<string>();
 const visit=(item:any,parent:any=null)=>{if(!seen.has(item.id)){seen.add(item.id);flattened.push({...item,group:item.group||parent?.group,parentName:parent?.name||''});}for(const sub of item.subitems||[])visit(sub,{...item,group:item.group||parent?.group});};
 for(const item of items)visit(item);
 return {name:b.name,items:flattened};
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
  if(!isStaffEmail(user.email))throw new HttpError('Admin access is restricted to @mntrlab.com and @thenationalarenaleague.com accounts.',403);
  const profile=check(await db.from('profiles').select('role,account_status,display_name').eq('id',user.id).maybeSingle());
  const invitation=user.app_metadata?.nal_network_invitation;
  if(pathFor(req)==='/staff/accept'&&req.method==='POST'){
   if(!invitation?.pending||!STAFF_ROLES.includes(invitation.role))throw new HttpError('There is no pending staff invitation for this account.',409);
   if(!user.email_confirmed_at)throw new HttpError('Verify your email using the invitation link first.',403);
   if(!profile||profile.account_status!=='active')throw new HttpError('This account is not active.',403);
   check(await db.from('profiles').update({role:invitation.role}).eq('id',user.id));
   const acceptedSections=Array.isArray(invitation.sections)?validateSections(invitation.sections):sectionsFor({app_metadata:{}},{role:invitation.role});
   const r=await db.auth.admin.updateUserById(user.id,{app_metadata:{...user.app_metadata,nal_network_sections:acceptedSections,nal_network_invitation:{...invitation,pending:false,accepted_at:new Date().toISOString()}}});if(r.error)throw r.error;
   await audit(user.id,'staff_invite_accepted','Staff invitation accepted',user.id);
   return reply({success:true,role:invitation.role,sections:acceptedSections});
  }
  if(pathFor(req)==='/me'&&invitation?.pending&&profile?.account_status==='active')return reply({invitation_pending:true,user:{id:user.id,email:user.email,name:profile.display_name,role:invitation.role},sections:[]});
  if(invitation?.pending)throw new HttpError('Accept your staff invitation before using the dashboard.',403);
  if(!profile||profile.account_status!=='active')throw new HttpError('Your account does not have staff access. Ask a super admin to assign access.',403);
  const owner=check(await db.from('nal_super_admins').select('user_id').eq('user_id',user.id).eq('is_active',true).maybeSingle());
  const isSuper=!!owner;const sections=sectionsFor(user,profile,isSuper);
  const url=new URL(req.url);const path=url.pathname.replace(/^.*\/nal-network-admin/,'')||'/me';
  const x=req.method==='POST'&&path!=='/assets/upload'?await req.json():{};
  if(req.method==='GET'&&path==='/me')return reply({user:{id:user.id,email:user.email,name:profile.display_name,role:isSuper?'super_admin':profile.role},sections,verified_only:sections.length===0});
  const required=path==='/polls'?'polls':path.startsWith('/friday/')?'friday':path.startsWith('/transactions')||path==='/roster'?'transactions':path.startsWith('/assets')?'assets':path==='/library'?'friday':path==='/connections'?'connections':path.startsWith('/staff')?'staff':path==='/activity'?'activity':null;
  if(!required||!sections.includes(required))throw new HttpError('You have not been assigned access to this section.',403);
  const workspace=await handleMondayWorkspace({path,req,x,url,headers,user,profile,isSuper,monday,boardItems,audit,check,text,id,web,HttpError});if(workspace)return workspace;
  if(path==='/polls'&&req.method==='GET'){
   const polls=check(await db.from('polls').select('*,poll_options(*)').in('status',['draft','active']).order('created_at',{ascending:false}).limit(100));
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
   const r=await fetch(base+'/functions/v1/nal-operations-api',{headers:{Authorization:'Bearer '+jwt},signal:AbortSignal.timeout(45000)});const j=await r.json();if(!r.ok||j.success===false)throw new HttpError('The transaction connection is unavailable. Please refresh to try again.',502);return reply(j);
  }
  if(path==='/activity'&&req.method==='GET')return reply({activity:check(await db.from('admin_activity_log').select('id,action_type,details,created_at').gte('created_at',ACTIVITY_START).order('created_at',{ascending:false}).limit(100))});
  if(!isSuper)throw new HttpError('Super admin access required.',403);
  if(path==='/roster'&&req.method==='POST'){
   const response=await fetch(base+'/functions/v1/nal-roster-admin',{method:'POST',headers:{Authorization:'Bearer '+jwt,'Content-Type':'application/json'},body:JSON.stringify(x),signal:AbortSignal.timeout(40000)});
   const data=await response.json();if(!response.ok||data.success===false)throw new HttpError(data.error||'Roster update failed',response.status);
   await audit(user.id,'roster_updated',`Player ${String(x.player?.firstName||'')} ${String(x.player?.lastName||'')}: ${String(x.rosterStatus||'')}`);
   return reply(data);
  }
  if(path==='/staff'&&req.method==='GET'){
   const p=[];for(let offset=0;;offset+=1000){const rows=check(await db.from('profiles').select('id,display_name,role,account_status').order('id').range(offset,offset+999));p.push(...rows);if(rows.length<1000)break;}
   const owners=check(await db.from('nal_super_admins').select('user_id').eq('is_active',true));
   // Only super admins receive account email addresses.
   const users=await allUsers();
   const byId=new Map(users.map(u=>[u.id,u]));
   return reply({members:p.filter(m=>isStaffEmail(byId.get(m.id)?.email)).sort((a,b)=>a.display_name.localeCompare(b.display_name)).map(m=>({...m,email:byId.get(m.id)?.email||'',eligible_by_domain:isStaffEmail(byId.get(m.id)?.email),sections:byId.get(m.id)?.app_metadata?.nal_network_invitation?.pending?(byId.get(m.id)?.app_metadata?.nal_network_invitation?.sections||sectionsFor(byId.get(m.id)||{},{role:byId.get(m.id)?.app_metadata?.nal_network_invitation?.role})):sectionsFor(byId.get(m.id)||{},m,owners.some(o=>o.user_id===m.id)),super_admin:owners.some(o=>o.user_id===m.id),invitation_pending:!!byId.get(m.id)?.app_metadata?.nal_network_invitation?.pending}))});
  }
  if(path==='/staff/invite'&&req.method==='POST'){
   const email=text(x.email,254).toLowerCase();if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw new HttpError('Enter a valid email address.');
   if(!isStaffEmail(email))throw new HttpError('Staff invitations are restricted to @mntrlab.com and @thenationalarenaleague.com accounts.',403);
   const role='verified';const invitedSections=validateSections(x.sections||[]);
   const delivery=x.delivery;if(!['email','link'].includes(delivery))throw new HttpError('Choose email or acceptance link.');
   const users=await allUsers();const existing=users.find(u=>u.email?.toLowerCase()===email);
   if(existing&&!x.resend)throw new HttpError('This email already has a Forum account. Use its Send access link option after verifying the account.',409);
   if(existing){const p=check(await db.from('profiles').select('role,account_status').eq('id',existing.id).maybeSingle());if(!p||!isStaffEmail(existing.email)||p.account_status!=='active')throw new HttpError('Only active accounts with an approved staff email domain can receive access links.',403);}
   const display_name=existing?undefined:text(x.display_name,30);if(display_name&&display_name.length<3)throw new HttpError('Use a display name of at least 3 characters.');
   let invited:any,properties:any;
   if(delivery==='email'){
    if(existing){const r=await db.auth.signInWithOtp({email,options:{shouldCreateUser:false,emailRedirectTo:'https://nal-network.com/admin/accept-invite'}});if(r.error)throw new HttpError('Email could not be sent. '+r.error.message+' You can generate an acceptance link instead.',502);invited=existing;}
    else{const r=await db.auth.admin.inviteUserByEmail(email,{redirectTo:'https://nal-network.com/admin/accept-invite',data:{display_name}});if(r.error||!r.data.user)throw new HttpError('Invitation email could not be sent. '+(r.error?.message||'Try again.')+' You can generate an acceptance link instead.',502);invited=r.data.user;}
   }else{
    const r=await db.auth.admin.generateLink({type:existing&&!existing.app_metadata?.nal_network_invitation?.pending?'magiclink':'invite',email,options:{data:display_name?{display_name}:undefined,redirectTo:'https://admin.nal-network.com/accept-invite'}});if(r.error)throw new HttpError('The acceptance link could not be generated. '+r.error.message,502);invited=r.data.user;properties=r.data.properties;
   }
   if(!existing){
    // New invitees stay verified, with no dashboard privileges, until acceptance.
    check(await db.from('profiles').update({role:'verified'}).eq('id',invited.id));
    const r=await db.auth.admin.updateUserById(invited.id,{app_metadata:{...invited.app_metadata,nal_network_sections:[],nal_network_invitation:{pending:true,role,sections:invitedSections,invited_by:user.id,invited_at:new Date().toISOString()}}});if(r.error)throw r.error;
   }
   await audit(user.id,'staff_invited',(existing?'Access link':'Staff invitation')+' '+(delivery==='email'?'emailed to ':'generated for ')+email,invited.id);
   const acceptance_url=properties?.hashed_token?'https://admin.nal-network.com/accept-invite?'+new URLSearchParams({token_hash:properties.hashed_token,type:properties.verification_type||'invite'}).toString():undefined;
   return reply({success:true,email,delivery,acceptance_url});
  }
  if(path==='/staff'&&req.method==='POST'){
   const target=String(x.user_id||'');if(target===user.id)throw new HttpError('You cannot change your own access.');
   const protectedUser=check(await db.from('nal_super_admins').select('user_id').eq('user_id',target).eq('is_active',true).maybeSingle());if(protectedUser)throw new HttpError('Super admin accounts are protected.');
   const selectedSections=validateSections(x.sections);
   const old=check(await db.from('profiles').select('role').eq('id',target).maybeSingle());if(!old)throw new HttpError('Staff account not found.',404);
   const targetUser=await db.auth.admin.getUserById(target);if(targetUser.error||!isStaffEmail(targetUser.data.user?.email))throw new HttpError('An @mntrlab.com or @thenationalarenaleague.com account is required.',403);
   const targetAccount=targetUser.data.user;const metadata={...targetAccount.app_metadata};
   if(metadata.nal_network_invitation?.pending)metadata.nal_network_invitation={...metadata.nal_network_invitation,sections:selectedSections};
   else metadata.nal_network_sections=selectedSections;
   const updated=await db.auth.admin.updateUserById(target,{app_metadata:metadata});if(updated.error)throw updated.error;
   await audit(user.id,'permissions_changed','Dashboard access: '+(selectedSections.join(', ')||'none'),target);return reply({success:true});
  }
  throw new HttpError('Not found',404);
 }catch(e){const status=e instanceof HttpError?e.status:500;console.error(JSON.stringify({event:'admin_api_error',status,message:e instanceof Error?e.message:'Unknown error'}));return reply({error:status===500?'The request could not be completed. Please try again.':(e as Error).message},status);}
});
