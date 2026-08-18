# Panther Peptides · Jarvis v150

Jarvis is the owner-facing operating agent for Panther Peptides. The owner talks to Jarvis in natural language; the dashboard exists to show Jarvis's business state, tasks, approvals, inventory, training, documents, connections, durable memory, and permission tiers.

**Required customer-facing positioning:** FOR RESEARCH USE ONLY — NOT FOR HUMAN OR VETERINARY USE.

## Easiest way to start

### Mac
Double-click **Start Jarvis.command**. The first launch creates a private Python environment, installs Jarvis dependencies, starts the local server, and opens the browser setup wizard.

### Windows
Double-click **Start Jarvis.bat**. The first launch creates a private Python environment, installs Jarvis dependencies, starts the local server, and opens the browser setup wizard.

If Python is not installed, the launcher tells the owner where to install it. No code editing is required.

## First-run wizard
The browser wizard collects only the owner-facing setup information: name, domain, support email, margin target, optional OpenAI API key, and optional Shopify credentials. Connection settings entered in Jarvis persist on its data volume; secret values are encrypted at rest and are not displayed back in the UI.

Jarvis works in **local control mode** even before an OpenAI key is connected: it can read inventory, tasks, approvals, setup state and blockers. Once an OpenAI API key is connected, Jarvis uses the OpenAI Agents SDK for natural-language reasoning and tool orchestration.

## Jarvis Inbox
Use the **Jarvis Inbox** tab to upload PDF, XLSX, CSV, TXT, Markdown, or JSON documents such as supplier pricing guides, invoices, COAs and inventory files. Jarvis extracts searchable text and can use uploaded business documents as operating context.

## Current starting inventory
The system records the owner's 90 starting vials and $855 landed cost. Because the physical vials arrived unlabeled and without verifiable supplier lot/batch documentation or COAs, every starting lot remains quarantined with zero available-for-sale units. Jarvis cannot fabricate provenance or release these lots automatically.

## Jarvis permission ladder
Each workflow can be assigned one of five authority levels: **Observe → Recommend → Draft → Approval → Auto**. High-risk actions are hard-capped at Approval, including product publication, lot release, supplier approval, purchase orders, consequential refunds, marketing sends, payment-setting changes, and destructive data actions. Jarvis records proposed actions in an audit ledger.

## Durable owner memory
The **Memory** screen stores stable business preferences and operating policies that Jarvis should carry across sessions. Do not put passwords or API secrets in memory.

## Shopify order intake
Jarvis includes a signed Shopify `orders/create` webhook endpoint. Once the Shopify webhook secret and store credentials are configured, Shopify orders can flow into Jarvis automatically. Orders only allocate from released inventory; unknown SKUs or insufficient released inventory create high-priority owner tasks instead of being guessed or silently fulfilled.


## Customer communications
Jarvis now includes a customer communications queue. An authenticated inbound-email webhook can create support tickets automatically, classify risk, and produce conservative replies. Standard SMTP can deliver outbound transactional support email when configured. Human-use/medical questions are hard-locked to a research-only refusal template and always require owner approval; a custom reply cannot override that safety behavior.

## Shopify continuous order sync
In addition to the signed `orders/create` webhook, Jarvis can read recent paid Shopify orders through the Admin GraphQL API and map line items by SKU. Orders with missing SKU mappings or insufficient released inventory are blocked and turned into owner tasks. Optional background polling can be enabled with the `shopify_auto_sync` company setting after Shopify is connected. Shopify documents the Admin GraphQL `orders` query as suitable for order/fulfillment automation.

## Shipping preparation
Jarvis can create shipment requests from fulfillment tasks, carry forward the shipping address, and prepare carrier/service selections. Buying a shipping label remains approval-gated because it incurs a charge. The current build intentionally does not pretend a label was purchased unless a real shipping-provider connector returns success.

## Continuous operation / deployment
Docker Compose uses `restart: unless-stopped` and includes a health check. `render.yaml` and `Procfile` are included as hosted-deployment scaffolding. Hosted use should run behind HTTPS with owner authentication, persistent storage, backups, and secure cookie mode enabled. v12 includes these controls and reports deployment blockers in the Launch/System screens.


## Checkpoint 100 production stack
Jarvis v150 consolidates the production runtime through six additional control stages:

