# Panther SEO operational review — November 7, 2026 (Central)

The candidate combines the SEO specialist and quote-intake functionality on `jarvis/seo-operational`. Production was not merged, deployed or activated. Website version 8 was saved without deployment. This is a review candidate, not a claim that the production Jarvis service is already updated.

## Observed live results

| Target | Actual result | Interpretation |
| --- | --- | --- |
| Panther homepage | HTTP 200, one analyzed public HTML page; completed bounded crawl | Meaningful live HTML audit succeeded. The catalog uses homepage anchors rather than separate product URLs. |
| Panther robots.txt | HTTP 404 | Source contains no route in published version 7. Optional file is missing; it is not a site-wide crawl prohibition. |
| Panther sitemap.xml | HTTP 404 | Source contains no sitemap route. This is a verified website configuration gap. |
| Panther canonical | Absent in fetched HTML and browser DOM | Add the homepage's stable canonical URL. |
| Panther title/description/headings/images | Title and research-only description present; one H1; no absent image alt attributes | No missing-title, missing-description, multiple-H1 or missing-alt fix is supported by this sample. |
| Panther JSON-LD | No JSON-LD detected | Lower-priority review of factual organization markup; no fabricated Product offers, reviews, tests or certifications. |
| Connected Shopify storefront | Robots 200; sitemap 404; root redirects 302 to `/password` | Report correctly blocked with zero product pages analyzed. Review launch/password settings separately; no password or access setting was changed. |
| Public technical-documentation control | Two accessible HTML pages analyzed; partial due discovery errors/limits | Exercises real network parsing and truthful partial-state reporting. These are not Panther SEO findings. |

The initial direct requests timed out for Panther's homepage, robots and sitemap. Later requests from the corrected crawler succeeded, and an independent browser loaded the live homepage and displayed Not Found on both discovery routes. This rules out a persistent robots-only outage and confirms the source gaps. The exact origin of the earlier transient network/host latency is not proven; there were no production Worker log events returned by the available log query. There is no evidence that the timeout itself was caused by a robots rule. The old crawler had no transport retry and short socket deadlines; the candidate adds retry/timing/error evidence without bypassing exclusions.

Actual machine-readable results: [Panther](evidence/panther-live.json), [Shopify](evidence/shopify-live.json), [separate public control](evidence/public-control-live.json), [report access verification](evidence/report-access-verification.json). Each live report was saved to an isolated SQLite database and read back by a fresh Python process. Panther and Shopify reports were additionally retrieved through owner-authenticated FastAPI test HTTP endpoints; anonymous requests returned 401. This verifies the persistence/access implementation, not production Render disk survival.

## Highest-priority supported improvements

1. Publish the prepared Panther sitemap and canonical URL. The sitemap contains only the actual public homepage, with no invented product routes, fragments, private routes or fabricated modification dates.
2. Publish explicit robots discovery rules excluding admin/API/auth routes and pointing to the sitemap. This aids discovery and policy clarity; robots rules do not replace authentication.
3. Determine whether Shopify should be public before attempting product SEO there. Its password gate is a launch configuration decision requiring separate owner authorization; the current release does not remove it.
4. Consider factual organization structured data later. The existing title, description, single H1 and informative image descriptions do not justify speculative rewrites from this audit.

No measured rankings, traffic, revenue gains, indexing guarantee, testing/certification claim or medical claim is asserted. A sitemap helps discovery but does not guarantee indexing. Reference: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview

## Website candidate

Saved Site version: **8**, project `appgprj_6a7d2d2f5ccc8191b94700f98739cdae`.

Saved version ID: `appgprj_6a7d2d2f5ccc8191b94700f98739cdae~appgver_01c26527cef881918ec52c0676acc52f`.

Source commit: `0bcb02c4cb1a867114ce09191f0452f17c5c28cf`. No deployment ID was returned because this was save-only. The current public website remains version 7.

