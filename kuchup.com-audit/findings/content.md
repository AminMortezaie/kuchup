# Content Quality — kuchup.com

**Score: 68 / 100**

## Summary

Public marketing copy is clear and product-specific. Country landing pages carry real FAQ substance (~740–880 words). Thin spots: Pricing and How it Works. Homepage H1 under-uses the keyword promise already in the title.

## Page inventory (indexable)

| URL | Words | Title quality | Notes |
|-----|-------|---------------|-------|
| `/` | ~1233 | Strong keyword title | H1 generic |
| `/how-it-works` | ~249 | OK | Thin for intent |
| `/pricing` | ~153 | OK | Thin |
| `/mcp` | ~552 | Strong | FAQ schema |
| `/relocation-jobs-{country}` ×5 | ~739–877 | Strong | Templated but differentiated |
| `/apply`, `/panel` | — | App chrome | robots Disallow (correct) |

## Content quality script (QRG-aligned)

| Page | overall_quality | flags |
|------|-----------------|-------|
| Home | 92 | repetitive |
| Germany | 91 | repetitive |
| How it works | 92 | repetitive |
| Pricing | 93 | repetitive |

High scores reflect low filler/AI-pattern noise. “Repetitive” aligns with shared nav/chrome and country-page templates (Jaccard token overlap ~0.31–0.39 across country pairs — acceptable uniqueness, not near-duplicate).

## High

1. **Homepage H1/title mismatch**  
   - Title: “Relocation Jobs | Visa-Sponsored Software Roles in Europe”  
   - H1: “All your opportunities, in one place”  
   - SERP competitors for sponsorship keywords lead with visa/country/role language in H1.  
   - **Fix:** H1 that names the outcome, e.g. “Visa-sponsored software jobs in Europe — tracked in one place.”

2. **Thin commercial pages**  
   - `/pricing` (~153 words) and `/how-it-works` (~249) risk weak rankings and weak AI-citation passages.  
   - **Fix:** Expand with plan comparison detail, eligibility, limits, and a short “who it’s for / not for” section.

## Medium

3. **Brand naming split:** UI says **KUCHUP**; schema/`<title>` brand often **Relocation Jobs**. Pick a primary entity name and use the other as `alternateName` consistently in copy + schema (already partially done in JSON-LD).

4. **Country pages are guide-shaped** while SERP winners mix deep visa guides with live job inventory. Ensure each country URL surfaces **live role counts / sample jobs** above the fold, not only FAQ.

5. **E-E-A-T:** Author/org evidence is thin beyond GitHub `sameAs`. Add About, methodology (“how we detect sponsorship”), last-updated dates on country pages.

## Low

6. Homepage body leans product narrative; add 1–2 citable stats with sources (refresh cadence is already stated — pair with catalog size / countries covered).

## What works

- Distinct titles + meta descriptions on all sitemap pages.  
- Country FAQs answer real seeker questions (sponsorship certainty, sources).  
- Clear ICP: international software engineers + relocation.  
- Low AI-slop pattern score in automated checks.

## Falsifiability

- H1 fix failed if homepage H1 still omits visa/relocation/software after change.  
- Thin-page fix failed if `/pricing` remains under ~400 substantive words.
