
const cors={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,apikey,content-type","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json","Cache-Control":"no-store"};
const publicKey="sb_publishable_tHzWH6oFoUemOrdLs_h9bw_UOLBP-yb";
const channels=new Set(["72169","72160","72161","72162","72163","72164","72165","72166","72167","72168","72158"]);
const utc=v=>Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(v||"")?v:String(v||"").replace(" ","T")+"Z");
export function currentEvent(events,channel,id,now=Date.now()){
 return events.filter(e=>String(e.channel_id)===channel&&(!id||String(e.event_id)===id)&&utc(e.start_time_utc)<=now&&now<utc(e.end_time_utc))
 .sort((a,b)=>utc(b.start_time_utc)-utc(a.start_time_utc))[0]||null;
}
Deno.serve(async req=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors});
 if(req.method!=="GET")return Response.json({error:"Read-only endpoint"},{status:405,headers:cors});
 if(req.headers.get("apikey")!==publicKey)return Response.json({error:"Invalid API key"},{status:401,headers:cors});
 const scope=new URL(req.url).searchParams.get("scope")||"";
 const m=/^game:([0-9]+)::([0-9]+)$/.exec(scope);
 const channel=scope==="live-channel"?"72169":m?.[1],id=m?.[2];
 if(!channel||!channels.has(channel))return Response.json({error:"Invalid event"},{status:400,headers:cors});
 try{
  let events;
  if(channel==="72161"){
   const r=await fetch("https://nal-network.com/data/live-games.json",{signal:AbortSignal.timeout(10000),cache:"no-store"});if(!r.ok)throw Error();
   const d=await r.json();events=Array.isArray(d)?d:d.games;
  }else{
   const r=await fetch("https://qpavspvpdebtbbffdcmo.supabase.co/functions/v1/nal-live-events?channelId="+channel,{signal:AbortSignal.timeout(15000),cache:"no-store"});
   const d=await r.json();if(!r.ok||!d.ok)throw Error();events=d.events;
  }
  if(!Array.isArray(events))throw Error();
  const event=currentEvent(events,channel,id);
  const secret=JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS")||"{}").default||Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!secret)throw Error();
  const headers={"Content-Type":"application/json",apikey:secret};
  if(!secret.startsWith("sb_secret_"))headers.Authorization="Bearer "+secret;
  const r=await fetch(Deno.env.get("SUPABASE_URL")+"/rest/v1/rpc/player_chat_sync_event",{method:"POST",headers,body:JSON.stringify({p_scope:scope,p_event_key:event?channel+"::"+event.event_id:null,p_title:event?.title||null,p_end:event?new Date(utc(event.end_time_utc)).toISOString():null})});
  if(!r.ok)throw Error();
  return Response.json({ok:true,room:await r.json(),checked_at:new Date().toISOString()},{headers:cors});
 }catch{return Response.json({ok:false,error:"Live status unavailable"},{status:503,headers:cors});}
});
