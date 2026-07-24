# Performance / Core Web Vitals — kuchup.com

**Score: 60 / 100** (provisional — lab/field APIs unavailable)

## Data availability

| Source | Status |
|--------|--------|
| PageSpeed Insights (anon) | Rate limited during audit |
| CrUX field data | No `GOOGLE_API_KEY` / google-api.json |
| Render diagnostics | SSR, non-SPA, ~fast TTFB on apex (~0.27s curl) |

## Observed performance-adjacent signals

- **Positive:** SSR HTML, no `<img>` weight on homepage, Cloudflare edge, clean console (no errors in render).  
- **Negative:** `Cache-Control: no-store` on HTML; no resource hints audited via PSI; hero is CSS/SVG-light (good for LCP candidates).

## Visual / UX proxies

- Desktop + mobile screenshots captured.  
- Viewport meta present; no horizontal scroll; fonts readable (16px base).  
- Primary CTA (“Find roles”) **is** above the fold on desktop and mobile (correcting the automated visual heuristic that flagged `cta_visible: false`).

## High (when measurable)

1. Re-run PSI/CrUX after API key setup — treat LCP/INP/CLS as authoritative.  
2. Stop `no-store` on public HTML to improve repeat-view LCP/TTFB.

## Medium

3. Ensure LCP element is the H1 or search widget text (not a late webfont). Preload critical font files if custom fonts block render.  
4. Keep third-party scripts minimal on marketing pages (currently light).

## Note on INP

INP is the sole interactivity CWV metric. Search dropdowns / “Find roles” interactions should stay ≤200ms; audit after key setup.

## Falsifiability

- Performance claim failed if mobile LCP >2.5s or INP >200ms in CrUX once data exists.  
- Caching fix failed if homepage still sends `Cache-Control: no-store`.
