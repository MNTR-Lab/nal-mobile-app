// Cloudflare Pages Function: GET /api/social/facebook
// Configure FACEBOOK_PAGE_ACCESS_TOKEN as an encrypted Pages secret.
const PAGE_ID = '382815872049803';
const GRAPH_VERSION = 'v26.0';
const TTL_SECONDS = 900;
const FIELDS = 'id,message,created_time,permalink_url,full_picture,attachments{media_type,type,media,target,subattachments}';
export async function onRequestGet({ request, env }) {
  const headers = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers });
  if (!env.FACEBOOK_PAGE_ACCESS_TOKEN) return response({ ok: false, message: 'Facebook feed is not configured.' }, 503);
  const cache = caches.default;
  const cacheKey = new Request(new URL('/api/social/facebook', request.url).toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return cached;
  try {
    const endpoint = new URL(`https://graph.facebook.com/${GRAPH_VERSION}/${PAGE_ID}/posts`);
    endpoint.searchParams.set('fields', FIELDS);
    endpoint.searchParams.set('limit', '15');
    // POST keeps the token out of query URLs and browser-visible requests.
    const upstream = await fetch(endpoint.toString(), {
      method: 'GET',
      headers: { Authorization: `Bearer ${env.FACEBOOK_PAGE_ACCESS_TOKEN}` },
      signal: AbortSignal.timeout(10000)
    });
    const json = await upstream.json();
    if (!upstream.ok || json.error) {
      console.error('NAL Facebook API error', json.error?.code, json.error?.type);
      return response({ ok: false, message: 'Facebook is not currently returning posts.' }, 502);
    }
    const posts = (Array.isArray(json.data) ? json.data : []).map(post => {
      const attachment = post.attachments?.data?.[0];
      return {
        id: String(post.id || ''),
        message: String(post.message || '').slice(0, 4000),
        created_time: post.created_time || null,
        permalink_url: /^https:\/\/(www\.)?facebook\.com\//.test(post.permalink_url || '') ? post.permalink_url : `https://www.facebook.com/${PAGE_ID}`,
        full_picture: /^https:\/\//.test(post.full_picture || '') ? post.full_picture : null,
        is_video: attachment?.media_type === 'video' || attachment?.type === 'video_inline' || /\/reel\//.test(post.permalink_url || '')
      };
    });
    const result = response({ ok: true, platform: 'facebook', posts });
    result.headers.set('cache-control', `public, max-age=${TTL_SECONDS}`);
    request && result.headers.set('access-control-allow-origin', new URL(request.url).origin);
    await cache.put(cacheKey, result.clone());
    return result;
  } catch (err) {
    console.error('NAL Facebook feed request failed', err?.name || 'unknown');
    return response({ ok: false, message: 'Facebook feed temporarily unavailable.' }, 502);
  }
}
