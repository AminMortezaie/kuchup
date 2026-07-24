# ACTION PLAN — kuchup.com

Prioritized by impact × dependency. Each item includes THINK / CONNECT / ACCEPT / GROW.

---

## Phase 1 — Critical fixes (Week 1)

### 1. Consolidate host (www ↔ apex)
- **Priority:** Critical  
- **THINK:** Two live hosts split signals and create duplicate URLs.  
- **CONNECT:** Unblocks canonicals, sitemap trust, and backlink equity.  
- **Work:** 301 `www` → `https://kuchup.com` (or reverse) in Cloudflare/Caddy; update absolute URLs.  
- **ACCEPT:** Failed if `https://www.kuchup.com/` still returns 200 with distinct HTML URL.  
- **GROW:** GSC “Duplicate without user-selected canonical” count ↓.

### 2. Self-referencing canonicals on all indexable pages
- **Priority:** High  
- **CONNECT:** Depends on #1 preferred host.  
- **ACCEPT:** Failed if View Source on `/` and `/relocation-jobs-germany` lack matching canonical.  
- **GROW:** Coverage → Valid pages stable week-over-week.

### 3. Open Graph image + favicon set
- **Priority:** High  
- **Work:** 1200×630 `og:image`; `/favicon.ico` + SVG + apple-touch-icon.  
- **ACCEPT:** Failed if Facebook/LinkedIn debugger still shows no image; `/favicon.ico` still 404.  
- **GROW:** Social CTR on shared links.

### 4. Stop `Cache-Control: no-store` on public HTML
- **Priority:** High  
- **CONNECT:** Improves CWV headroom before PSI deep-dive.  
- **ACCEPT:** Failed if homepage response still `no-store`.  
- **GROW:** Repeat TTFB / LCP in PSI.

---

## Phase 2 — High-impact SEO (Weeks 2–3)

### 5. Rewrite homepage H1 (and optionally eyebrow) for intent
- **Example:** “Visa-sponsored software jobs in Europe — in one workspace.”  
- **ACCEPT:** Failed if H1 still omits visa/relocation/software.  
- **GROW:** Brand + generic impressions in GSC.

### 6. Country pages: live inventory above the fold
- Role count + 3–5 sample jobs + sponsorship signal before FAQ.  
- **CONNECT:** Aligns page type with SERP consensus (SXO).  
- **ACCEPT:** Failed if Germany page still FAQ-first with no live jobs.  
- **GROW:** Country URL CTR and engagement.

### 7. Schema upgrades
- `WebSite` SearchAction; `SoftwareApplication` on product pages; `BreadcrumbList`; `JobPosting`/`ItemList` when accurate.  
- Keep FAQPage if useful for UX; do **not** expect Google FAQ rich results.  
- **ACCEPT:** Rich Results Test shows new types without errors.

### 8. Expand thin pages
- `/pricing` and `/how-it-works` → ≥400–600 words of substantive, unique copy.  
- **ACCEPT:** Failed if word count still &lt;300 meaningful words.

### 9. Security headers via Cloudflare/Caddy
- HSTS, X-Content-Type-Options, Referrer-Policy, frame controls, CSP as feasible.

---

## Phase 3 — Content & authority (Month 2)

### 10. Entity / E-E-A-T pack
- About + methodology (“how sponsorship is detected”); more `sameAs`; visible last-updated dates.

### 11. Optional `llms.txt`
- Short machine-readable summary of product + canonical country URLs.

### 12. Digital PR / links
- Launch posts, engineering blogs, relocation newsletters.  
- Measure with Moz/Bing once keys added; CC graph presence later.

### 13. Capture drift baseline
- `/seo drift baseline https://kuchup.com` after Phase 1 ships.

---

## Phase 4 — Monitoring (ongoing)

### 14. Configure Google API key + GSC/GA4
- Unlock CrUX, PSI with quota, indexation, query data (`/seo google`).

### 15. IndexNow on publish
- Ping Bing when sitemap/country content changes.

### 16. Re-audit quarterly
- `/seo audit https://kuchup.com` + compare drift.

---

## Dependency graph (simplified)

```
Host 301 → Canonicals → Outreach/links
       ↘ Sitemap lastmod / GSC property
OG+favicon (parallel)
H1 + country inventory → Schema JobPosting
Thin page expand (parallel)
Google API → CWV truth → Performance tuning
```
