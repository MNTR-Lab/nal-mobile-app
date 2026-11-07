import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MONDAY_API_URL = "https://api.monday.com/v2";
const BOARD_ID = "18421027719";
const APPROVED_GROUP = "group_mm5251en";

const COL = {
  activeRoster: "boolean_mm58fd1p",
  status: "color_mm581gnf",
  date: "date_mm529ngc",
  organization: "single_selectrkknj7l",
  transactionType: "single_select4w70vhf",
  firstName: "short_textqgu7jmng",
  lastName: "short_text8mqlqiik",
  position: "single_select2j27cbs",
  height: "short_text83a4xfpd",
  weight: "short_textk8t1m1zy",
  college: "short_textemwe53jr",
  proExperience: "short_texta2nd7kpg",
  injuryLength: "single_selectwfkfsod",
  suspensionReason: "long_text4yeqsbzs",
};

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { ...cors, "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

async function mondayRequest(query: string, variables: Record<string, unknown>) {
  const token = Deno.env.get("MONDAY_API_TOKEN");
  if (!token) throw new Error("MNTR+ Database token is not configured.");
  const r = await fetch(MONDAY_API_URL, {
    method: "POST",
    headers: { Authorization: token, "Content-Type": "application/json", "API-Version": "2026-07" },
    body: JSON.stringify({ query, variables }),
  });
  const out = await r.json();
  if (!r.ok || out.errors) throw new Error(out.errors ? JSON.stringify(out.errors) : "MNTR+ Database request failed.");
  return out.data;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ success: false, error: "Method not allowed" }, 405);

  try {
    const authHeader = req.headers.get("Authorization") || "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    if (!token) return json({ success: false, error: "Super Admin login required." }, 401);

    const url = Deno.env.get("SUPABASE_URL")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(url, serviceKey, { auth: { persistSession: false } });

    const { data: userData, error: userError } = await supabase.auth.getUser(token);
    if (userError || !userData.user) return json({ success: false, error: "Your Super Admin session is invalid or expired." }, 401);

    const { data: admin } = await supabase
      .from("nal_super_admins")
      .select("user_id,is_active")
      .eq("user_id", userData.user.id)
      .eq("is_active", true)
      .maybeSingle();

    if (!admin) return json({ success: false, error: "Super Admin authorization required." }, 403);

    const body = await req.json();
    const player = body?.player || {};
    const rosterStatus = String(body?.rosterStatus || "");
    const reason = String(body?.reason || "").trim();
    const injuryLength = String(body?.injuryLength || "").trim();

    const map: Record<string, { type: string; active: boolean }> = {
      "Active Roster": { type: "Signing", active: true },
      "Injured Reserve": { type: "Injury Report", active: false },
      "Commissioner's Exempt List": { type: "Commissioner's Exempt List (MAX 3)", active: false },
      "Suspended": { type: "Team/League Suspension", active: false },
      "Released": { type: "Release", active: false },
    };
    const selected = map[rosterStatus];
    if (!selected) return json({ success: false, error: "Unsupported roster status." }, 400);
    if (!player.firstName || !player.lastName || !player.organization) return json({ success: false, error: "Player name and organization are required." }, 400);
    if (rosterStatus === "Suspended" && !reason) return json({ success: false, error: "A suspension reason is required." }, 400);
    if (rosterStatus === "Injured Reserve" && !injuryLength) return json({ success: false, error: "Select an injury designation." }, 400);

    const values: Record<string, unknown> = {
      [COL.activeRoster]: { checked: selected.active ? "true" : "false" },
      [COL.status]: { label: "Approved" },
      [COL.date]: { date: new Date().toISOString().slice(0,10) },
      [COL.organization]: { label: player.organization },
      [COL.transactionType]: rosterStatus === "Suspended" ? { index: 6 } : { label: selected.type },
      [COL.firstName]: player.firstName,
      [COL.lastName]: player.lastName,
    };
    if (player.position) values[COL.position] = { label: player.position };
    if (player.height) values[COL.height] = player.height;
    if (player.weight) values[COL.weight] = player.weight;
    if (player.college) values[COL.college] = player.college;
    if (player.professionalExperience) values[COL.proExperience] = player.professionalExperience;
    if (rosterStatus === "Injured Reserve") values[COL.injuryLength] = { label: injuryLength };
    if (rosterStatus === "Suspended") values[COL.suspensionReason] = reason;

    const mutation = `mutation ($board: ID!, $group: String!, $name: String!, $values: JSON!) {
      create_item(board_id: $board, group_id: $group, item_name: $name, column_values: $values) { id name }
    }`;
    const result = await mondayRequest(mutation, {
      board: BOARD_ID,
      group: APPROVED_GROUP,
      name: `${player.firstName} ${player.lastName} — ${rosterStatus}`,
      values: JSON.stringify(values),
    });

    return json({ success: true, item: result?.create_item || null, rosterStatus });
  } catch (e) {
    console.error(e);
    return json({ success: false, error: e instanceof Error ? e.message : "Unknown server error" }, 500);
  }
});