import html from './index.html';
import css from './admin.css';
import app from './app.js';
import config from './config.js';
import transactions from './transactions.js';
import invites from './staff-invites.js';
import workspace from './workspace.js';
import social from './social.js';
const functions='https://rcoaprzmutcwlpugobry.supabase.co/functions/v1/';
const security={
 'Cache-Control':'no-store',
 'X-Content-Type-Options':'nosniff',
 'Referrer-Policy':'no-referrer',
 'X-Robots-Tag':'noindex, nofollow',
 'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
 'Content-Security-Policy':"default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src 'self' https://rcoaprzmutcwlpugobry.supabase.co; img-src 'self' blob: data: https:; frame-src blob: https://nal-network.com https://www.nal-network.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
};
export default {async fetch(request){
 const url=new URL(request.url);
 try{
  if(url.pathname.startsWith('/api/')){
   if(!['GET','POST'].includes(request.method))return new Response('Method not allowed',{status:405,headers:security});
   if(!request.headers.get('Authorization'))return Response.json({error:'Sign in with your Forum account.'},{status:401,headers:security});
   if(request.method==='POST'&&request.headers.get('Origin')!==url.origin)return Response.json({error:'Origin not allowed'},{status:403,headers:security});
   const path=url.pathname.slice(5);let target;
   if(path.startsWith('fcf/admin/'))target='nal-network-admin/friday/'+path.slice(4);
   else if(path==='roster')target='nal-network-admin/roster';
   else if(['social','social/files','social/download','me','polls','transactions','transactions/schema','assets','assets/files','assets/upload','assets/download','library','connections','staff','staff/invite','staff/accept','activity'].includes(path))target='nal-network-admin/'+path;
   else return new Response('Not found',{status:404,headers:security});
   const upload=path==='assets/upload';const max=upload?21*1024*1024:1048576;
   if(Number(request.headers.get('Content-Length'))>max)return Response.json({error:'The upload is too large. Maximum file size is 20 MB.'},{status:413,headers:security});
   let body;
   if(request.method==='POST'){
    const reader=request.body?.getReader();let total=0;const chunks=[];
    if(reader)for(;;){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>max){await reader.cancel();return Response.json({error:'The request is too large.'},{status:413,headers:security});}chunks.push(value);}
    body=new Uint8Array(total);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength;}
   }
   const response=await fetch(functions+target+url.search,{method:request.method,headers:{Authorization:request.headers.get('Authorization'),'Content-Type':upload?(request.headers.get('Content-Type')||'application/octet-stream'):'application/json',Origin:'https://admin.nal-network.com'},body,signal:AbortSignal.timeout(55000)});
   const headers={...security,'Content-Type':response.headers.get('Content-Type')||'application/json'};
   if(['assets/download','social/download'].includes(path)&&response.ok){headers['Content-Disposition']=response.headers.get('Content-Disposition')||'attachment';headers['Content-Security-Policy']="sandbox; default-src 'none'";}
   return new Response(response.body,{status:response.status,headers});
  }
  if(request.method!=='GET'&&request.method!=='HEAD')return new Response('Method not allowed',{status:405,headers:security});
  const files={'/social.js':[social,'text/javascript'],'/workspace.js':[workspace,'text/javascript'],'/transactions.js':[transactions,'text/javascript'],'/staff-invites.js':[invites,'text/javascript'],'/admin.css':[css,'text/css'],'/app.js':[app,'text/javascript'],'/config.js':[config,'text/javascript']};
  const f=files[url.pathname];
  if(f)return new Response(request.method==='HEAD'?null:f[0],{headers:{...security,'Content-Type':f[1]+'; charset=utf-8'}});
  if(url.pathname==='/accept-invite'||url.pathname==='/'||url.pathname==='/admin'||url.pathname==='/admin/'||url.pathname==='/social'||url.pathname==='/transactions'||url.pathname==='/admin/transactions')return new Response(request.method==='HEAD'?null:html,{headers:{...security,'Content-Type':'text/html; charset=utf-8'}});
  return new Response('Not found',{status:404,headers:security});
 }catch(e){console.error(JSON.stringify({event:'admin_gateway_error',message:e.message}));return Response.json({error:'The server connection timed out. Please try again.'},{status:502,headers:security});}
}};
