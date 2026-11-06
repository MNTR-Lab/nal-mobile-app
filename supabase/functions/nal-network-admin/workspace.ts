// Native dashboard workflows. Every call reaches this module only after authentication,
// domain, active-account, and section-permission checks in index.ts.
const WS_BOARDS={assets:'18437455062',transactions:'18421027719',library:'18436132233'};
const WS_TX={firstName:'short_textqgu7jmng',lastName:'short_text8mqlqiik',organization:'single_selectrkknj7l',transactionType:'single_select4w70vhf',position:'single_select2j27cbs',height:'short_text83a4xfpd',weight:'short_textk8t1m1zy',college:'short_textemwe53jr',professionalExperience:'short_texta2nd7kpg',transactionDate:'date_mm529ngc',tradeDetails:'long_textvw1fr5rg',injuryLength:'single_selectwfkfsod',suspensionReason:'long_text4yeqsbzs'};
const WS_GAME={game_status:'color_mm89fnxk',highlight_status:'color_mm89r0bf',thumbnail_url:'text_mm891a48',description:'long_text_mm896fe9',season:'numeric_mm8994m2',game_date:'date_mm89z94b',away_team:'text_mm89fwb0',full_game_url:'text_mm89hvh3',preview_url:'text_mm897kk8',home_team:'text_mm89qc4f',preview_start:'text_mm898yg1',preview_end:'text_mm8980ms'};
function wsSettings(value:any){try{return typeof value==='string'?JSON.parse(value):value||{};}catch{return {};}}
function wsLabels(column:any){const raw=wsSettings(column?.settings).labels||[];return Array.isArray(raw)?raw.filter((l:any)=>!l.is_deactivated).map((l:any)=>({id:Number(l.id),label:l.label||l.name||''})):Object.entries(raw).map(([id,label])=>({id:Number(id),label:String(label)}));}
function wsColumn(board:any,id:string){return board.columns.find((c:any)=>c.id===id);}
function wsValue(c:any,item:any,key:string){return item.column_values?.find((v:any)=>v.id===key)?.text||'';}
function wsDate(c:any,value:any){if(!value)return {};if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||(!Number.isFinite(Date.parse(value))||new Date(value+'T00:00:00Z').toISOString().slice(0,10)!==value))throw new c.HttpError('Enter a valid date.');return {date:value};}
function wsStatus(c:any,board:any,columnId:string,value:any){if(!value)return {};const label=wsLabels(wsColumn(board,columnId)).find((l:any)=>l.label===value);if(!label)throw new c.HttpError('Select a valid '+(wsColumn(board,columnId)?.title||'status')+'.');return {index:label.id};}
async function wsBoard(c:any,kind:keyof typeof WS_BOARDS){const r=await c.monday('query($ids:[ID!]!){boards(ids:$ids){id name groups{id title} columns{id title type settings}}}',{ids:[WS_BOARDS[kind]]},kind!=='transactions');const b=r.boards?.[0];if(!b)throw new c.HttpError('This connected board is unavailable.',503);return b;}
async function wsItem(c:any,kind:keyof typeof WS_BOARDS,itemId:any,files=false){
 const fileFields=files?' ... on FileValue {files { ... on FileAssetValue {asset_id name is_image asset {id public_url file_extension file_size}} ... on FileLinkValue {file_id name url} ... on FileDocValue {file_id url}}}':'';
 const r=await c.monday(`query($ids:[ID!]!){items(ids:$ids){id name updated_at board{id} group{id title} column_values{id text value ${fileFields}}}}`,{ids:[c.id(itemId)]},kind!=='transactions');const item=r.items?.[0];if(!item||String(item.board?.id)!==WS_BOARDS[kind])throw new c.HttpError('Record not found in this section.',404);return item;
}
function wsFiles(item:any,column:string){return (item.column_values?.find((v:any)=>v.id===column)?.files||[]).map((f:any)=>({id:f.asset_id?String(f.asset_id):null,name:f.name||'Linked document',image:!!f.is_image,extension:f.asset?.file_extension||'',size:f.asset?.file_size||0,downloadable:!!f.asset_id}));}
function wsSafeFilename(value:string){return String(value||'download').replace(/[\r\n"\\/]/g,'_').slice(0,180);}
function wsDownloadUrl(c:any,value:string){const u=new URL(value);const h=u.hostname.toLowerCase();if(u.protocol!=='https:'||!(h==='monday.com'||h.endsWith('.monday.com')||h.endsWith('.amazonaws.com')||h.endsWith('.cloudfront.net')))throw new c.HttpError('This file cannot be retrieved securely.',502);return u.href;}
async function wsUpload(c:any,itemId:string,file:File){
 const token=Deno.env.get('FCF_MONDAY_API_TOKEN')||Deno.env.get('MONDAY_API_TOKEN');if(!token)throw new c.HttpError('The file connection is unavailable.',503);
 const data=new FormData();data.append('query','mutation($file:File!,$item:ID!,$column:String!){add_file_to_column(file:$file,item_id:$item,column_id:$column){id name}}');data.append('variables',JSON.stringify({file:null,item:itemId,column:'file_mm8jsk7z'}));data.append('map',JSON.stringify({upload:'variables.file'}));data.append('upload',file,wsSafeFilename(file.name));
 const r=await fetch('https://api.monday.com/v2/file',{method:'POST',headers:{Authorization:token,'API-Version':'2026-07'},body:data,signal:AbortSignal.timeout(50000)});const j=await r.json();if(!r.ok||j.errors?.length)throw new c.HttpError('The upload was not completed. Try again.',502);return j.data?.add_file_to_column;
}
export async function handleMondayWorkspace(c:any):Promise<Response|null>{
 const {path,req,x,url}=c;const reply=(data:any,status=200)=>new Response(JSON.stringify(data),{status,headers:c.headers});
 if(path==='/connections'&&req.method==='GET'){
  const statuses=await Promise.all((['transactions','library','assets'] as const).map(async kind=>{try{const b=await wsBoard(c,kind);return {section:kind,name:b.name,connected:true,count:undefined};}catch{return {section:kind,name:kind,connected:false};}}));return reply({connections:statuses});
 }
 if(path==='/transactions/schema'&&req.method==='GET'){
  const b=await wsBoard(c,'transactions');return reply({organizations:wsLabels(wsColumn(b,WS_TX.organization)),types:wsLabels(wsColumn(b,WS_TX.transactionType)),positions:wsLabels(wsColumn(b,WS_TX.position)),injuries:wsLabels(wsColumn(b,WS_TX.injuryLength))});
 }
 if(path==='/transactions'&&req.method==='POST'){
  const board=await wsBoard(c,'transactions');const existing=x.id?await wsItem(c,'transactions',x.id):null;
  if(existing&&x.updatedAt&&existing.updated_at!==x.updatedAt)throw new c.HttpError('This transaction changed since you opened it. Refresh before saving.',409);
  const first=c.text(x.firstName,120),last=c.text(x.lastName,120);const state=x.state||'Pending';if(!['Pending','Approved','Needs Action'].includes(state))throw new c.HttpError('Choose a valid review status.');
  const values:any={};for(const [key,col] of Object.entries(WS_TX)){
   const v=x[key];if(['organization','transactionType','position','injuryLength'].includes(key))values[col]=wsStatus(c,board,col,v);
   else if(key==='transactionDate')values[col]=wsDate(c,v);
   else if(['tradeDetails','suspensionReason'].includes(key))values[col]={text:typeof v==='string'?v.slice(0,5000):''};
   else values[col]=typeof v==='string'?v.trim().slice(0,500):'';
  }
  if(!x.organization||!x.transactionType)throw new c.HttpError('Select an organization and transaction type.');
  values.boolean_mm58fd1p={checked:x.activeRoster===true?'true':'false'};
  values.color_mm581gnf=state==='Pending'?{}:wsStatus(c,board,'color_mm581gnf',state==='Approved'?'Approved':'Rejected');
  const reason=String(x.reviewReason||'').trim().slice(0,1000);if(state==='Needs Action'&&!reason)throw new c.HttpError('Add a reason when returning a transaction.');
  const name=first+' '+last+(state==='Needs Action'?' — '+reason:'');
  const group=state==='Approved'?'group_mm5251en':state==='Needs Action'?'group_mm52ns1y':'topics';
  let savedId=existing?.id;
  if(existing){values.name=name;await c.monday('mutation($board:ID!,$item:ID!,$values:JSON!){change_multiple_column_values(board_id:$board,item_id:$item,column_values:$values){id}}',{board:board.id,item:existing.id,values:JSON.stringify(values)});
   if(existing.group?.id!==group){try{await c.monday('mutation($item:ID!,$group:String!){move_item_to_group(item_id:$item,group_id:$group){id}}',{item:existing.id,group});}catch{throw new c.HttpError('Player details were saved, but the review queue could not be updated. Refresh before trying again.',502);}}
  }else{
   const created=await c.monday('mutation($board:ID!,$group:String!,$name:String!,$values:JSON!){create_item(board_id:$board,group_id:$group,item_name:$name,column_values:$values){id}}',{board:board.id,group,name,values:JSON.stringify(values)});savedId=created.create_item?.id;
  }
  if(!savedId)throw new c.HttpError('The transaction was not saved.',502);await c.audit(c.user.id,'transaction_saved','Transaction '+savedId+': '+state);return reply({success:true,id:savedId});
 }
 if(path==='/assets'&&req.method==='GET'){
  const b=await c.boardItems(WS_BOARDS.assets,true);const schema=await wsBoard(c,'assets');
  return reply({board:b.name,groups:schema.groups,items:b.items.map((i:any)=>{let raw:any={};try{raw=JSON.parse(i.column_values.find((v:any)=>v.id==='file_mm8jsk7z')?.value||'{}');}catch{}return {id:i.id,name:i.parentName?i.parentName+' / '+i.name:i.name,recordName:i.name,group:i.group?.title||'',groupId:i.group?.id,details:wsValue(c,i,'text_mm8jjxt8'),usage:wsValue(c,i,'dropdown_mm8j7gcm'),date:wsValue(c,i,'date_mm8j3gz6'),link:(()=>{try{return JSON.parse(i.column_values.find((v:any)=>v.id==='link_mm8jkx6a')?.value||'{}').url||'';}catch{return '';}})(),attachmentCount:raw.files?.length||0};})});
 }
 if(path==='/assets'&&req.method==='POST'){
  const b=await wsBoard(c,'assets');let itemId=x.id?c.id(x.id):null;if(itemId)await wsItem(c,'assets',itemId);
  const usage=Array.isArray(x.usage)?x.usage:[];if(usage.some((s:string)=>!['Free for use','Website','Social media'].includes(s)))throw new c.HttpError('Choose valid usage options.');
  const link=c.web(x.link);const values:any={text_mm8jjxt8:typeof x.details==='string'?x.details.slice(0,10000):'',dropdown_mm8j7gcm:{labels:usage},date_mm8j3gz6:wsDate(c,x.date),link_mm8jkx6a:link?{url:link,text:'Usage link'}:{}};
  if(itemId){if(x.name)values.name=c.text(x.name,255);await c.monday('mutation($board:ID!,$item:ID!,$values:JSON!){change_multiple_column_values(board_id:$board,item_id:$item,column_values:$values){id}}',{board:b.id,item:itemId,values:JSON.stringify(values)},true);}
  else{if(!b.groups.some((g:any)=>g.id===x.group))throw new c.HttpError('Choose an asset category.');const out=await c.monday('mutation($board:ID!,$group:String!,$name:String!,$values:JSON!){create_item(board_id:$board,group_id:$group,item_name:$name,column_values:$values){id}}',{board:b.id,group:x.group,name:c.text(x.name,255),values:JSON.stringify(values)},true);itemId=out.create_item?.id;}
  await c.audit(c.user.id,'asset_updated','Digital asset '+itemId);return reply({success:true,id:itemId});
 }
 if(path==='/assets/files'&&req.method==='GET'){const item=await wsItem(c,'assets',url.searchParams.get('item'),true);return reply({files:wsFiles(item,'file_mm8jsk7z')});}
 if(path==='/assets/upload'&&req.method==='POST'){
  const form=await req.formData();const item=await wsItem(c,'assets',form.get('item'));const file=form.get('file');if(!(file instanceof File)||!file.size)throw new c.HttpError('Choose a file to upload.');if(file.size>20*1024*1024)throw new c.HttpError('Files must be 20 MB or smaller.',413);
  const out=await wsUpload(c,item.id,file);await c.audit(c.user.id,'asset_updated','File uploaded to asset '+item.id+': '+wsSafeFilename(file.name));return reply({success:true,file:out});
 }
 if(path==='/assets/download'&&req.method==='GET'){
  const item=await wsItem(c,'assets',url.searchParams.get('item'),true);const assetId=c.id(url.searchParams.get('asset'));const file=item.column_values.find((v:any)=>v.id==='file_mm8jsk7z')?.files?.find((f:any)=>String(f.asset_id)===assetId);
  if(!file?.asset?.public_url)throw new c.HttpError('File not found on this asset.',404);
  const remote=await fetch(wsDownloadUrl(c,file.asset.public_url),{redirect:'follow',signal:AbortSignal.timeout(45000)});if(!remote.ok)throw new c.HttpError('This file could not be downloaded.',502);
  return new Response(remote.body,{headers:{'Content-Type':remote.headers.get('Content-Type')||'application/octet-stream','Content-Disposition':'attachment; filename="'+wsSafeFilename(file.name)+'"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"}});
 }
 if(path==='/library'&&req.method==='GET'){
  const b=await c.boardItems(WS_BOARDS.library,true);const schema=await wsBoard(c,'library');
  return reply({games:b.items.map((i:any)=>Object.fromEntries([['id',i.id],['matchup',i.name],...Object.entries(WS_GAME).map(([key,col])=>[key,wsValue(c,i,col)])])),statuses:wsLabels(wsColumn(schema,WS_GAME.game_status)),highlightStatuses:wsLabels(wsColumn(schema,WS_GAME.highlight_status))});
 }
 if(path==='/library'&&req.method==='POST'){
  const b=await wsBoard(c,'library');const existing=x.id?await wsItem(c,'library',x.id):null;const name=c.text(x.matchup,255);if(!x.game_status||!x.highlight_status)throw new c.HttpError('Select both game and highlight status.');const values:any={};
  for(const [key,col] of Object.entries(WS_GAME)){
   const v=x[key];if(['game_status','highlight_status'].includes(key))values[col]=wsStatus(c,b,col,v);
   else if(key==='game_date')values[col]=wsDate(c,v);
   else if(key==='season'){if(v&&!/^\d{4}$/.test(String(v)))throw new c.HttpError('Enter a four-digit season.');values[col]=v?String(v):'';}
   else if(key==='description')values[col]={text:String(v||'').slice(0,5000)};
   else if(['thumbnail_url','full_game_url','preview_url'].includes(key))values[col]=c.web(v)||'';
   else values[col]=String(v||'').slice(0,500);
  }
  let savedId=existing?.id;
  if(existing){values.name=name;await c.monday('mutation($board:ID!,$item:ID!,$values:JSON!){change_multiple_column_values(board_id:$board,item_id:$item,column_values:$values){id}}',{board:b.id,item:existing.id,values:JSON.stringify(values)},true);}
  else{const out=await c.monday('mutation($board:ID!,$name:String!,$values:JSON!){create_item(board_id:$board,group_id:"topics",item_name:$name,column_values:$values){id}}',{board:b.id,name,values:JSON.stringify(values)},true);savedId=out.create_item?.id;}
  await c.audit(c.user.id,'library_game_saved','Game library item '+savedId);return reply({success:true,id:savedId});
 }
 return null;
}
