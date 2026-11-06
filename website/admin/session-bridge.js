'use strict';
// Tokens are sent only to the exact staff origin in an existing same-site frame.
// Never use URL query strings, wildcard postMessage targets, or user metadata for access.
if(window.parent!==window&&window.supabase){
 const adminOrigin='https://admin.nal-network.com';
 const client=window.supabase.createClient(window.NAL_CONFIG.url,window.NAL_CONFIG.key,{auth:{persistSession:true,autoRefreshToken:false,detectSessionInUrl:false}});
 window.addEventListener('message',async event=>{
  if(event.origin!==adminOrigin||event.source!==window.parent)return;
  try{
   if(event.data?.type==='nal-admin-session-get'){
    const {data:{session}}=await client.auth.getSession();
    window.parent.postMessage({type:'nal-admin-session',session:session?{access_token:session.access_token,refresh_token:session.refresh_token}:null},adminOrigin);
   }
   if(event.data?.type==='nal-admin-session-set'&&event.data.session?.access_token&&event.data.session?.refresh_token){
    await client.auth.setSession({access_token:event.data.session.access_token,refresh_token:event.data.session.refresh_token});
   }
   if(event.data?.type==='nal-admin-session-clear')await client.auth.signOut({scope:'local'});
  }catch{window.parent.postMessage({type:'nal-admin-bridge-error'},adminOrigin);}
 });
 window.parent.postMessage({type:'nal-admin-bridge-ready'},adminOrigin);
}
