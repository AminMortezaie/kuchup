# Sitemap — kuchup.com

**Score: 78 / 100**

## Discovery

- robots.txt declares `Sitemap: https://kuchup.com/sitemap.xml`  
- sitemap responds **200**, kind **urlset**, valid  
- Common alternates (`sitemap_index.xml`, `wp-sitemap.xml`) correctly 404

## Contents (9 URLs)

1. `/`  
2. `/how-it-works`  
3. `/pricing`  
4. `/mcp`  
5. `/relocation-jobs-germany`  
6. `/relocation-jobs-ireland`  
7. `/relocation-jobs-netherlands`  
8. `/relocation-jobs-portugal`  
9. `/relocation-jobs-uk`

## What works

- Only indexable marketing URLs included.  
- App routes (`/panel`, `/apply`, `/api/…`) correctly **excluded** and robots-disallowed.  
- Stable, human-readable locs on the preferred content set.

## Medium

1. **No `<lastmod>`** (and no changefreq/priority — fine) — add accurate `lastmod` when country pages or catalog methodology updates.  
2. **Host consistency:** sitemap locs use apex; if www remains live without redirect, submit only after host consolidation.  
3. **Growth path:** when public board URLs become crawlable/indexable (if ever), either keep them noindex or add a dedicated sitemap — do not dump thousands of thin job URLs without unique content.

## Low

4. Single urlset is fine at this scale; split only after 100+ URLs.

## Falsifiability

- Sitemap regresses if robots stops declaring it or returns non-200.  
- Contamination if `/panel` or `/apply` appear in locs.
