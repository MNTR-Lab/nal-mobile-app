# NAL League Portal

Custom NAL-branded directory at `portal.nal-network.com`. Staff never open Monday.com. All reads and writes occur server-side against the private NAL Directory board (`18439266861`).

## Deployment prerequisites

Deploy `worker.js` as a Cloudflare Worker with a custom domain `portal.nal-network.com`. **Do not make this publicly accessible until Cloudflare Access is configured and verified.** The Worker fails closed without a valid Access JWT and explicit email allowlist.

Configure Worker secrets:
- `MONDAY_API_TOKEN`: Monday API token with access to the new private board. Never place this token in frontend code or Git.
- `ACCESS_TEAM_DOMAIN`: Cloudflare Access team domain (e.g. `yourteam.cloudflareaccess.com`).
- `ACCESS_AUD`: Access application audience tag.
- `PORTAL_PERMISSIONS`: JSON object keyed by lowercased staff email, for example `{"commissioner@example.org":{"role":"admin","teams":[]},"owner@example.org":{"role":"team","teams":["Omaha Beef"]}}`.

Protect the entire custom domain with a Cloudflare Access application and an explicit allow policy. JWT verification in the Worker is an additional layer, not a replacement for the Access policy.

## Features

- NAL-branded directory, search, team filter, slide-out Add/Edit form.
- Backend reads the Monday board and maps column IDs from board column titles.
- Team-scoped server-side edit authorization; league administrators can edit all teams.
- API requests require a verified Access JWT and email in `PORTAL_PERMISSIONS`.
- No Monday links, forms, iframes or browser-side API credentials.

## Required testing before staff launch

1. Confirm Monday board columns correspond to Name, Team / Affiliation, Position / Role, Email Address, Phone Number, Additional Information.
2. Test board read, create, update, and correct name updates with a disposable record.
3. Test super-admin, authorized owner, unauthorized team member, and anonymous requests. Verify cross-team edits are rejected.
4. Check mobile layout and ensure personal data is never cached publicly.
5. Review Cloudflare Access audit logs and create a recovery/rollback plan.

This branch contains the implementation source; it is **not** evidence that the custom domain, secrets, Access policies, or deployment are live.
