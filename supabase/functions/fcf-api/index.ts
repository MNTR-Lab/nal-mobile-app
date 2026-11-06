// Supabase Edge Function: fcf-api. Set verify_jwt=false; endpoint validates admin JWT itself.
import { createClient } from 'npm:@supabase/supabase-js@2.57.0';
const url=Deno.env.get('SUPABASE_URL')!,key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db=createClient(url,key,{auth:{autoRefreshToken:false,persistSession:false}});
const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Content-Type':'application/json'};
const reply=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers});
const fail=(message:string,status=400)=>reply({error:message},status);
async function admin(req:Request){
 const jwt=req.headers.get('Authorization')?.replace(/^Bearer\s+/i,'');if(!jwt)return false;
 const {data:{user},error}=await db.auth.getUser(jwt);if(error||!user)return false;
 const email=String(user.email||'').toLowerCase();
 if(!['@mntrlab.com','@thenationalarenaleague.com'].some(domain=>email.endsWith(domain))||user.app_metadata?.nal_network_invitation?.pending)return false;
 const {data:p}=await db.from('profiles').select('role,account_status').eq('id',user.id).single();if(p?.account_status!=='active')return false;
 const {data:owner}=await db.from('nal_super_admins').select('user_id').eq('user_id',user.id).eq('is_active',true).maybeSingle();if(owner)return true;
 const assigned=user.app_metadata?.nal_network_sections;
 return Array.isArray(assigned)?assigned.includes('friday'):p.role==='admin';
}
function directThumbnail(value:string|null){if(!value)return null;try{const u=new URL(value);if(u.hostname==='www.dropbox.com'||u.hostname==='dropbox.com'){u.searchParams.delete('dl');u.searchParams.set('raw','1');return u.toString()}return value}catch{return value}}
Deno.serve(async req=>{if(req.method==='OPTIONS')return new Response(null,{headers});try{const path=new URL(req.url).pathname.replace(/^.*\/fcf-api/,'');if(path.startsWith('/admin/')&&!(await admin(req)))return fail('NAL administrator access required',403);

if(path==='/admin/library'&&req.method==='GET'){
 const token=Deno.env.get('FCF_MONDAY_API_TOKEN') || Deno.env.get('MONDAY_API_TOKEN');
 if(!token)return fail('Set FCF_MONDAY_API_TOKEN to the MNTR+ Monday account token. Leave the shared MONDAY_API_TOKEN unchanged.',503);
 const query='query($ids:[ID!]!){boards(ids:$ids){items_page(limit:500){items{id name column_values{id text value}}}}}';
 const response=await fetch('https://api.monday.com/v2',{method:'POST',headers:{'Authorization':token,'Content-Type':'application/json','API-Version':'2024-10'},body:JSON.stringify({query,variables:{ids:['18436132233']}})});
 if(!response.ok)return fail('Monday API returned '+response.status,502);
 const result=await response.json();
 if(result.errors?.length)return fail('Monday API: '+result.errors.map((e:any)=>e.message).join('; '),502);
 const board=result.data?.boards?.[0];
 if(!board)return fail('The Fan Choice Friday connection cannot access Game Library board 18436132233. Set the dedicated FCF_MONDAY_API_TOKEN secret using the MNTR+ Monday account. Leave MONDAY_API_TOKEN unchanged; it is also used by NAL Operations.',502);
 const items=board.items_page?.items||[];
 const games=items.map((item:any)=>{
 const c=Object.fromEntries((item.column_values||[]).map((v:any)=>[v.id,v.text||'']));
 return {monday_id:item.id,matchup:item.name,game_date:c['date_mm89z94b']||null,thumbnail_url:directThumbnail(c['text_mm891a48']||null),preview_url:c['text_mm897kk8']||null,description:c['long_text_mm896fe9']||'',full_game_url:c['text_mm89hvh3']||null,season:c['numeric_mm8994m2']||null,game_status:c['color_mm89fnxk']||'',highlight_status:c['color_mm89r0bf']||''};
 }).filter((g:any)=>g.game_status==='Approved'&&g.highlight_status==='Approved');
 return reply({games,count:games.length});
}

if(path==='/poll'&&req.method==='GET'){const {data:poll,error}=await db.from('fcf_polls').select('*').in('status',['active','closed','published']).order('created_at',{ascending:false}).limit(1).maybeSingle();if(error)throw error;if(!poll)return reply({poll:null,options:[]});const {data:options}=await db.from('fcf_options').select('*').eq('poll_id',poll.id).order('display_order');return reply({poll,options})}
if(path==='/vote'&&req.method==='POST'){const {poll_id,option_id,token}=await req.json();if(!Number.isSafeInteger(poll_id)||!Number.isSafeInteger(option_id)||typeof token!=='string'||!/^[0-9a-f-]{36}$/i.test(token))return fail('Invalid vote');const {data:p}=await db.from('fcf_polls').select('*').eq('id',poll_id).maybeSingle();const now=Date.now();if(!p||p.status!=='active'||(p.opens_at&&Date.parse(p.opens_at)>now)||(p.closes_at&&Date.parse(p.closes_at)<=now))return fail('Voting is not open',403);const {data:o}=await db.from('fcf_options').select('id').eq('id',option_id).eq('poll_id',poll_id).maybeSingle();if(!o)return fail('Invalid game selection');const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token));const hash=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');const {error}=await db.from('fcf_votes').insert({poll_id,option_id,voter_token_hash:hash});if(error?.code==='23505')return fail('You have already voted in this poll',409);if(error)throw error;return reply({success:true})}
if(path==='/results'&&req.method==='POST'){
 const {poll_id,token}=await req.json().catch(()=>({}));
 if(!Number.isSafeInteger(poll_id)||typeof token!=='string'||!/^[0-9a-f-]{36}$/i.test(token))return fail('Invalid request',400);
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token));
 const hash=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
 const {data:verified}=await db.from('fcf_votes').select('id').eq('poll_id',poll_id).eq('voter_token_hash',hash).maybeSingle();
 if(!verified)return fail('Results are available after you vote.',403);
 const {data:opts,error:oe}=await db.from('fcf_options').select('id,matchup').eq('poll_id',poll_id).order('display_order');
 if(oe)throw oe;
 const {data:votes,error:ve}=await db.from('fcf_votes').select('option_id').eq('poll_id',poll_id);
 if(ve)throw ve;
 const total=(votes||[]).length;
 const results=(opts||[]).map((o:any)=>({id:o.id,matchup:o.matchup,percentage:total?Math.round((votes||[]).filter((v:any)=>v.option_id===o.id).length*1000/total)/10:0})).sort((a:any,b:any)=>b.percentage-a.percentage);
 return reply({results:results.map((o:any,i:number)=>({...o,rank:i+1}))});
}
if(path==='/admin/polls'&&req.method==='GET'){
 const {data:polls,error}=await db.from('fcf_polls').select('*').order('created_at',{ascending:false});
 if(error)throw error;return reply({polls});
}
if(path==='/admin/archive'&&req.method==='POST'){
 const {id}=await req.json();if(!Number.isSafeInteger(id))return fail('Invalid poll');
 const {data,error}=await db.from('fcf_polls').update({status:'closed'}).eq('id',id).select('id').maybeSingle();
 if(error)throw error;if(!data)return fail('Poll not found',404);return reply({success:true,id});
}
if(path==='/admin/poll'&&req.method==='GET'){
 const id=new URL(req.url).searchParams.get('id');
 if(id&&!/^[1-9]\d*$/.test(id))return fail('Invalid poll');
 let query=db.from('fcf_polls').select('*');
 if(id)query=query.eq('id',Number(id));
 const {data:poll,error}=await query.order('created_at',{ascending:false}).limit(1).maybeSingle();
 if(error)throw error;if(!poll)return reply({poll:null,options:[],results:[]});
 const {data:options,error:oe}=await db.from('fcf_options').select('*').eq('poll_id',poll.id).order('display_order');if(oe)throw oe;
 // Paginate so archive totals remain correct above the default API row limit.
 const counts=new Map<number,number>();
 for(let offset=0;;offset+=1000){const {data:votes,error:ve}=await db.from('fcf_votes').select('id,option_id').eq('poll_id',poll.id).order('id').range(offset,offset+999);if(ve)throw ve;for(const v of votes||[])counts.set(v.option_id,(counts.get(v.option_id)||0)+1);if((votes||[]).length<1000)break;}
 return reply({poll,options,results:(options||[]).map(o=>({matchup:o.matchup,votes:counts.get(o.id)||0}))});
}
if(path==='/admin/poll'&&req.method==='POST'){
 const x=await req.json();
 if(!x.question||!Array.isArray(x.games)||x.games.length<2||x.games.length>4||x.games.some((g:any)=>!g.matchup?.trim()))return fail('Provide a question and 2–4 games');
 if(!['draft','active','closed','published'].includes(x.status))return fail('Invalid status');
 if([x.opens_at,x.closes_at].some(v=>v&&!Number.isFinite(Date.parse(v))))return fail('Invalid date');
 if(x.closes_at&&x.opens_at&&Date.parse(x.closes_at)<=Date.parse(x.opens_at))return fail('Closing time must follow opening time');
 const payload={title:x.title||'Fan Choice Friday',question:x.question,status:x.status,opens_at:x.opens_at||null,closes_at:x.closes_at||null};
 let id=x.id;
 if(id){
  if(!Number.isSafeInteger(id))return fail('Invalid poll');
  const {data:existing,error:pe}=await db.from('fcf_polls').select('id').eq('id',id).maybeSingle();if(pe)throw pe;if(!existing)return fail('Poll not found',404);
  const {count,error:ce}=await db.from('fcf_votes').select('*',{count:'exact',head:true}).eq('poll_id',id);if(ce)throw ce;
  if(count){
   const {data:opts,error:oe}=await db.from('fcf_options').select('*').eq('poll_id',id).order('display_order');if(oe)throw oe;
   const same=opts?.length===x.games.length&&opts.every((o:any,i:number)=>['matchup','game_date','thumbnail_url','preview_url'].every(k=>(o[k]||null)===(x.games[i][k]||null)));
   if(!same)return fail('This poll has votes. Create a new poll to change the game choices.',409);
   const {error}=await db.from('fcf_polls').update(payload).eq('id',id);if(error)throw error;return reply({success:true,id});
  }
  // Never modify game rows on an active poll; close it first to stop voting.
  const {data:p}=await db.from('fcf_polls').select('status').eq('id',id).single();
  if(p?.status==='active')return fail('Close this poll before changing its choices.',409);
  const {error:de}=await db.from('fcf_options').delete().eq('poll_id',id);if(de)throw de;
 }else{
  const {data,error}=await db.from('fcf_polls').insert({...payload,status:'draft'}).select('id').single();if(error)throw error;id=data.id;
 }
 const {error}=await db.from('fcf_options').insert(x.games.map((g:any,i:number)=>({poll_id:id,matchup:g.matchup,game_date:g.game_date||null,thumbnail_url:directThumbnail(g.thumbnail_url||null),preview_url:g.preview_url||null,display_order:i})));
 if(error)throw error;
 const {error:ue}=await db.from('fcf_polls').update(payload).eq('id',id);if(ue)throw ue;
 return reply({success:true,id});
}
return fail('Not found',404)}catch(e){console.error(e);return fail('Unexpected server error',500)}});


