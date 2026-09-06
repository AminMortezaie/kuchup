import type { Metadata } from "next";
import { EngineeringShell } from "@/components/engineering/EngineeringShell";
import {
  ENGINEERING_POSTS,
  OG_IMAGE,
  SITE,
  engineeringPostPath,
  formatPostDate,
} from "@/lib/engineering-posts";

const TITLE = "Engineering notes from production";
const DESCRIPTION =
  "Measured incidents from the Kuchup fetch worker and job board — real numbers, wrong hypotheses, and the fix.";
const CANONICAL = `${SITE}/engineering`;

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/engineering" },
  openGraph: {
    title: `${TITLE} | Relocation Jobs`,
    description: DESCRIPTION,
    url: CANONICAL,
    siteName: "Relocation Jobs",
    type: "website",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: TITLE,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${TITLE} | Relocation Jobs`,
    description: DESCRIPTION,
    images: [OG_IMAGE],
  },
};

export default function EngineeringIndexPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: "Kuchup Engineering",
    url: CANONICAL,
    description: DESCRIPTION,
    blogPost: ENGINEERING_POSTS.map((post) => ({
      "@type": "BlogPosting",
      headline: post.title,
      description: post.description,
      datePublished: post.datePublished,
      url: `${SITE}${engineeringPostPath(post.slug)}`,
    })),
  };

  return (
    <EngineeringShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <main className="mx-auto mt-12 max-w-2xl">
        <p className="text-sm font-medium uppercase tracking-[0.08em] text-text-muted">
          Engineering
        </p>
        <h1 className="engineering-title mt-2 text-fluid-hero text-text-primary">
          Production notes
        </h1>
        <p className="mt-4 text-base leading-relaxed text-text-secondary">
          Incidents from the worker that refreshes visa-sponsored European
          software jobs every six hours. Numbers from production. No runbooks.
        </p>
        <ol className="engineering-index mt-10">
          {ENGINEERING_POSTS.map((post) => (
            <li key={post.slug}>
              <article>
                <time dateTime={post.datePublished} className="engineering-index-date">
                  {formatPostDate(post.datePublished)}
                </time>
                <h2 className="font-display text-xl font-semibold text-text-primary">
                  <a href={engineeringPostPath(post.slug)}>{post.title}</a>
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {post.metric}
                </p>
              </article>
            </li>
          ))}
        </ol>
      </main>
    </EngineeringShell>
  );
}
