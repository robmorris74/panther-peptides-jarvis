# Panther Peptides · Jarvis v150 — Final Software Release

Jarvis v150 is the consolidated production-oriented software release for the Panther Peptides owner/operator agent.

## What is complete
- Direct Jarvis owner chat and voice-ready UI
- Persistent business memory, training feedback, goals and decision history
- Inventory, lot, quarantine, COA, chain-of-custody and evidence controls
- Storefront drafts, research-only compliance audits and owner-gated publishing
- Orders, fulfillment, shipping preparation and approval-gated paid labels
- Customer support triage, transactional email queue and medical/human-use refusal guardrails
- Shopify integration scaffolding, signed webhooks and replay protection
- Procurement, supplier assurance, purchasing budgets and owner approvals
- Finance/ledger, margin controls, reconciliation, forecasting and owner briefings
- Background scheduler/work queue, retries, watchdog, circuit breakers and Safe Mode
- Security, owner authentication, backups, recovery bundles, restore controls and audit trails
- Incident, anomaly, SLA, exception and escalation management
- Production readiness, self-tests, release manifests, maturity checks and final certification
- Uploaded-document prompt-injection screening
- Model usage budget controls
- Secret-free owner data export

## Hard safety boundaries
The following remain owner-gated and cannot be silently promoted to automatic external execution:
- releasing quarantined inventory
- publishing products
- approving suppliers or purchases
- consequential refunds
- marketing sends
- purchasing shipping labels

Customer-facing research-only statement:

**FOR RESEARCH USE ONLY — NOT FOR HUMAN OR VETERINARY USE**

## What still requires the owner
Software completion is not the same as business go-live. A live deployment still requires real account credentials/authorizations for the services the owner chooses to use. Physical inventory also remains blocked until the required provenance/testing/release conditions are met.

The current undocumented/unlabeled inventory should remain quarantined. Jarvis intentionally reports `no released inventory` as a go-live blocker until documented inventory is released through the controlled workflow.
