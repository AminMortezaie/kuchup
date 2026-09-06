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
    title: "One event loop: Germany got slower, the catalog moved",
    description:
      "Four days after we replaced thread-per-company with one event loop, 153 of 154 real catalog runs succeeded. Germany’s median scrape went from 103 seconds to 130. Performance here meant the six-hour cycle finishing, not finishing sooner.",
    metric:
      "153 / 154 real catalog runs · 0 thread errors in 3,375 attempts",
    kicker: "Production measurement",
    datePublished: "2026-09-06",
    dateModified: "2026-09-06",
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
