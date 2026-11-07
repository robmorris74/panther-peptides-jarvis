# Website quotes → Jarvis → owner alerts

The public website retains all quote requests. An authenticated integration feed returns at most 50 unacknowledged requests. Jarvis's background intake worker polls once per minute, stores each request in its persistent SQLite database, and atomically creates a `new_quote_request` dashboard activity alert. Only then does it acknowledge receipt to the website. Retries and restarts do not create duplicate inbox entries or dashboard alerts. Requests, including their text, are data; intake never queues them as agent instructions or orders.

The website owner inbox shows whether Jarvis has received each request. Receipt means durable intake, not that an email was delivered. Original quote records and their price snapshots are preserved.

## Configuration

Set the same random secret of at least 32 characters as `PANTHER_QUOTES_TOKEN` in both Sites and the existing Jarvis Render service. Keep it out of source and browser code. The Sites side has been configured separately; use a secure environment-variable update to transfer the matching value to Jarvis. Do not paste secrets into chat or PRs. Jarvis defaults to the existing Panther storefront URL; redirects are disabled when sending the secret.

For owner email alerts configure `SMTP_HOST`, `SMTP_FROM`, `SMTP_PORT` (587 for STARTTLS or 465 for TLS), and `SMTP_USER`/`SMTP_PASSWORD` if required. Alerts use `PANTHER_QUOTES_ALERT_EMAIL`, then `OWNER_NOTIFICATION_EMAIL`, then the confirmed owner address rob.morris@egc-inc.com. No buyer email is sent. The email contains the reference, institution and private owner-inbox link, not the full inquiry.

Without SMTP, dashboard alerts still work and email delivery stays pending. SMTP failures retain an error and are retried. A process crash after SMTP accepts a message but before the database records delivery can produce a duplicate email; SMTP is not an exactly-once delivery service. A stable Message-ID is used.

## Owner access and verification

`GET /business/quotes` returns saved requests and delivery status after owner authentication. `POST /business/quotes/sync` provides an authenticated, same-origin manual retry. Jarvis tools `quote_requests` and `quote_sync_status` provide the same inspection through its agent. The existing dashboard activity feed shows new-quote alerts.

Deploy the Jarvis branch through its existing CI/staging process. Configure the matching secret and SMTP in Render, then submit a synthetic website request and verify: saved website reference → Jarvis inbox → website received timestamp → dashboard alert → actual owner email delivery. This PR alone does not verify those live steps. No live notification is claimed until that end-to-end check passes.

Local checks: seven intake/auth/retry tests plus two existing document-receipt tests passed. Website checks cover auth, repeat reads, idempotent acknowledgements and retained records. The older full_operator/day2 suites currently import a missing legacy `app` package; they are not a passing release gate.
