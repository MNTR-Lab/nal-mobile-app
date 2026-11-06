import html from './index.html';
import css from './admin.css';
import app from './app.js';
import config from './config.js';
import transactions from './transactions.js';
import invites from './staff-invites.js';
const functions='https://rcoaprzmutcwlpugobry.supabase.co/functions/v1/';
const security={
 'Cache-Control':'no-store',
 'X-Content-Type-Options':'nosniff',
 'Referrer-Policy':'no-referrer',
 'X-Robots-Tag':'noindex, nofollow',
 'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
 'Content-Security-Policy':"default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src 'self' https://rcoaprzmutcwlpugobry.supabase.co; img-src 'self' data: https:; frame-src https://nal-network.com https://www.nal-network.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
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
   else if(['me','polls','transactions','assets','staff','staff/invite','staff/accept','activity'].includes(path))target='nal-network-admin/'+path;
   else return new Response('Not found',{status:404,headers:security});
   if(Number(request.headers.get('Content-Length'))>1048576)return new Response('Request too large',{status:413,headers:security});
   const body=request.method==='POST'?await request.text():undefined;
   if(body&&body.length>1048576)return new Response('Request too large',{status:413,headers:security});
   const response=await fetch(functions+target+url.search,{method:request.method,headers:{Authorization:request.headers.get('Authorization'),'Content-Type':'application/json',Origin:'https://admin.nal-network.com'},body,signal:AbortSignal.timeout(55000)});
   return new Response(response.body,{status:response.status,headers:{...security,'Content-Type':'application/json'}});
  }
  if(request.method!=='GET'&&request.method!=='HEAD')return new Response('Method not allowed',{status:405,headers:security});
  const files={'/transactions.js':[transactions,'text/javascript'],'/staff-invites.js':[invites,'text/javascript'],'/admin.css':[css,'text/css'],'/app.js':[app,'text/javascript'],'/config.js':[config,'text/javascript']};
  const f=files[url.pathname];
  if(f)return new Response(request.method==='HEAD'?null:f[0],{headers:{...security,'Content-Type':f[1]+'; charset=utf-8'}});
  if(url.pathname==='/accept-invite'||url.pathname==='/'||url.pathname==='/admin'||url.pathname==='/admin/'||url.pathname==='/transactions'||url.pathname==='/admin/transactions')return new Response(request.method==='HEAD'?null:html,{headers:{...security,'Content-Type':'text/html; charset=utf-8'}});
  return new Response('Not found',{status:404,headers:security});
 }catch(e){console.error(JSON.stringify({event:'admin_gateway_error',message:e.message}));return Response.json({error:'The server connection timed out. Please try again.'},{status:502,headers:security});}
}};
