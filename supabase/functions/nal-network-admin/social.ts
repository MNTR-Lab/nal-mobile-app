// Shared Monday board; the admin dashboard is strictly scoped to Organization=NAL.
const SOCIAL_BOARD='18437085764';
const SC={organization:'text_mm8gvkrn',campaign:'text_mm8g21rg',publish:'text_mm8gr6p',platform:'text_mm8g9k8p',caption:'long_text_mm8gwyqm',destination:'text_mm8gq1vr',assetType:'text_mm8gcsak',media:'file_mm8gwyhd',notes:'long_text_mm8gcy4k',status:'color_mm8g5tag',assigned:'text_mm8gnpw3',role:'text_mm8g310x',published:'text_mm8gxxm9',visible:'text_mm8g5dp2',date:'date_mm8gkjks',asset:'link_mm8wqjxz'};
function socialValue(item:any,id:string){return item.column_values?.find((v:any)=>v.id===id)?.text||'';}
function socialNal(item:any){return socialValue(item,SC.organization).trim().toLowerCase()==='nal';}
function socialLabels(board:any){let s=board.columns.find((v:any)=>v.id===SC.status)?.settings||{};if(typeof s==='string')s=JSON.parse(s);return Array.isArray(s.labels)?s.labels.filter((v:any)=>!v.is_deactivated).map((v:any)=>({id:v.id,label:v.label})):Object.entries(s.labels||{}).map(([id,label])=>({id:Number(id),label}));}
export function socialDateTime(value:unknown){
 if(!value)return '';
 const s=String(value).trim();let m=s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2}):(\d{2})(?:\s*(AM|PM))?(?:\s*(?:ET|EST|EDT))?$/i);
 if(!m){const us=s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?(?:\s*(?:ET|EST|EDT))?$/i);if(us)m=[us[0],us[3].length===2?'20'+us[3]:us[3],us[1].padStart(2,'0'),us[2].padStart(2,'0'),us[4],us[5],us[6]] as RegExpMatchArray;}
 if(!m)return '';
 let hour=Number(m[4]);const minute=Number(m[5]);if(m[6]){if(hour<1||hour>12)return '';hour=hour%12+(m[6].toUpperCase()==='PM'?12:0);}
 const day=m[1]+'-'+m[2]+'-'+m[3];if(hour>23||minute>59||!Number.isFinite(Date.parse(day+'T00:00:00Z'))||new Date(day+'T00:00:00Z').toISOString().slice(0,10)!==day)return '';
 return day+'T'+String(hour).padStart(2,'0')+':'+m[5];
}
function socialLink(item:any,id:string){try{const value=item.column_values.find((v:any)=>v.id===id);return JSON.parse(value?.value||'{}').url||(/^https?:\/\//.test(value?.text||'')?value.text:'');}catch{return '';}}
export function socialNormalize(item:any){return {id:item.id,title:item.name,updated_at:item.updated_at,publish_at_et:socialDateTime(socialValue(item,SC.publish)),publish_at_original:socialValue(item,SC.publish),platforms:socialValue(item,SC.platform).split(',').map((v:string)=>v.trim()).filter(Boolean),status:socialValue(item,SC.status)||'Draft',campaign:socialValue(item,SC.campaign),caption:socialValue(item,SC.caption),assigned_to:socialValue(item,SC.assigned),media_url:socialLink(item,SC.asset),destination_url:socialValue(item,SC.destination),notes:socialValue(item,SC.notes),published_url:socialValue(item,SC.published),asset_type:socialValue(item,SC.assetType)||'Image',content_role:socialValue(item,SC.role)||'Main Post'};}
async function socialBoard(c:any){const j=await c.monday('query($ids:[ID!]!){boards(ids:$ids){id name columns{id title type settings}}}',{ids:[SOCIAL_BOARD]},true);const b=j.boards?.[0];if(!b)throw new c.HttpError('The social media board connection is unavailable.',503);return b;}
async function socialItem(c:any,id:any,files=false){const fields=files?' ... on FileValue {files{... on FileAssetValue {asset_id name asset{id public_url file_extension}}}}':'';const j=await c.monday(`query($ids:[ID!]!){items(ids:$ids){id name updated_at state board{id} group{id} column_values{id text value ${fields}}}}`,{ids:[c.id(id)]},true);const p=j.items?.[0];if(!p||p.state==='archived'||String(p.board?.id)!==SOCIAL_BOARD||!socialNal(p))throw new c.HttpError('NAL social post not found.',404);return p;}
export async function handleSocial(c:any):Promise<Response|null>{
 const {path,req,x}=c;if(!path.startsWith('/social'))return null;const reply=(v:any)=>new Response(JSON.stringify(v),{headers:c.headers});
 if(path==='/social'&&req.method==='GET'){
  const b=await socialBoard(c);let j=await c.monday('query($ids:[ID!]!){boards(ids:$ids){items_page(limit:500){cursor items{id name updated_at column_values{id text value}}}}}',{ids:[SOCIAL_BOARD]},true);let page=j.boards?.[0]?.items_page;if(!page)throw new c.HttpError('The social schedule could not load.',502);let items=[...page.items];
  while(page.cursor){j=await c.monday('query($cursor:String!){next_items_page(cursor:$cursor,limit:500){cursor items{id name updated_at column_values{id text value}}}}',{cursor:page.cursor},true);page=j.next_items_page;if(!page||items.length>=10000)throw new c.HttpError('The social schedule could not load completely.',502);items.push(...page.items);}
  const posts=items.filter(socialNal).map(socialNormalize),order=['Draft','Pending Review','Approved','Scheduled','Posted','Rejected'];const labels=socialLabels(b).map((v:any)=>v.label);return reply({configured:true,posts,statuses:order.filter(s=>labels.includes(s)).concat(labels.filter((s:string)=>!order.includes(s))),platforms:[...new Set(posts.flatMap((p:any)=>p.platforms))],board_id:SOCIAL_BOARD});
 }
 if(path==='/social'&&req.method==='POST'){
  if(x.action&&x.action!=='archive')throw new c.HttpError('Unknown social post action.');
  const existing=x.id?await socialItem(c,x.id):null;
  if(existing&&(!x.updated_at||existing.updated_at!==x.updated_at))throw new c.HttpError('This post changed since you opened it. Refresh before saving.',409);
  if(x.action==='archive'){if(!existing)throw new c.HttpError('Choose a post to archive.');await c.monday('mutation($id:ID!){archive_item(item_id:$id){id}}',{id:existing.id},true);console.log(JSON.stringify({event:'social_post_archived',user:c.user.id,id:existing.id}));return reply({success:true,id:existing.id});}
  const board=await socialBoard(c),labels=socialLabels(board),status=labels.find((v:any)=>v.label===x.status);if(!status)throw new c.HttpError('Choose a valid posting status.');
  const title=c.text(x.title,250),publish=socialDateTime(x.publish_at_et);if(x.publish_at_et&&!publish)throw new c.HttpError('Enter a valid posting date and time in Eastern Time.');if(x.status==='Scheduled'&&!publish)throw new c.HttpError('Set a date and time before marking a post Scheduled.');
  if(!Array.isArray(x.platforms)||!x.platforms.length||x.platforms.length>20||x.platforms.some((v:any)=>typeof v!=='string'||!v.trim()||v.length>80||v.includes(',')))throw new c.HttpError('Choose at least one valid platform.');
  const short=(v:any,max=250)=>typeof v==='string'?v.trim().slice(0,max):'';
  const media=c.web(x.media_url)||'',dest=c.web(x.destination_url)||'',published=c.web(x.published_url)||'';
  const values:any={name:title,[SC.publish]:publish.replace('T',' '),[SC.date]:publish?{date:publish.slice(0,10)}:{},[SC.platform]:[...new Set(x.platforms.map((v:string)=>v.trim()))].join(', '),[SC.status]:{index:status.id},[SC.campaign]:short(x.campaign),[SC.caption]:{text:short(x.caption,8000)},[SC.assigned]:short(x.assigned_to),[SC.notes]:{text:short(x.notes,8000)},[SC.destination]:dest,[SC.asset]:media?{url:media,text:'Post creative'}:{},[SC.published]:published,[SC.assetType]:short(x.asset_type)||'Image',[SC.role]:short(x.content_role)||'Main Post'};
  const group=['Scheduled','Posted'].includes(x.status)?'group_mm8g7fq9':'topics';let id=existing?.id;
  if(existing){await c.monday('mutation($b:ID!,$id:ID!,$v:JSON!){change_multiple_column_values(board_id:$b,item_id:$id,column_values:$v){id}}',{b:SOCIAL_BOARD,id:existing.id,v:JSON.stringify(values)},true);if(existing.group?.id!==group){try{await c.monday('mutation($id:ID!,$group:String!){move_item_to_group(item_id:$id,group_id:$group){id}}',{id:existing.id,group},true);}catch{throw new c.HttpError('The post was saved, but its board group could not be updated. Refresh before trying again.',502);}}}
  else{delete values.name;values[SC.organization]='NAL';values[SC.visible]='No';const result=await c.monday('mutation($b:ID!,$group:String!,$name:String!,$v:JSON!){create_item(board_id:$b,group_id:$group,item_name:$name,column_values:$v){id}}',{b:SOCIAL_BOARD,group,name:title,v:JSON.stringify(values)},true);id=result.create_item?.id;}
  if(!id)throw new c.HttpError('The social post was not saved.',502);console.log(JSON.stringify({event:'social_post_saved',user:c.user.id,id,status:x.status}));return reply({success:true,id});
 }
 if(path==='/social/files'&&req.method==='GET'){const p=await socialItem(c,c.url.searchParams.get('item'),true);return reply({files:(p.column_values.find((v:any)=>v.id===SC.media)?.files||[]).filter((f:any)=>f.asset_id).map((f:any)=>({id:String(f.asset_id),name:f.name,extension:f.asset?.file_extension||''}))});}
 if(path==='/social/download'&&req.method==='GET'){
  const p=await socialItem(c,c.url.searchParams.get('item'),true),id=c.id(c.url.searchParams.get('asset'));const file=p.column_values.find((v:any)=>v.id===SC.media)?.files?.find((f:any)=>String(f.asset_id)===id);if(!file?.asset?.public_url)throw new c.HttpError('Media not found on this post.',404);
  const url=new URL(file.asset.public_url),h=url.hostname;if(url.protocol!=='https:'||!(h==='monday.com'||h.endsWith('.monday.com')||h.endsWith('.amazonaws.com')||h.endsWith('.cloudfront.net')))throw new c.HttpError('This media URL cannot be retrieved securely.',502);const r=await fetch(url,{signal:AbortSignal.timeout(45000)});if(!r.ok)throw new c.HttpError('This media could not be downloaded.',502);
  return new Response(r.body,{headers:{'Content-Type':r.headers.get('Content-Type')||'application/octet-stream','Content-Disposition':'attachment; filename="'+String(file.name||'media').replace(/[\r\n"\\/]/g,'_').slice(0,180)+'"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"}});
 }
 return null;
}
