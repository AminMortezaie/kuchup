# GEO / AI Search Readiness — kuchup.com

**Score: 48 / 100**

## Dimension scores

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Citability | 25% | 55 | FAQ answers help; homepage H1/lead less extractable |
| Structural readability | 20% | 70 | Clear H2/H3; SSR |
| Multi-modal content | 15% | 25 | Almost no images/charts/video |
| Authority & brand | 20% | 35 | GitHub only; not in Common Crawl graph |
| Technical accessibility | 20% | 65 | SSR OK; no llms.txt; generic robots |

**Weighted ≈ 48**

## AI crawler access (robots.txt)

```
User-agent: *
Allow: /
Disallow: /panel /remote /admin /apply /company /api/
```

No explicit GPTBot / OAI-SearchBot / ClaudeBot / PerplexityBot rules — they inherit `*`. App surfaces correctly blocked.

## Gaps

1. **`/llms.txt` → 404** (optional for Google Search; useful for some LLM tools).  
2. **Common Crawl:** domain **not found** in cc-main-2026-jan-feb-mar rankings — weak discovery/authority prior.  
3. **Brand entity thin:** one `sameAs` (GitHub). No Wikipedia/YouTube/Reddit footprint detected in this pass.  
4. **Passage design:** country FAQs are stronger citation units than the homepage hero.

## High

1. Add self-contained answer blocks (40–60 word direct answers under question H2s) on country pages — many FAQs already close; tighten the first sentence.  
2. Publish methodology + last-updated dates (authority / freshness for AI and Google).

## Medium

3. Optional `llms.txt` summarizing product, countries, and canonical URLs.  
4. Expand `sameAs` and earn non-GitHub brand mentions (LinkedIn company, launch posts).  
5. Add one diagram/screenshot per country page (multi-modal).

## Info

- Do not block search bots that matter for AI answers unless there is a deliberate training-vs-search policy.  
- FAQ structure helps citability even without Google FAQ rich results.

## Falsifiability

- GEO improved if llms.txt 200 and country pages show visible “Updated …” dates.  
- Authority failed if `sameAs` still only GitHub after brand expansion.
