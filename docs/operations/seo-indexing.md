# SEO indexing

How to get kuchup.com found on Google and how LinkedIn discovers public job pages.

Architecture, JSON-LD shape, conversion funnel, and code map: [job-syndication.md](../reference/job-syndication.md).

## Prerequisites

- Domain `kuchup.com` is live and serving the public homepage
- Preferred host is **apex** `https://kuchup.com` (`www` must 301 to apex)
- `robots.txt` at `https://kuchup.com/robots.txt` allows indexing
- `sitemap.xml` at `https://kuchup.com/sitemap.xml` is up to date (includes `<lastmod>`)
- `sitemap-jobs.xml` at `https://kuchup.com/sitemap-jobs.xml` lists active visa-sponsored `/jobs/<slug>` URLs
- Engineering notes at `https://kuchup.com/engineering` (posts are in `sitemap.xml`, never `sitemap-jobs.xml`)
- Marketing pages deployed (see [ec2-panel.md](ec2-panel.md))

## After an SEO / marketing deploy

1. Confirm host consolidation:
   - `curl -sI https://www.kuchup.com/` → `301` with `Location: https://kuchup.com/...`
2. Spot-check head tags on `/` and one country page:
   - `rel="canonical"` points at apex
   - `og:image` absolute URL returns 200
   - `/favicon.ico` returns 200
3. Confirm marketing HTML is cacheable (`Cache-Control` is not `no-store` on `/`)
4. Re-submit `https://kuchup.com/sitemap.xml` and `https://kuchup.com/sitemap-jobs.xml` in Google Search Console
5. Request indexing for key URLs (URL inspection)
6. Spot-check a live job URL: `curl -s https://kuchup.com/jobs/<slug> | grep JobPosting` — JSON-LD must be in the first HTML response (no login wall)

## Google Search Console setup

1. Go to <https://search.google.com/search-console>
2. Add property: **URL prefix** `https://kuchup.com` (apex only after www redirects)
3. Verify ownership — choose any method:
   - **DNS TXT record** (recommended): add the TXT record in your DNS provider (Cloudflare).
   - **HTML file**: Google provides a file; drop it into `relocation_jobs/static/` and re-deploy.
   - **Google Analytics / Google Tag Manager**: if already installed.
4. Once verified, submit the sitemaps:
   - Navigate to **Sitemaps** section
   - Enter `https://kuchup.com/sitemap.xml` and submit
   - Enter `https://kuchup.com/sitemap-jobs.xml` and submit
5. Request manual indexing for key pages:
   - **URL inspection** → paste root URL → **Request indexing**
   - Repeat for: `/how-it-works`, `/pricing`, `/mcp`, `/engineering`, `/engineering/cant-start-new-thread`, `/relocation-jobs-germany`, `/relocation-jobs-netherlands`, `/relocation-jobs-uk`, `/relocation-jobs-portugal`, `/relocation-jobs-ireland`

## Public job pages

Visa-positive catalog jobs are public at `/jobs/<slug>`. Each page is server-rendered HTML with `schema.org/JobPosting` JSON-LD so LinkedInBot and Googlebot can read the posting without JavaScript.

- Open roles: HTTP 200, listed in `/sitemap-jobs.xml`
- Closed roles (dropped from the employer ATS on a successful refresh): HTTP **410**, omitted from the jobs sitemap, with a link to the country marketing page
- Unknown slugs: HTTP 404

`hiringOrganization` is Kuchup so LinkedIn can attach the posting to the company page. The job title and description name the real employer.

## What to expect

| Timeline | Event |
|----------|-------|
| Hours–days | Homepage indexed |
| Days–weeks | Marketing pages indexed |
| Days–weeks | Individual `/jobs/<slug>` URLs crawled from `/sitemap-jobs.xml` |
| Weeks–months | Category queries start returning results |

> Google may treat `hiringOrganization` that is not the employer as low-quality for Google Jobs. LinkedIn company-page wrapping is the intended distribution channel.

## Monitoring

- Check Search Console **Performance** tab weekly for clicks and impressions
- Watch **Coverage** for indexing errors or sitemap issues
- Fix any `noindex` flags, unexpected 404s, or crawl errors promptly
- Closed roles should be **410**, not lingering 200s in the jobs sitemap
