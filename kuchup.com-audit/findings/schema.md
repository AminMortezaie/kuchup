# Schema / Structured Data — kuchup.com

**Score: 55 / 100**

## Detected JSON-LD

### Homepage
- `Organization` (name: Relocation Jobs, alternateName: KUCHUP, sameAs: GitHub)
- `WebSite` (no `potentialAction` / SearchAction)

### `/mcp` + country landers
- `FAQPage` with Question/Answer nodes

### App routes (`/apply`, `/panel`)
- No JSON-LD (fine; robots-disallowed)

## Validation notes

- Graph parses cleanly on home.  
- FAQPage is valid markup, but **Google retired FAQ rich results for all sites (May 7, 2026)**. Severity = **Info** — keep for UX/AI readability; do not expect FAQ SERP stars; do not recommend new FAQPage for Google SERP benefit.

## High

1. **Add `WebSite` SearchAction** pointing at the public board/search URL pattern so sitelinks search box eligibility is possible.  
2. **Add `SoftwareApplication` (or `WebApplication`)** for Kuchup product pages (`/`, `/pricing`, `/mcp`) with offers, feature list, and applicationCategory.

## Medium

3. **`JobPosting` (or ItemList of jobs)** on country pages / board when roles are public — strongest schema match for this business type. Only emit for currently open roles with accurate `datePosted` / `validThrough`.  
4. **`BreadcrumbList`** on country + secondary pages.  
5. **Organization completeness:** `logo`, `foundingDate`, contact, and more `sameAs` (LinkedIn/X once live).

## Info

6. Existing FAQPage — no Google rich-result benefit; optional keep for structure. Prefer `QAPage` only for genuine user-submitted Q&A threads.

## Do not recommend

- HowTo schema (deprecated).  
- New FAQPage solely for Google SERP.

## Falsifiability

- SearchAction failed if Rich Results Test still shows WebSite without `potentialAction`.  
- JobPosting failed if country pages still have zero JobPosting after board widgets ship.
