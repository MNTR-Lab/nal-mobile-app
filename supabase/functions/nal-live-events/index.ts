
const cors={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,apikey,content-type","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json","Cache-Control":"no-store"};
const allowed=new Set(["72169","72160","72161","72162","72163","72164","72165","72166","72167","72168","72158"]);
Deno.serve(async req=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors});
 if(req.method!=="GET")return Response.json({error:"Read-only endpoint"},{status:405,headers:cors});
 const channel=new URL(req.url).searchParams.get("channelId")||"72169";
 if(!allowed.has(channel))return Response.json({error:"Invalid channel"},{status:400,headers:cors});
 try{
  const env=Deno.env.toObject();
  const secretMap={"72169":"Network Originals - Live (NAL)","72160":"Amarillo Live (NAL)","72162":"Dallas Apex (Live)","72163":"Louisiana Rouxgaroux (Live)","72164":"Omaha Beef (Live)","72165":"Pueblo Punishers (Live)","72166":"Salina Liberty (Live)","72167":"Sioux City Bandits (Live)","72168":"Southwest Kansas Storm (Live)","72158":"Wheeling Miners (Live)"};
  const explicit=["LIGHTCAST_LIVE_API_KEY","LIGHTCAST_NETWORK_LIVE_API_KEY","LIGHTCAST_NAL_NETWORK_API_KEY","NAL Network Live","Live (NAL)"];
  let key=env[secretMap[channel]]||(channel==="72169"?explicit.map(n=>env[n]).find(Boolean):null);
  if(!key){
   const accountId=env.LIGHTCAST_ACCOUNT_ID,accountKey=env.LIGHTCAST_ACCOUNT_API_KEY;
   if(!accountId||!accountKey)throw Error("Existing Lightcast account credentials unavailable");
   const u=new URL("https://www.lightcast.com/api/public/v1/channels");
   u.search=new URLSearchParams({action:"channels",accountId,apiKey:accountKey,channelId:channel,subchannels:"false"}).toString();
   const r=await fetch(u,{signal:AbortSignal.timeout(15000)});
   const data=await r.json();
   const candidates=[];function walk(v){if(!v||typeof v!=="object")return; if(!Array.isArray(v))candidates.push(v);for(const x of Object.values(v))if(x&&typeof x==="object")walk(x);}walk(data);
   const node=candidates.find(v=>String(v.channel_id||v.channelId||v.id)===channel);
   if(node){for(const [n,v] of Object.entries(node))if(/api.?key/i.test(n)&&typeof v==="string")key=v;}
   if(!key)return Response.json({ok:false,error:"Channel credential mapping required",channelId:channel,},{status:503,headers:cors});
  }
  const u=new URL("https://www.lightcast.com/api/public/v1/events");u.search=new URLSearchParams({action:"getEvents",channelId:channel,channelApiKey:key,count:"250",timezone:"UTC",ssl:"true"}).toString();
  const r=await fetch(u,{signal:AbortSignal.timeout(15000)});const d=await r.json();
  if(!r.ok||d.error)throw Error("Lightcast events request failed");
  const raw=Array.isArray(d)?d:Array.isArray(d.events)?d.events:Array.isArray(d.data)?d.data:d.event_id?[d]:[];
  const events=raw.filter(e=>e.event_id).map(e=>({event_id:String(e.event_id),channel_id:channel,title:String(e.name||""),start_time_utc:e.start_time_utc,end_time_utc:e.end_time_utc}));
  return Response.json({ok:true,channelId:channel,checked_at:new Date().toISOString(),events},{headers:cors});
 }catch{return Response.json({ok:false,error:"Live event status temporarily unavailable"},{status:502,headers:cors});}
});
