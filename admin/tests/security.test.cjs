const {test}=require('node:test');
const assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../supabase/functions/nal-network-admin/index.ts'),'utf8');
function handler({role='admin',status='active',superAdmin=false,valid=true,protectedTarget=false}={}){
 let serve;const changes=[];
 const db={auth:{getUser:async()=>({data:{user:valid?{id:'staff-1',email:'staff@example.test'}:null},error:valid?null:new Error('bad token')})},from(table){let op='select';const q={select(){return q},eq(){return q},update(v){op='update';changes.push({table,v});return q},insert(v){op='insert';changes.push({table,v});return q},maybeSingle:async()=>({data:table==='profiles'?{role,account_status:status,display_name:'Staff'}:table==='nal_super_admins'?(superAdmin||protectedTarget?{user_id:'staff-1'}:null):null,error:null}),then(resolve){return Promise.resolve({data:[],error:null}).then(resolve)}};return q;}};
 const js=stripTypeScriptTypes(source.replace(/^import[^\n]+\n/,''),{mode:'transform'});
 vm.runInNewContext(js,{Deno:{env:{get:()=>''},serve:h=>serve=h},createClient:()=>db,Response,URL,AbortSignal,console:{error(){}},fetch:()=>{throw new Error('Unexpected external fetch');}});
 return {serve,changes};
}
const req=(path='/me',body,token='valid')=>new Request('https://test.invalid/functions/v1/nal-network-admin'+path,{method:body?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
test('missing and invalid sessions are rejected',async()=>{assert.equal((await handler().serve(req('/me',null,''))).status,401);assert.equal((await handler({valid:false}).serve(req())).status,401);});
test('fans and suspended administrators have no staff access',async()=>{assert.equal((await handler({role:'fan'}).serve(req())).status,403);assert.equal((await handler({status:'suspended'}).serve(req())).status,403);});
test('ordinary admin cannot change staff roles',async()=>{const h=handler();assert.equal((await h.serve(req('/staff',{user_id:'target',role:'admin'}))).status,403);assert.equal(h.changes.length,0);});
test('moderator can access polls only',async()=>{const h=handler({role:'moderator'});const me=await (await h.serve(req())).json();assert.deepEqual(me.sections,['polls']);assert.equal((await h.serve(req('/assets'))).status,403);assert.equal((await h.serve(req('/transactions'))).status,403);});
test('super admin receives staff controls and cannot change own role',async()=>{const h=handler({superAdmin:true});const me=await (await h.serve(req())).json();assert.equal(me.user.role,'super_admin');assert(me.sections.includes('staff'));assert.equal((await h.serve(req('/staff',{user_id:'staff-1',role:'fan'}))).status,400);assert.equal(h.changes.length,0);});
test('super admin accounts are protected from role edits',async()=>{const h=handler({superAdmin:true,protectedTarget:true});assert.equal((await h.serve(req('/staff',{user_id:'owner',role:'fan'}))).status,400);assert.equal(h.changes.length,0);});
test('untrusted web origins are rejected',async()=>{const r=req();r.headers.set('Origin','https://untrusted.example');assert.equal((await handler().serve(r)).status,403);});
test('non-super admin cannot invoke roster writes',async()=>{assert.equal((await handler().serve(req('/roster',{player:{},rosterStatus:'Released'}))).status,403);});
