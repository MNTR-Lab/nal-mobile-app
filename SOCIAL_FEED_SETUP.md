# NAL Network — Facebook Social Feed

This ZIP contains the **complete existing website/index.html**, with an added live Facebook feed renderer, and a Cloudflare Pages Function at `functions/api/social/facebook.js`. Existing routes, team pages, fan forum, shop, and Social layout are preserved.

## One-time Cloudflare setup

1. Commit both `website/index.html` and `functions/api/social/facebook.js` to `nal-network-web` (keep the folder structure).
2. In the Cloudflare Pages project that serves the **preview**, add an encrypted environment variable / secret named `FACEBOOK_PAGE_ACCESS_TOKEN` with the **Facebook Page access token** (not an app token or a user token). Do not paste the token into GitHub or the HTML. Configure the preview environment; production can be configured separately later.
3. Redeploy the preview and visit `/social`. Confirm that `/api/social/facebook` returns `{ "ok": true, "posts": [...] }` and the Social page displays real posts.
4. If the endpoint responds with 503, the secret is missing. If it responds with 502, check Cloudflare function logs and the token's Page permissions / validity.

**IMPORTANT Cloudflare Pages build-directory note:** This project stores its site under `website/`. For a Pages project whose **root directory is the repository root** and **build output directory is `website`**, the `functions/` directory in this ZIP is correct. If your Pages project instead sets its **root directory to `website`**, move the function to `website/functions/api/social/facebook.js` or adjust the Pages root settings; the function must live under the configured Pages project root.

The Facebook Graph API test previously returned real NAL posts for Page ID `382815872049803`, but the server-side Cloudflare token and deployment have **not** been tested here. Facebook permissions and token lifetime remain subject to Meta. This implementation shows recent Facebook posts with available images and links to reels/videos; it does not stream native video inline. Instagram, TikTok, and X buttons remain outbound links pending separate authorized integrations. Feed cache is approximately 15 minutes per Cloudflare edge location.

No live site deployment or GitHub changes have been made by this ZIP creation.