- **v75 Service assurance:** released-inventory reservations, lot-expiry monitoring, support SLA checks, supplier review scheduling, and consolidated service-assurance scoring.
- **v80 Governance v2:** hashed research-only policy snapshots, lot release dossiers, document validation, zero-default risk budgets, and governance scoring.
- **v85 Business planning:** demand forecasts, inventory-aging risk, cash-runway snapshots, SKU concentration analysis, and a side-effect-free planning cycle.
- **v90 Continuity:** dependency inventory, verified backup checks, tabletop recovery drills, continuity plans, and continuity scoring.
- **v95 Security posture:** internal security events, secret-rotation review, owner-access review, tamper-evident audit checkpoints, and consolidated security scoring.
- **v100 Governor:** explicit autonomy contracts, go-live certification, maturity scoring, self-evaluation, owner briefing, and a bounded governor loop that processes only allow-listed internal work.

All v100 analytical/governance cycles report `external_side_effects: false`. High-risk actions remain owner-gated and the hard research-only policy cannot be converted into an auto-execution path by the governor.

## Development checks
Run `pytest -q`. The current package includes the full regression suite through checkpoint 100, including policy, lot release, procurement, fulfillment, starting inventory quarantine, first-run setup, local Jarvis operation, document inbox, permission tiers, durable memory, Shopify webhook signatures/order sync, customer communications, shipping approvals, continuity, security posture, governance, planning, and governor controls.


## Owner security

Jarvis retains the owner password created during first-run setup, PBKDF2-SHA256 password hashing, signed 12-hour session cookies, same-origin checks on write actions, a security audit log, and rolling local SQLite backups. Shopify webhooks remain outside the owner session gate but still require their Shopify HMAC signature.

The first-run setup route is public only until an owner password exists. After setup, the setup screen and all business APIs require an authenticated owner session.

## Backups

Jarvis creates a rolling database backup automatically during the business heartbeat when the newest backup is more than 20 hours old. The owner can also create a backup from the Security tab. The newest 14 database backups are retained under `data/backups/`.

## Jarvis v8 additions

- Owner notification center with deduplicated approval alerts.
- Optional owner email alerts using the existing SMTP connection.
- EasyPost shipping adapter for live rate shopping and label purchase.
- Shipping-label charges remain owner-approval gated. Jarvis cannot buy postage until the corresponding approval is approved.
- Hosted Render configuration now includes persistent storage and placeholders for shipping/email secrets.

### EasyPost connection (optional)
Set `EASYPOST_API_KEY` plus the `SHIP_FROM_*` address variables. Jarvis can then quote rates without spending money. Label purchase requires a pending shipping-label approval to be approved first.

## v9 command center and installable owner app
Jarvis v9 adds a deterministic owner command center at `/owner/command-center`. It ranks persisted business state into two queues: items that require the owner and items Jarvis can operate on internally. This is intentionally separate from model-generated prose so urgent business state is not dependent on AI interpretation.

The owner console is also a Progressive Web App. On supported browsers, use **Add to Home Screen / Install App** to launch Jarvis like a private app on a phone, tablet, or computer. Authentication and approval rules remain enforced by the server.

## Jarvis v10: hosted launch path

v10 moves connection configuration into Jarvis's persistent data volume. Credentials entered through the owner-only **Launch** screen are written to `data/jarvis.env` locally, or alongside the configured database path when hosted. The application reloads that persistent configuration on startup, so a host restart does not discard connections.

The **Launch** tab provides a deterministic readiness checklist and shows operating blockers separately from optional integrations. Starting inventory remains a hard live-sales blocker until a documented lot is released through the existing quality and owner-approval workflow.

Jarvis can now configure OpenAI, Shopify, SMTP email, EasyPost, owner notifications, and the ship-from address from the protected browser console. Secret values are never returned by the setup-summary API. The Security screen also provides an authenticated download link for the newest SQLite database backup.

For hosted operation, `render.yaml` attaches `/app/data` as persistent storage. Because `DATABASE_PATH=/app/data/operator.db`, Jarvis automatically stores persistent configuration at `/app/data/jarvis.env` unless `JARVIS_CONFIG_PATH` is explicitly set.

## Jarvis v11: hosted reliability and connection diagnostics