Changed source: new `app/seo.ts`, `app/robots.txt/route.ts`, `app/sitemap.xml/route.ts`; the existing client storefront is moved intact to `app/storefront.tsx`, and the new server `app/page.tsx` wrapper provides homepage-only canonical metadata. Public positioning, prices and quote integration are preserved. No new COA, testing or certification claims were added.

## Test results

| Check | Result |
| --- | --- |
| Current-runtime Python SEO, quote intake, document receipt tests | 37 passed |
| Production runtime compilation and import (`app223`, `jarvis_boot.py`) | Passed, version 230.0.0 |
| Website quote/integration/discovery route tests | 9 passed |
| Website TypeScript check and production Worker build | Passed |
| Browser inspection of unpublished website candidate | Homepage renders, canonical correct, research-only positioning present, robots text served, valid XML sitemap displayed |
| Live report persistence and authenticated retrieval | Passed; fresh-process readback verified, anonymous access 401 |
| Existing `test_full_operator.py` and `test_day2.py` | 2 collection errors: missing legacy `app` package, before tests execute |
| Existing required release CI as a whole | Not a passing release gate; legacy suite collection must be resolved before production promotion |

The new `SEO and quote integration review` workflow tests the current production package. It supplements the existing release workflow and does not remove, skip or override the legacy failing gate. Existing FastAPI lifecycle deprecation warnings remain. No production data was used or modified in tests.

## Hosting requirements and proposed rollout

1. **Release gate:** resolve the stale legacy CI suite contract through a reviewed change that preserves meaningful current-runtime regression coverage. Do not bypass the failing gate or treat focused tests as proof every old suite passes.
2. **Staging:** configure/verify a separate Render staging service using `Dockerfile.render.agent`, with `RENDER_STAGING_SERVICE_ID` and `JARVIS_STAGING_URL`, and the integration's Render credentials. These credentials/configurations are not available in this review environment, so no staging service or deployment is claimed. No staging-to-production substitution is permitted.
3. **Persistence/auth:** retain the existing single-process SQLite design and persistent `/app/data` volume, `DATABASE_PATH=/app/data/operator.db`, durable session/config files and owner authentication. Verify actual disk mounts, back up production SQLite before release, and isolate staging storage from production. The SEO report table is created additively and does not remove existing data.
4. **Egress/runtime:** staging needs outbound public HTTPS to the two fixed storefront hosts, working DNS/TLS and sufficient request duration for the bounded crawl. The SEO scanner needs no Search Console credential, paid SEO subscription, Shopify Admin token or new database. Existing Jarvis model configuration is needed for conversational recommendations; the deterministic audit endpoint itself does not call a model.
5. **Preserved quote service:** before activating the integrated service, supply the existing matching `PANTHER_QUOTES_TOKEN` through secure environment configuration; retain SMTP settings for owner email delivery. Verify synthetic quote → durable inbox → website acknowledgement → dashboard alert → actual owner email. Staging must use isolated test integration/SMTP configuration so it cannot acknowledge real quotes or email real recipients. The matching production token transfer and live SMTP delivery are still unverified; no secrets belong in reports or PRs.
6. **After explicit owner approval:** publish only saved website version 8; verify live robots/sitemap 200 and canonical URL. Deploy the exact reviewed Jarvis candidate to isolated staging after CI is green. Exercise owner-authenticated audit → saved report → restart/readback, blocked/partial cases, quote regressions and `/health/ready`.
7. **Production approval:** obtain explicit owner approval for the reviewed production promotion. The Render blueprint has `autoDeploy:true`, so merging `main` may activate production. Merge/promote only after required CI and staging checks pass and approval is recorded. Do not merge the overlapping PRs #1/#2 independently after merging the combined candidate. Run production readiness/report persistence and synthetic quote/email verification before declaring operation complete.
8. **Rollback:** retain the previous service commit and website version 7. If readiness, report persistence, quote intake or delivery regresses, redeploy the previous service commit and restore website version 7 as appropriate; preserve additive tables/records and backups. Do not erase business data to roll back code.

No schedule is enabled by this candidate. Audits run on demand. Automatic recurring operation would require a separately authorized schedule.
