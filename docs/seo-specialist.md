# Panther SEO specialist

The review candidate integrates the SEO specialist and quote-intake implementation. It includes the quote-intake branch's commit a55a837; both tool registries, endpoint groups and the quote startup/shutdown worker are preserved. Neither original draft PR needs to be merged separately if this combined candidate is selected.

Ask Jarvis: “Run the Panther SEO specialist, verify its saved report, and recommend the highest-priority improvements.” For the connected Shopify host specify `shopify`. The tools audit and recommend; they never publish source, activate services, send inquiries, spend money or change inventory.

## Audit and report contract

- `POST /seo/audit`: owner authentication and same-origin protection; body `{"site":"panther","max_pages":5}`. Valid sites are `panther` and `shopify`, page limit 1–8. One crawl at a time.
- `GET /seo/report?site=panther`: latest persisted report.
- `GET /seo/report?site=panther&report_id=1`: a particular historical report. The ID is scoped to this database and storefront. Missing reports return `ok:false` and `report:null`.
- Tools `seo_audit` and `seo_report` expose the same operations, including optional `report_id` readback.
- Reports are appended to `seo_reports` in the existing SQLite database; no new hosted database or vendor subscription is needed. A new blocked report does not delete an older successful report.

`state=completed` means the bounded queue was exhausted with at least one analyzed page and no unresolved fetch/discovery errors. It is not a whole-site certification or an absence of SEO findings. `partial` means pages were analyzed but errors, page/time limits or pending discovery prevent completion. `blocked` means no public HTML page could be analyzed. Always inspect `crawl_complete`, `stop_reason`, `remaining_pages`, `errors` and `skipped`. Top-level `ok` means some usable analysis exists; it does not mean the crawl is complete. A GET's `ok` only means a saved record was found.

Every actual request records URL, attempt, status/error class and elapsed time. Discovery records preserve HTTP statuses separately from network failures. A timeout never becomes a missing-sitemap claim. Explicit sitemap 404/410 is reported only if no valid alternate sitemap was discovered. XML namespaces, sitemap indexes and robots-declared sitemap locations are supported with bounds. The current catalog uses homepage fragments, so its one public HTML page is legitimate audit scope.

## Crawl controls

Only the two fixed HTTPS storefront origins are accepted by the agent and API. Each redirect is validated; private paths, encoded private paths, checkout/account/order routes and query strings are excluded. Redirect targets also obey the selected robots policy. Robots matching supports specific agent groups, wildcards, end anchors, unreserved URI escape equivalence, longest match and Allow tie precedence. Unknown robots policy (timeouts, server errors, HTML masquerading as robots) stops page crawling. An explicit robots 404 permits public crawling; robots.txt is optional.

Requests use finite connect/read timeouts, one bounded retry for transient transport failures or selected gateway statuses, a 1 MB decoded response cap and four redirect responses at most. Retry-After prevents immediate retries. Cooperative budgets are 20 seconds per fetch and 90 seconds per audit; a currently blocking socket operation can finish after the cooperative deadline, subject to its finite connect/read timeout. Discovery is capped at four sitemap requests and 64 locations per XML document; page queue and analyzed pages are bounded. No credentials are supplied by the crawler. A Shopify redirect to `/password` is an access blocker, not an audited product page.

Checks cover titles, descriptions, heading count, canonical presence, robots/noindex settings, absent image alt attributes, and presence of JSON-LD. Empty alt attributes can correctly describe decorative images and are not treated as missing. JSON-LD presence is not a schema validity test. No JavaScript rendering, performance measurement, Search Console, search-ranking, traffic or keyword-volume data is available. Fetched text is untrusted evidence, never executable instructions.

Maintain laboratory-research-only positioning. No dosing, human/veterinary use, therapeutic results, invented testing, certifications, reviews or guarantees. Follow the existing approval workflow for any proposed publication.

## Verification and deployment

See [SEO operational review](seo-operational-review.md) for actual live findings, test outcomes, saved website candidate and release requirements. Live JSON evidence is in [evidence](evidence/). `scripts/seo_smoke.py` uses an explicitly configured isolated database and verifies the saved report in a fresh Python process. Its optional fixed `public_control` run is a standalone diagnostic, not a production agent/API allowlist expansion.
