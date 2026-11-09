# Panther SEO specialist

Jarvis can now use `seo_audit` and `seo_report` for evidence-backed SEO work. Ask Jarvis: “Run the Panther SEO specialist on our public website, verify the saved report, and draft the highest-priority improvements.” For the Shopify storefront, specify `shopify`.

The specialist fetches up to eight public HTML pages on the selected, allowlisted storefront, checks robots.txt and sitemap.xml, and records findings in the persistent Jarvis SQLite database. It checks titles, descriptions, headings, canonical links, noindex directives, missing image alt attributes and the presence of structured data. It respects robots exclusions and excludes admin, APIs, accounts, carts, checkout and query strings. Redirects cannot leave the selected storefront. Fetches have time, size and redirect limits. Only one audit runs at a time.

Jarvis interprets the saved report using its existing model and tools. The specialist does not publish, modify stock, submit external forms or buy services. Any proposed source changes follow Jarvis's existing release process. Research-only positioning remains in effect; no human-use claims, fabricated tests, reviews or certifications. Search rankings, traffic and keyword volume require separate measurement; HTML findings are not those metrics.

Owner-authenticated endpoints: `POST /seo/audit` with optional `site` (`panther` or `shopify`) and `max_pages` (1–8); `GET /seo/report?site=panther` reads the latest persisted report; `GET /seo/scheduler` returns the scheduler and its latest report.

Production starts a daily audit worker automatically (`JARVIS_ENV=production`). The first audit runs at startup, then no more than once every 24 hours, using persisted report timestamps across restarts. Audits visit at most eight public pages. Failures are recorded as blocked or partial, not clean audits. `JARVIS_SEO_ENABLED=0` pauses the worker. Nonproduction environments must explicitly opt in. `/health` exposes only the scheduler revision, enabled flag and liveness; findings stay owner-authenticated. This worker audits and recommends; website maintenance runs separately through the connected Sites workflow.

The release gate now tests the actual v230 `app223` runtime (SEO, scheduling and document receipts). Legacy `test_full_operator.py` and `test_day2.py` remain in the repository but cannot collect without the absent `app` package; they are not represented as passing. The existing v230 import, deployment-contract and safety-contract gates remain enforced.

References used for checks:

- https://developers.google.com/search/docs/essentials
- https://developers.google.com/search/docs/appearance/title-link
- https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites

Validation: seven focused tests cover durable reports, metadata findings, failed crawls, robots exclusions, URL/redirect restrictions, runtime tool registration and endpoint authentication. The existing `test_full_operator.py` and `test_day2.py` refer to the absent legacy `app` package; their collection fails before any test runs. This change does not reconstruct or alter that older application.
