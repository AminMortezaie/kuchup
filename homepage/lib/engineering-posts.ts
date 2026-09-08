export const SITE = "https://kuchup.com";
export const OG_IMAGE = `${SITE}/og-default.png`;
export const LOGO = `${SITE}/static/icons/kuchup-bird.png`;

export const ENGINEERING_AUTHOR = {
  name: "Amin Mortezaie",
  url: "https://github.com/AminMortezaie",
} as const;

export type EngineeringPostMeta = {
  slug: string;
  title: string;
  description: string;
  metric: string;
  kicker: string;
  datePublished: string;
  dateModified: string;
};

export const ENGINEERING_POSTS: readonly EngineeringPostMeta[] = [
  {
    slug: "one-loop-not-faster",
    title: "One event loop: the thread error is gone",
    description:
      "We replaced thread-per-company with one event loop. The number that belongs to that change is the error string: 357 can't start new thread during the outage, zero since. Duration at concurrency 4 versus 2 is a different knob.",
    metric:
      "357 thread errors in the outage · 0 in 3,375 attempts after",
    kicker: "Production measurement",
    datePublished: "2026-09-06",
    dateModified: "2026-09-07",
  },
  {
    slug: "cant-start-new-thread",
    title: "can't start new thread: 186 companies looked dead",
    description:
      "On 1 September 2026 the production board showed fetch problems on most companies. 357 of 358 recent errors were RuntimeError: can't start new thread. The career sites were fine. The worker had run out of OS threads.",
    metric:
      "186 / 394 companies flagged · 357 / 358 errors were the same RuntimeError",
    kicker: "Production incident",
    datePublished: "2026-09-06",
    dateModified: "2026-09-06",
  },
  {
    slug: "678-postgres-round-trips",
    title: "678 Postgres round-trips: the board was not hung",
    description:
      "In July 2026 the Germany board took about 90 seconds to load. Job SQL was 0.67s. A location-label helper hit Postgres 678 times for 98 companies. After an in-memory cache, Germany was 1.7s.",
    metric: "678 DB round-trips for 98 companies · Germany ~89s → ~1.7s",
    kicker: "Production incident",
    datePublished: "2026-09-07",
    dateModified: "2026-09-07",
  },
  {
    slug: "cache-check-in-the-hot-path",
    title: "Cache check in the hot path: Redis did what Postgres did",
    description:
      "A generation-aware cache asked Redis on every country_label() call so MCP-added countries would appear without a restart. The board collapsed again. Throttle the check to once every 5s; the hot path stays in memory.",
    metric: "2 Redis round-trips × N companies · board back to ~1.3–1.7s",
    kicker: "Production incident",
    datePublished: "2026-09-07",
    dateModified: "2026-09-07",
  },
  {
    slug: "playwright-hung-for-15-hours",
    title: "Playwright hung for 15 hours and the worker still looked Up",
    description:
      "On 10 July 2026 one generic career page never returned from Playwright. wait_for_fetch_thread had no timeout. The container stayed Up. Scheduled fetches did not resume until a manual restart 15 hours later.",
    metric: "97/98 companies done · scheduler blocked 15+ hours · no join timeout",
    kicker: "Production incident",
    datePublished: "2026-09-07",
    dateModified: "2026-09-07",
  },
];

export function engineeringPostPath(slug: string): string {
  return `/engineering/${slug}`;
}

export function getEngineeringPost(
  slug: string,
): EngineeringPostMeta | undefined {
  return ENGINEERING_POSTS.find((post) => post.slug === slug);
}

export function formatPostDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
