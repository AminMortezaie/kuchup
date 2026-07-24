# FULL SEO AUDIT REPORT — kuchup.com

**Audited:** 2026-07-22  
**Tooling:** Claude SEO 2.2.4  
**URL:** https://kuchup.com/  
**Business type:** SaaS / jobs marketplace (visa-sponsored software engineering roles in Europe)  
**Pages crawled:** 9 sitemap URLs + `/apply`, `/panel` (robots-disallowed app surfaces)  
**Overall SEO Health Score: 60 / 100**

---

## Executive summary

Kuchup ships a clean SSR marketing site with a valid sitemap, sensible robots rules, and strong country-landing titles. It is early-stage on authority (absent from Common Crawl graph) and has a **critical host-duplication issue**: `www` and apex both return 200. Canonical tags are missing everywhere. SERP competition for sponsorship keywords favors guide+jobs hybrids; the homepage is a product landing with a search widget — better as a brand home, with country URLs carrying SEO weight once they show live inventory above the fold.

### Top critical / high issues

1. **Critical:** `www.kuchup.com` and `kuchup.com` both live — consolidate with 301 + canonicals.  
2. **High:** No `rel=canonical` on any public page.  
3. **High:** Homepage H1 undersells keywords already in the title.  
4. **High:** Missing `og:image` / social preview asset (and favicon 404).  
5. **High:** Schema gaps — no SearchAction, SoftwareApplication, or JobPosting.

### Top quick wins

1. 301 www → apex (or reverse) in Caddy/Cloudflare.  
2. Add self-referencing canonicals sitewide.  
3. Add `og:image` + favicon/apple-touch icons.  
4. Rewrite homepage H1 toward visa/relocation/software intent.  
5. Add `lastmod` to sitemap + visible “Updated …” on country pages.

---

## Score breakdown

| Category | Weight | Score | Weighted |
|----------|--------|-------|----------|
| Technical SEO | 22% | 62 | 13.6 |
| Content Quality | 23% | 68 | 15.6 |
| On-Page SEO | 20% | 65 | 13.0 |
| Schema / Structured Data | 10% | 55 | 5.5 |
| Performance (CWV) | 10% | 60* | 6.0 |
| AI Search Readiness | 10% | 48 | 4.8 |
| Images | 5% | 35 | 1.8 |
| **Total** | | | **≈ 60** |

\*Provisional — PSI anonymous quota rate-limited; no CrUX API key.

---

## Synthesis (PERCEIVE → ANALYZE → VALIDATE → ACT)

### PERCEIVE
- **External:** SERPs reward deep visa guides + sponsor lists + job indexes.  
- **Internal:** Small, well-structured site; product wedge is MCP + tracked applications.  
- **Listen:** FAQ copy already answers “does every role guarantee sponsorship?” honestly — good trust signal.

### ANALYZE
- **Think:** Indexation plumbing (host + canonical) must precede content scaling.  
- **Lateral:** Competitors win with thresholds/tables; Kuchup can differentiate with *live sponsorship-tagged roles* + agent workflow.  
- **System:** Country pages → board → MCP is the internal link spine; strengthen counts and JobPosting when public.

### VALIDATE
- Dual-host is independently verified via live fetches.  
- FAQPage kept at Info severity per 2026 Google FAQ retirement.  
- Performance score intentionally discounted without field data.

### ACT
See `ACTION-PLAN.md` — Phase 1 is host/canonical/OG; Phase 2 is country-page SERP fit; Phase 3 is authority.

---

## Technical SEO

See `findings/technical.md`.

**Works:** HTTPS, SSR, robots + sitemap, clean URLs, app paths disallowed.  
**Breaks:** www/apex split; no canonicals; missing security headers; `Cache-Control: no-store` on HTML.

## Content quality

See `findings/content.md`.

Country pages are the strongest assets (~740–880 words, QRG quality ~91). Pricing/How-it-works are thin. Automated quality scores are high with a “repetitive” flag from shared chrome/templates (Jaccard ~0.31–0.39 — not near-duplicate).

## On-page SEO

- Titles: generally strong and unique.  
- Meta descriptions: present but often >160 characters.  
- Headings: coherent H2/H3 tree on home.  
- Internal links: country hubs linked; hash nav used heavily on home.  
- Social: `og:title`/`og:description` present; **`og:image` missing**.

## Schema

See `findings/schema.md`. Organization + WebSite on home; FAQPage on MCP/countries (Info only for Google SERP).

## Performance

See `findings/performance.md`. Re-run with Google API key for LCP/INP/CLS.

## Images

Near-zero content images; decorative brand graphic only. Favicon 404. Priority is OG image + product screenshots, not alt-text cleanup.

## AI search readiness

See `findings/geo.md`. SSR helps; authority and multi-modal content lag. `llms.txt` 404.

## SXO

See `findings/sxo.md`. Homepage page-type mismatch vs sponsorship SERPs = High; country pages closer.

## Backlinks

See `findings/backlinks.md`. CC graph miss; configure Moz/Bing when ready.

## Conditional agents skipped

| Agent | Reason |
|-------|--------|
| seo-google | No credentials |
| seo-local / seo-maps | Not a local business |
| seo-ecommerce | Not ecommerce |
| seo-drift | No baseline |
| seo-cluster | No blog/pillar corpus yet |

---

## Artifacts

```
kuchup.com-audit/
  FULL-AUDIT-REPORT.md
  ACTION-PLAN.md
  audit-data.json
  findings/*.md
  screenshots/kuchup_com_{desktop,mobile}.png
  raw/…
```

## Offer

Generate a professional PDF report? Use `/seo google report full` (or ask to run `claude-seo run google_report.py --type full --data kuchup.com-audit/audit-data.json --domain kuchup.com --output-dir kuchup.com-audit/`).