v11 adds owner-visible system health and safe connection diagnostics. The **Connections** tab can test OpenAI, Shopify, and SMTP without sending a customer message; shipping setup can be checked without creating a billable shipment. The **System** tab reports database integrity, persistent-volume writeability, backup retention, uptime, heartbeat state, and deployment blockers.

Backups now follow `DATABASE_PATH` and live on the same persistent volume as the business database. This fixes an important hosted-deployment edge case where a container-local backup directory could disappear on redeploy.

Deployment templates are included for Render, Railway, Fly.io, and Docker Compose. Actual hosting still requires an owner-controlled hosting account and must use HTTPS, a persistent volume, and secret environment variables.

## Jarvis v12 production controls

- Connection secrets saved from the Launch screen are encrypted at rest in `jarvis.secrets.enc`. Jarvis uses `JARVIS_MASTER_KEY` when supplied by the host; otherwise it creates a restricted `jarvis.key` on the same persistent data volume. Keep that key with the deployment and do not publish it.
- The Launch screen now includes a deterministic go-live checklist covering owner security, persistent storage, backups, released inventory, Shopify, email, and shipping.
- **Safe Mode** is an owner emergency switch. It pauses outbound/paid external actions (customer email, Shopify product creation, shipping-label purchase, owner notification email) while leaving Jarvis available for analysis, drafts, tasks, and approvals.
- Existing plaintext secrets from older `jarvis.env` files are automatically migrated into encrypted storage when v12 first loads.

### Shopify own-store authentication
Jarvis v12 can use either a traditional Admin access token or Shopify client credentials for an app built for the owner's own store. With client credentials configured, Jarvis requests and caches the short-lived Shopify Admin API token automatically, so the owner does not need to paste a new token every day.


## v14 production hardening
- Hosted first-run claim protection before an owner password exists.
- Render generates a private bootstrap claim token automatically.
- Encrypted portable `.jarvis-recovery` exports containing the business database and persistent configuration.
- Recovery bundle verification from the owner console without mutating live business data.
- Historical checkpoint note; current v20 regression suite contains 78 passing tests.


## v14 reliability additions
Jarvis v14 adds an incident center for repeated system/integration failures and a guarded encrypted recovery restore workflow. Recovery restore requires Safe Mode, an exact typed confirmation, database integrity validation, and creates a pre-restore backup before replacement.

## Jarvis checkpoints 15–20

The v20 checkpoint consolidates six reliability/operations layers added after v14:

- **v15 — Incident runbooks:** deterministic recovery guidance for Shopify, backup, email, shipping, security, and unknown incidents. Runbooks never bypass approval gates.
- **v16 — Idempotency ledger:** persistent keys for duplicate-resistant external/event processing and diagnostics.
- **v17 — Approval health:** pending approvals are aged into fresh/stale/critical bands, with deduplicated owner tasks for stale decisions.
- **v18 — Privacy controls:** owner-visible inventory of customer contact data plus a Safe-Mode-only, exact-confirmation pseudonymization workflow.
- **v19 — Background job ledger:** durable run history and single-active-run locking primitives for unattended jobs.
- **v20 — Executive brief and production gate:** a deterministic owner brief plus a consolidated go-live gate combining database integrity, storage, owner security, Safe Mode, stale approvals, and deployment readiness.

These additions do not change the core inventory rule: undocumented/unverified starting vials remain quarantined and cannot be released automatically.


## Jarvis v35: supervised operating runtime

Jarvis v35 adds an internal event journal, a safe recurring-job scheduler, an explicit capability gate, a durable internal work queue with leasing/retry/dead-letter behavior, a persisted owner daily digest, and a bounded runtime supervisor. The runtime only executes allow-listed internal work and the existing internal-only operating cycle. It cannot use the scheduler or work queue to publish, purchase, refund, send marketing, buy postage, approve suppliers, or release inventory. Those actions remain governed by the existing owner-approval controls.

Key owner endpoints include `/jarvis/runtime/status`, `/jarvis/runtime/tick`, `/jarvis/work-queue`, `/jarvis/scheduler`, `/jarvis/capabilities`, `/jarvis/events`, and `/jarvis/digest/latest`.


## Jarvis v40: mission control and supervised learning

Jarvis v40 adds business objectives/KPI tracking, a decision journal for owner accept/reject/edit feedback, integration circuit breakers, SLA breach monitoring, and a consolidated mission-control health score. A safe KPI snapshot job measures approval backlog and verifies that undocumented-lot releases and unauthorized high-risk auto-actions remain at zero. These additions do not increase authority for consequential actions: publishing, supplier approval, purchasing, refunds, inventory release, marketing, and postage purchases remain owner-gated.

