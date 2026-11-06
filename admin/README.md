# NAL Network Staff Admin

Production: https://admin.nal-network.com/

The standalone Cloudflare Worker `nal-network-admin` serves this dashboard. It does not replace the public Pages site. Source lives on `nal-network-web` in the existing NAL repository.

## Services

- Supabase project `rcoaprzmutcwlpugobry`: the same Auth users and profiles as the NAL Forum.
- `nal-network-admin` Edge Function: verifies the user with Auth on every request, checks active profile role and the existing `nal_super_admins` allowlist, handles polls, staff access, assets, transaction reads, and roster-update forwarding.
- `fcf-api`: existing Fan Choice Friday workflow, including Monday Game Library board 18436132233.
- `nal-operations-api` and `nal-roster-admin`: existing transaction and roster workflows for board 18421027719.
- Digital Asset Management board 18437455062: reads and metadata edits use the dedicated FCF/MNTR+ Monday token, falling back to the shared token only when the dedicated secret is absent. Attachments are managed through authenticated Monday links.

Server credentials are read from existing Supabase environment secrets. The frontend config contains only the same public publishable key already used by the website. Never put service-role or Monday credentials in this directory.

## Access

Active `admin` profiles can access all content sections. Active `moderator` profiles can manage general fan polls. Members of `nal_super_admins` who also have an active admin profile can manage staff, see activity, and invoke roster writes. Existing super-admin accounts are protected from staff-role changes through this API. Granting ordinary admin does not grant super admin.

The designated owner's existing Forum account is in that allowlist. The server-side app metadata designation is retained, but authorization uses fresh database checks rather than user-editable metadata or stale browser claims.

`website/admin/session-bridge.html` and its scripts exchange sessions only between the exact admin origin and the two public website origins through `postMessage`. Both source window and origin are checked. No tokens are placed in URLs. If the browser cannot share a session, the same Forum credentials work in the dashboard sign-in form.

## Deploy

Upload `worker.js` as an ES module and `index.html`, `admin.css`, `app.js`, and `config.js` as text modules to Worker `nal-network-admin`. Compatibility date: 2026-11-06. Enable observability and traces. Bind custom domain admin.nal-network.com in zone 24249123560a6f348a31a3f2589a225e, account 0b83177a971bd8fcfad88ed4e531eb50.

Deploy `supabase/functions/nal-network-admin/index.ts` as Edge Function `nal-network-admin`. Platform JWT verification is disabled because the handler performs `auth.getUser(jwt)` itself before every operation, then enforces profile and super-admin checks.

The existing public Pages deployment publishes the session bridge and /admin redirects from the website directory when this branch updates.

## Checks

```
node --check admin/app.js
node --check website/admin/session-bridge.js
node --test admin/tests/security.test.cjs
```

Fan Choice Friday changes go through its existing API; its existing vote-preservation and choice-edit restrictions still apply. Transaction approvals and contract review remain in Monday; roster status changes create approved transactions via the existing API. Additional boards and arbitrary publishing mappings are intentionally not exposed until their workflows are specified.

Database migration `extend_admin_activity_for_network_dashboard` extends the existing audit action constraint with poll, asset, roster, and Fan Choice Friday events while retaining all existing action types.
