# SEO indexing

How to get kuchup.com found on Google and how LinkedIn discovers public job pages.

Architecture, JSON-LD shape, conversion funnel, and code map: [job-syndication.md](../reference/job-syndication.md).

## Prerequisites

- Domain `kuchup.com` is live and serving the public homepage
- Preferred host is **apex** `https://kuchup.com` (`www` must 301 to apex)
- `robots.txt` at `https://kuchup.com/robots.txt` allows indexing
- `sitemap.xml` at `https://kuchup.com/sitemap.xml` is up to date (includes `<lastmod>` and `https://kuchup.com/jobs`)
- `sitemap-jobs.xml` at `https://kuchup.com/sitemap-jobs.xml` lists active visa-sponsored `/jobs/<slug>` URLs
- LinkedIn feed at `https://kuchup.com/feeds/linkedin-jobs.xml` (not a Google sitemap; do not submit it in Search Console)
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
   - Repeat for: `/jobs`, `/how-it-works`, `/pricing`, `/mcp`, `/engineering`, `/engineering/cant-start-new-thread`, `/engineering/one-loop-not-faster`, `/engineering/678-postgres-round-trips`, `/engineering/cache-check-in-the-hot-path`, `/engineering/playwright-hung-for-15-hours`, `/relocation-jobs-germany`, `/relocation-jobs-netherlands`, `/relocation-jobs-uk`, `/relocation-jobs-portugal`, `/relocation-jobs-ireland`

## Public job pages

Visa-positive catalog jobs are public at `/jobs/<slug>`. `GET /jobs` is the HTML index (optional `?country=`). Each detail page is server-rendered HTML with `schema.org/JobPosting` JSON-LD so LinkedInBot and Googlebot can read the posting without JavaScript.

- Open roles: HTTP 200, listed in `/sitemap-jobs.xml` and on `/jobs`
- Closed roles (dropped from the employer ATS on a successful refresh): HTTP **410**, omitted from the jobs sitemap and hub, with a link to the country marketing page
- Unknown slugs: HTTP 404

`/sitemap-jobs.xml` is live from the catalog, not a checked-in file. New ATS fetches update it automatically; Search Console submit is for Google recrawl, not for adding URLs.

`hiringOrganization` is Kuchup so LinkedIn can attach the posting to the company page. The job title and description name the real employer. Visible location is city plus country/region.

After a homepage deploy, set the LinkedIn company Page website or custom button to `https://kuchup.com/jobs`.

### LinkedIn BD (XML feed)

Unpaid wrapping has no request-crawl. Fastest documented ingest is a partner XML feed (~24h scrape for job boards) after Talent BD accepts it.

1. Confirm `https://kuchup.com/feeds/linkedin-jobs.xml` returns `<source>` with open visa `applyUrl` values on apex `https://kuchup.com/jobs/<slug>`
2. Set `LINKEDIN_COMPANY_ID` and `LINKEDIN_JOB_POSTER_EMAIL` in gitignored `.env` (placeholders only in docs)
3. Email `LL-BD@linkedin.com`: daily listing count, markets (UK/DE/NL/PT/IE), search URL `https://kuchup.com/jobs`, sample job URLs, feed URL
4. Note the `https://www` applyUrl guideline vs Kuchup apex canonical — do not 301 Apply through www

LinkedIn may refuse aggregator feeds. Organic wrapping still depends on LinkedInBot following hub links; expect days–weeks and incomplete coverage. Do not submit the LinkedIn XML URL as a Google sitemap.

## What to expect

| Timeline | Event |
|----------|-------|
| Hours–days | Homepage indexed |
| Days–weeks | Marketing pages indexed |
| Days–weeks | Individual `/jobs/<slug>` URLs crawled from `/jobs` hub links and `/sitemap-jobs.xml` |
| After BD accepts XML | LinkedIn job-board feed scrape about every 24 hours |
| Weeks–months | Category queries start returning results |

> Google may treat `hiringOrganization` that is not the employer as low-quality for Google Jobs. LinkedIn company-page wrapping is the intended distribution channel.

## Monitoring

- Check Search Console **Performance** tab weekly for clicks and impressions
- Watch **Coverage** for indexing errors or sitemap issues
- Fix any `noindex` flags, unexpected 404s, or crawl errors promptly
- Closed roles should be **410**, not lingering 200s in the jobs sitemap

## Engineering notes

Canonical home: `https://kuchup.com/engineering`. Posts are static marketing HTML (Next export), listed in `/sitemap.xml` only.

After an engineering deploy:

1. Confirm `https://kuchup.com/engineering` and the post URL return 200
2. Confirm `/sitemap.xml` lists those URLs and `/sitemap-jobs.xml` does not
3. Request indexing in Search Console for `/engineering` and the new slug
4. Syndicate **after** the kuchup.com URL is live: Dev.to (or Hashnode) frontmatter `canonical_url: https://kuchup.com/engineering/<slug>`
5. One HN submission for the first post only — do not dump the series

Current posts:

- `https://kuchup.com/engineering/one-loop-not-faster`
- `https://kuchup.com/engineering/cant-start-new-thread`
- `https://kuchup.com/engineering/678-postgres-round-trips`
- `https://kuchup.com/engineering/cache-check-in-the-hot-path`
- `https://kuchup.com/engineering/playwright-hung-for-15-hours`
