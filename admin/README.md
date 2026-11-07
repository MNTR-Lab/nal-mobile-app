# NAL Network Staff Admin

Production: https://admin.nal-network.com/

The standalone Cloudflare Worker `nal-network-admin` serves this dashboard. It does not replace the public Pages site. Source lives on `nal-network-web` in the existing NAL repository.

## Services

- Supabase project `rcoaprzmutcwlpugobry`: the same Auth users and profiles as the NAL Forum.
- `nal-network-admin` Edge Function: verifies the user with Auth on every request, checks active profile role and the existing `nal_super_admins` allowlist, handles polls, staff access, assets, transaction reads, and roster-update forwarding.
- `fcf-api`: existing Fan Choice Friday workflow, including Monday Game Library board 18436132233.
- `nal-operations-api` and `nal-roster-admin`: existing transaction and roster workflows for board 18421027719.
- Digital Asset Management board 18437455062: reads and metadata edits use the dedicated FCF/MNTR+ Monday token, falling back to the shared token only when the dedicated secret is absent. Attachments are listed, uploaded, previewed, and downloaded through authenticated dashboard endpoints.

Server credentials are read from existing Supabase environment secrets. The frontend config contains only the same public publishable key already used by the website. Never put service-role or Monday credentials in this directory.

## Access

Active `admin` profiles can access all content sections. Active `moderator` profiles can manage general fan polls. Members of `nal_super_admins` who also have an active admin profile can manage staff, see activity, and invoke roster writes. Existing super-admin accounts are protected from staff-role changes through this API. Granting ordinary admin does not grant super admin.

The designated owner's existing Forum account is in that allowlist. The server-side app metadata designation is retained, but authorization uses fresh database checks rather than user-editable metadata or stale browser claims.

`website/admin/session-bridge.html` and its scripts exchange sessions only between the exact admin origin and the two public website origins through `postMessage`. Both source window and origin are checked. No tokens are placed in URLs. If the browser cannot share a session, the same Forum credentials work in the dashboard sign-in form.

## Deploy

Upload `worker.js` as an ES module and `index.html`, `admin.css`, `app.js`, `config.js`, `transactions.js`, `staff-invites.js`, and `workspace.js` as text modules to Worker `nal-network-admin`. Compatibility date: 2026-11-06. Enable observability and traces. Bind custom domain admin.nal-network.com in zone 24249123560a6f348a31a3f2589a225e, account 0b83177a971bd8fcfad88ed4e531eb50.

Deploy `supabase/functions/nal-network-admin/index.ts` with its sibling `workspace.ts` as Edge Function `nal-network-admin`. Platform JWT verification is disabled because the handler performs `auth.getUser(jwt)` itself before every operation, then enforces profile and super-admin checks.

The existing public Pages deployment publishes the session bridge and /admin redirects from the website directory when this branch updates.

## Checks

```
node --check admin/app.js
node --check website/admin/session-bridge.js
node --test admin/tests/security.test.cjs
```

Fan Choice Friday changes go through its existing API; its existing vote-preservation and choice-edit restrictions still apply. Transaction submissions, metadata corrections, and review statuses are managed in the dashboard; existing contract/signature columns are preserved. Roster status changes create approved transactions via the existing API. Additional boards and arbitrary publishing mappings are intentionally not exposed until their workflows are specified.

Database migration `extend_admin_activity_for_network_dashboard` extends the existing audit action constraint with poll, asset, roster, and Fan Choice Friday events while retaining all existing action types.

## Staff workflow update (November 6, 2026)

Closed general polls are excluded from the dashboard query; their stored votes and records remain intact. The Activity Log view has a fixed reset cutoff of 2026-11-06 00:00 America/New_York (05:00 UTC), so future activity remains visible without a rolling daily reset. The staff list includes `verified`, `moderator`, and `admin` accounts, excluding fans and VIP-only accounts.

The Transactions tab follows the existing league `team-portal.html` interface: summary counts, four filters, pending queue with elapsed waiting time, recent ten/all toggle, and player detail sheet. Native editing and roster updates use the existing board and API.

Super admins can create accounts and choose email delivery or generate an acceptance link. Link generation does not send email. New invitees remain `verified` and blocked from dashboard actions until email verification and acceptance. Their intended access is stored in server-controlled app metadata; the acceptance endpoint ignores client-supplied roles. The acceptance page lets them choose one password shared with the Forum. Existing eligible accounts can receive access links without duplicating their account or changing its role. Native email delivery uses the project's existing SMTP configuration and redirects through the /admin/accept-invite return page on the allowed Forum origin, which saves the accepted session and continues to the staff dashboard. Generated acceptance links verify directly on the admin domain and do not depend on the Auth redirect allowlist. Email failures are shown as failures, with link generation offered as an alternative.

