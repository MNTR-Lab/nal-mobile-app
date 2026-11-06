'use strict';
const STAFF_ACCESS_OPTIONS=[['polls','Polls'],['friday','Fan Choice Friday'],['transactions','Transactions'],['assets','Digital Assets'],['connections','Connected Workspaces'],['activity','Activity Log']];
function permissionCheckboxes(selected=[]){return '<fieldset class="permission-options"><legend>Dashboard access</legend>'+STAFF_ACCESS_OPTIONS.map(([key,label])=>'<label class="check"><input type="checkbox" name="sections" value="'+key+'" '+(selected.includes(key)?'checked':'')+'>'+label+'</label>').join('')+'<label class="check"><input type="checkbox" disabled>Staff & Permissions — super admin only</label></fieldset>';}
function accessLabels(selected=[]){return selected.map(key=>STAFF_ACCESS_OPTIONS.find(([k])=>k===key)?.[1]||(key==='staff'?'Staff & Permissions':key)).join(', ')||'No dashboard access';}

function inviteEditor(id){
 const member=id?members.find(m=>m.id===id):null;
 showEditor(member?'Send staff access link':'Create a NAL Verified account',
 '<form id="invite-form" data-id="'+esc(member?.id||'')+'">'+
 '<label>Display name<input name="display_name" minlength="3" maxlength="30" required value="'+esc(member?.display_name||'')+'" '+(member?'readonly':'')+'></label>'+
 '<p class="muted">Only @mntrlab.com and @thenationalarenaleague.com accounts can be invited.</p><label>Email<input name="email" type="email" autocomplete="off" maxlength="254" required value="'+esc(member?.email||'')+'" '+(member?'readonly':'')+'></label>'+
 (member?'':permissionCheckboxes())+
 '<p class="muted">'+(member?'This uses their existing Forum account and preserves their current access.':'They choose their own password after accepting. Their account also works for the Forum. Dashboard permissions do not change their Forum badge.')+'</p>'+
 '<div class="actions"><button type="submit" name="delivery" value="email" class="primary">'+(member?'Email access link':'Create & email invitation')+'</button><button type="submit" name="delivery" value="link">'+(member?'Generate access link':'Create & get acceptance link')+'</button></div></form><div id="invite-result" hidden></div>');
}
async function submitInvitation(form,button){
 const values=new FormData(form),delivery=button.value,email=values.get('email');
 if(delivery==='email'&&!confirm('Send '+(form.dataset.id?'an access link':'an invitation')+' to '+email+'?'))return;
 const result=await api('staff/invite',{email,display_name:values.get('display_name'),sections:values.getAll('sections'),delivery,resend:!!form.dataset.id});
 form.hidden=true;const host=$('#invite-result');host.hidden=false;
 if(result.acceptance_url){
  host.innerHTML='<div class="invite-result"><strong>Acceptance link ready</strong><p>Share this private, single-use link with '+esc(email)+'.</p><label>Acceptance link<input class="invite-link" readonly id="staff-acceptance-link"></label><button type="button" id="copy-staff-invite">Copy link</button><p class="muted">No email was sent. The recipient sets their password after accepting.</p></div>';
  $('#staff-acceptance-link').value=result.acceptance_url;
  $('#copy-staff-invite').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(result.acceptance_url);editorMessage('Link copied.');}catch{$('#staff-acceptance-link').select();editorMessage('Select and copy the acceptance link above.');}});
 }else host.innerHTML='<div class="invite-result"><strong>Email sent to '+esc(email)+'</strong><p>They can accept the email link and continue to NAL Staff Admin using the same Forum account.</p></div>';
 // Reload the eligible staff list without closing the invitation result.
 const data=await api('staff');members=data.members;if(section==='staff')drawStaff();
}
function showInvitationSetup(me){
 current=null;$('#login').hidden=true;$('#dashboard').hidden=true;$('#invite-setup').hidden=false;$('#signout').hidden=false;
 $('#invite-identity').textContent=me.user.name+' · '+me.user.email;
 $('#invitation-form').hidden=false;$('#invite-complete').hidden=true;
}
function showVerifiedReady(){
 current=null;$('#login').hidden=true;$('#dashboard').hidden=true;$('#invite-setup').hidden=false;$('#signout').hidden=false;
 $('#invitation-form').hidden=true;$('#invite-complete').hidden=false;$('#invite-identity').textContent='Your account is ready. Dashboard access has not been assigned yet.';
}
async function startInvitation(){
 if(!invitationFlow)return false;
 $('#login-message').textContent='Checking your invitation…';
 const params=new URLSearchParams(location.search);const token=params.get('token_hash'),type=params.get('type');
 if(token){
  // Remove the credential from browser history before further navigation.
  history.replaceState({},'',location.pathname);
  if(!['invite','magiclink','email'].includes(type)){ $('#login-message').textContent='This invitation link is not valid.';return true;}
  const r=await sb.auth.verifyOtp({token_hash:token,type});
  if(r.error){$('#login-message').textContent='This link is invalid or expired. Ask a super admin for a new access link.';$('#login-message').className='error';return true;}
 }
 const {data:{session}}=await sb.auth.getSession();
 if(!session){invitationFlow=false;bridge('nal-admin-session-get');$('#login-message').textContent='Open the invitation link from your email, or sign in with your Forum account.';return true;}
 invitationFlow=false;bridge('nal-admin-session-set',session);await enter();return true;
}
