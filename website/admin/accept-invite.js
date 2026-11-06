'use strict';
(async()=>{
 const output=document.getElementById('invite-return-status');
 if(!window.supabase){output.textContent='The account service could not load. Refresh to try again.';return;}
 const client=window.supabase.createClient(window.NAL_CONFIG.url,window.NAL_CONFIG.key,{auth:{persistSession:true,autoRefreshToken:false,detectSessionInUrl:true}});
 try{
  const {data:{session},error}=await client.auth.getSession();
  if(error||!session){output.textContent='This invitation may be expired. Ask a super admin for a new acceptance link.';return;}
  // The accepted session remains on the Forum origin. The admin session bridge imports it.
  history.replaceState({},'',location.pathname);
  window.location.replace('https://admin.nal-network.com/accept-invite');
 }catch{output.textContent='Your invitation could not be opened. Ask a super admin for a new acceptance link.';}
})();
