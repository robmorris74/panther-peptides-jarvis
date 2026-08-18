# Panther Peptides · Jarvis setup

1. Install Python 3.11+ and run `./run_local.sh`.
2. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable Jarvis chat.
3. Open `http://127.0.0.1:8000/jarvis`.
4. Add owner training examples in the Training tab.
5. Review the 90-unit starting inventory. It is intentionally quarantined because the physical vials arrived unlabeled and without lot/batch documentation or COAs.
6. Add real supplier, lot, identity/purity/COA, pricing, and storage records only when evidence exists.
7. Connect Shopify only after the product/quality records and customer-facing policies are ready.

Jarvis can automatically perform low-risk internal work such as reading operating data, creating tasks, and drafting material. Consequential actions remain approval-gated by default.

## Jarvis v5 permission ladder
Jarvis separates reasoning from authority. Every business workflow is assigned one of five modes: Observe, Recommend, Draft, Approval, or Auto. High-risk workflows such as publishing, purchasing, supplier approval, inventory release, refunds, marketing sends, payment-setting changes, and destructive data operations cannot be placed into silent Auto mode in this build.

## Durable owner memory
Use the Memory screen to save stable operating preferences, policies, and business rules. Do not store passwords, API keys, payment credentials, or other secrets in Jarvis memory. Account secrets belong in the connection configuration only.

## Running continuously
Docker Compose is the easiest persistent local/server mode and is configured with `restart: unless-stopped` plus a health check. `render.yaml` and `Procfile` are included as deployment scaffolding for a hosted service. Do not expose Jarvis directly to the public internet until owner authentication and production secret management are configured.

## Jarvis v13 hosted owner claim
When `JARVIS_ENV=production` and no owner password exists yet, Jarvis requires a one-time `JARVIS_BOOTSTRAP_TOKEN` before setup can be completed. The Render blueprint generates this value automatically. Other hosts should create it as a secret before first launch.

This prevents an unclaimed public Jarvis URL from being taken over by the first visitor. After the owner password is configured, normal signed owner sessions protect the console.

## Portable encrypted recovery
The owner console now includes **Recovery**. Create a recovery bundle with a passphrase of at least 12 characters. The bundle packages the database and persistent connection configuration inside an encrypted `.jarvis-recovery` file. Jarvis can verify a recovery bundle without changing live data.

Keep the recovery passphrase outside Jarvis. A recovery bundle plus its passphrase should be treated as sensitive business data.
