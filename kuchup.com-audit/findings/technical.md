# Technical SEO — kuchup.com

**Score: 62 / 100**  
**Business type context:** SaaS / jobs marketplace (visa-sponsored software roles)

## Summary

Crawl fundamentals are solid (HTTPS, valid sitemap, sensible robots.txt, SSR). The highest-severity issue is **host duplication**: `www.kuchup.com` and `kuchup.com` both return 200 without consolidation. Canonical tags are absent sitewide.

## Category results

| Category | Status | Notes |
|----------|--------|-------|
| Crawlability | Pass | `Allow: /`; app surfaces disallowed |
| Indexability | Fail | No canonicals; www/apex split |
| Security | Partial | HTTPS OK; security headers missing |
| URL structure | Pass | Clean paths, no query spam |
| Mobile | Pass | Viewport present; no horizontal scroll |
| Core Web Vitals | Unknown | PSI rate-limited; no CrUX credentials |
| Structured data | Partial | Org/WebSite present; gaps elsewhere |
| JS rendering | Pass | Not an SPA (`is_spa: false`) |
| IndexNow | Fail | Not detected |

## Critical

1. **www and apex both live (no preferred host)**  
   - `https://kuchup.com/` → 200  
   - `https://www.kuchup.com/` → 200 (does **not** redirect to apex)  
   - `http://` correctly upgrades to HTTPS, but www/http stays on www.  
   - **Fix:** Pick one host (prefer apex), 301 the other, and set matching canonicals + Search Console property.

## High

2. **No `<link rel="canonical">` on any crawled public page**  
   - Leaves Google to guess preferred URL; amplifies www/apex risk.  
   - **Fix:** Self-referencing canonicals on all indexable pages pointing at the chosen host.

3. **HTML served with `Cache-Control: no-store`**  
   - Prevents CDN/browser caching of the marketing shell; hurts TTFB repeat views and CWV headroom.  
   - **Fix:** Cache public HTML briefly (or stale-while-revalidate); keep `no-store` only on authenticated `/panel` and `/api/`.

## Medium

4. **Missing security headers** on homepage responses:  
   `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` all absent.  
   - Indirect SEO/trust signal; add via Caddy/Cloudflare.

5. **Meta descriptions exceed typical SERP truncation** (165–215 chars). Titles are mostly fine (25–70).

6. **Favicon / apple-touch-icon 404** (`/favicon.ico`, `/favicon.svg`, `/apple-touch-icon.png`).

## Low / Info

7. **robots.txt correctly blocks** `/panel`, `/remote`, `/admin`, `/apply`, `/company`, `/api/` — good. Those URLs still return 200 if hit directly; consider `noindex` meta as defense in depth.  
8. **IndexNow** not implemented (Bing/Yandex discovery speed).  
9. **PSI lab data unavailable** during audit (anonymous quota rate limit). Re-run `/seo google` after adding `GOOGLE_API_KEY`.

## What works

- Valid `sitemap.xml` declared in robots and fetchable (9 URLs).  
- `meta robots: index, follow` on marketing pages.  
- Clean SSR HTML (Cloudflare + Caddy).  
- HTTP → HTTPS redirect on apex.  
- Mobile viewport + touch targets OK (visual analysis).

## Falsifiability

- Host fix failed if both www and apex still 200 after deploy.  
- Canonical fix failed if View Source still lacks `rel=canonical` on `/` and country pages.