Jarvis can now use Mission Control, business objectives, and the decision journal in direct agent conversations. Integration failures are tracked by circuit state so repeated failures can pause attempts instead of hammering an unhealthy external service.

## Jarvis v45: production intelligence and financial controls

Jarvis v45 adds side-effect-free anomaly detection, deterministic daily financial snapshots, a research-only storefront compliance audit, and a strategic planning layer that turns anomalies, unmet objectives, SLAs, and integration health into a prioritized owner/agent plan. These systems are available to the internal durable queue and scheduler but do not expand Jarvis authority: publishing, purchases, refunds, supplier approval, inventory release, marketing, and shipping-label purchases remain owner-gated.

## v50 production-governance layer

- Tamper-evident execution receipts with hash-chain verification.
- Protected owner-policy limits that cannot disable high-risk approval or research-only safeguards.
- Runtime pause control for maintenance/change windows without shutting Jarvis down.
- Change-control records with mandatory owner approval for high-impact configuration/deployment changes.
- Consistent SQLite recovery checkpoints before risky maintenance.
- Runtime safety attestations that verify lot-release, autonomy, receipt-chain, and research-only controls.
- Jarvis version 65.0.0.


## Jarvis v65 production control plane

Checkpoint 60 adds five supervised operations layers:

- **Action preflight**: deterministic, side-effect-free checks before proposed actions. High-risk actions remain owner approval gated.
- **Chain of custody**: lot-level custody events and provenance visibility. Recording custody never substitutes for COA, identity, purity, or supplier verification.
- **Reconciliation**: compares order totals, ledger income, inventory bounds, and order relationships without changing financial records.
- **Exception triage**: converts failed integrity checks, stale approvals, and degraded configured integrations into prioritized internal exceptions.
- **Control plane**: runs safety attestation and reconciliation before allowing Jarvis's internal-only orchestrator to process work. It never performs external side effects itself.

Panther Peptides remains **FOR RESEARCH USE ONLY — NOT FOR HUMAN OR VETERINARY USE**. Undocumented inventory must remain quarantined until release controls are satisfied and owner approval is recorded.


## v65 production-resilience additions
- Worker lease watchdog recovers only expired internal work, never external actions.
- Inventory cycle counts record physical-count variances without silently changing inventory.
- Evidence links track provenance/identity/purity support for lots.
- Owner escalations deduplicate high-severity exceptions and stale approvals.
- Production Sentinel consolidates these checks into a side-effect-free resilience score.

## Jarvis v70 checkpoint

Jarvis v70 adds five production-control layers on top of v65:

- **Supplier assurance reviews** score supplier verification, lot evidence, and completed testing history without auto-approving suppliers.
- **Evidence manifests** create SHA-256 manifests for lot evidence and flag incomplete released lots or duplicate COA hashes across lots.
- **Exception policies** provide configurable observe/task/escalate behavior without granting new external authority.
- **Job safety quarantine** moves internal jobs that exhaust their retry budget to a dead-letter quarantine instead of retrying forever. Requeueing requires an exact owner confirmation and is limited to allow-listed internal work.
- **Operational freezes + Production Guardian** let the owner pause outbound, procurement, publishing, fulfillment, or integration scopes and run a side-effect-free consolidated safety check.

All consequential business actions remain subject to the existing approval and research-only controls.


## Jarvis v150 — Final Production Release

Checkpoint 150 consolidates the operating agent into a release-oriented build. It adds startup validation, immutable safety-boundary auditing, prompt-injection screening for uploaded documents, model-usage budget tracking, webhook replay protection, connector degradation plans, a unified owner action center, secret-free owner data export, release manifests, and a final certification/supervisor cycle.

Jarvis remains supervised for consequential actions. Product publishing, procurement, lot release, consequential refunds, marketing sends, supplier approval, and paid shipping-label purchases remain owner-gated. The required customer-facing statement is: **FOR RESEARCH USE ONLY — NOT FOR HUMAN OR VETERINARY USE**.

A software release can be production-ready while the business itself remains blocked from live sales. Jarvis v150 intentionally reports a go-live blocker when there is no released, documented inventory.