Audit migration `add_staff_invitation_audit_events` preserves prior action types and adds `staff_invited` and `staff_invite_accepted`.

## League email eligibility

The staff directory also includes existing Auth accounts with the exact, case-insensitive email suffix `@thenationalarenaleague.com`, regardless of their current profile role. Eligibility is checked from Auth records on the server when listing accounts, assigning roles, or sending access links. Directory inclusion alone never grants dashboard access or changes profile roles. Existing NAL Verified staff and protected administrators remain listed.

## Strict staff domain restriction

Only Auth accounts ending in `@mntrlab.com` or `@thenationalarenaleague.com` may access this dashboard, appear in its staff directory, receive staff invitations/access links, or be assigned permissions here. Matching is case-insensitive and exact. The server applies this check before returning account information or processing invitation acceptance, including for existing admins and super admins. Assigned roles, active status, and super-admin protections still apply. Outside-domain accounts retain their separate Forum accounts and existing Forum roles; this restriction concerns the admin dashboard. This restriction supersedes the earlier directory rule that listed all verified/admin/moderator accounts.

## Dashboard checkboxes and Forum badges

Per-person dashboard sections are stored in server-controlled Auth app metadata (`nal_network_sections`). An explicit empty list revokes dashboard tools. When the field is absent, existing admin/moderator defaults are retained for compatibility. Server authorization checks each requested section on every call; menu visibility is not the access boundary. Staff permission management and roster writes remain protected super-admin actions. Activity Log can be assigned separately.

Saving dashboard checkboxes does not modify the person's Forum role or badge. New invitations carry a pending section list and keep the Forum role `verified`; the selected sections activate only after invitation acceptance. The existing Fan Choice Friday API also checks the same section grants and allowed email domains.

`profiles.forum_badge` is a nullable presentation override, protected from client-side edits. Forum author display falls back to the profile role when no override exists. The owner's existing account has the `verified` override, preserving the blue NAL Employee verification icon while retaining its admin role and super-admin authorization. Migration `separate_forum_badges_and_dashboard_permissions` adds the override protection and permissions audit event.

## Native Monday workspaces (November 6, 2026)

The dashboard reads and writes the existing boards without sending staff to Monday. Transactions support new records, corrections, and Pending/Approved/Needs Action review statuses with stale-edit detection. Contract and signature columns are preserved; the native form does not collect signatures.

Digital assets support metadata editing, category selection on creation, and attachment uploads up to 20 MiB per file. Attached raster images and PDFs can be previewed; other uploaded files can be downloaded. External cloud-document links are listed but must have a local copy attached to use the native preview/download workflow. Download requests verify both board and item membership and stream fresh authorized asset content with sandbox headers.

The Fan Choice Friday game library supports adding and editing game metadata, media URLs, and game/highlight approval statuses. Connected Workspaces displays connection status and opens each native dashboard module, subject to its assigned section permissions.

Migration `audit_native_monday_workspace_writes` adds transaction and library audit events while preserving prior actions. Run `node --test admin/tests/*.test.cjs` for the full authorization and workflow suite.

## Social Media Schedule (November 7, 2026)

`/social#social` is the native NAL planning desk for Monday board `18437085764`. All API reads and writes enforce exact case-insensitive Organization=NAL, including file downloads and archival, so shared-board MNTR+ and team records stay outside this dashboard. New posts are assigned NAL and Client Visible=No on the server. Existing audience, client visibility, and attachments are preserved by edits. Staff access is controlled by the `social` permission checkbox; existing explicitly assigned section lists do not gain this permission automatically.

The board retains its existing Draft/Scheduled/Posted/Rejected labels and now also supports Pending Review and Approved. Asset Link is `link_mm8wqjxz`; original uploaded Post Media remains `file_mm8gwyhd`. The page supports a seven-day view, all-post list, platform/status/search filters, creation, editing, duplication, archival, captions, campaign, assignments, creative links, existing attachment downloads, and published links. Staff publish manually on each platform. Native calendar date and Publish At ET are updated together; legacy dates normalize to Eastern wall-clock time. Edits and archives reject stale updated_at values.

Deployment adds `social.js` to the Worker text modules, `social.ts` to the admin Edge Function, and `/social`, `/social/files`, `/social/download` to the gateway allowlist. No additional database table or duplicate calendar is created. API write events are recorded in structured Worker logs; Monday retains item history.

Verification: 66 automated checks passed. In the production dashboard, a private test was created as Draft, edited to Scheduled at 2026-11-08 12:30 ET, and independently read from Monday to verify the native date, NAL organization, private visibility, platforms, caption, and Completed / Scheduled group. Test item 13495697650 was archived after verification.
