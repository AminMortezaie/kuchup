import type { Metadata } from "next";
import type { ComponentType } from "react";
import { notFound } from "next/navigation";
import { CantStartNewThreadPost } from "@/components/engineering/CantStartNewThreadPost";
import { OneLoopNotFasterPost } from "@/components/engineering/OneLoopNotFasterPost";
import {
  ENGINEERING_AUTHOR,
  ENGINEERING_POSTS,
  LOGO,
  OG_IMAGE,
  SITE,
  engineeringPostPath,
  formatPostDate,
  getEngineeringPost,
} from "@/lib/engineering-posts";

const POST_BODIES: Record<string, ComponentType> = {
  "cant-start-new-thread": CantStartNewThreadPost,
  "one-loop-not-faster": OneLoopNotFasterPost,
};

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return ENGINEERING_POSTS.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getEngineeringPost(slug);
  if (!post) {
    return { title: "Not found" };
  }
  const path = engineeringPostPath(post.slug);
  const url = `${SITE}${path}`;
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: path },
    openGraph: {
      title: `${post.title} | Relocation Jobs`,
      description: post.description,
      url,
      siteName: "Relocation Jobs",
      type: "article",
      publishedTime: post.datePublished,
      modifiedTime: post.dateModified,
      authors: [ENGINEERING_AUTHOR.name],
      images: [
        {
          url: OG_IMAGE,
          width: 1200,
          height: 630,
          alt: post.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${post.title} | Relocation Jobs`,
      description: post.description,
      images: [OG_IMAGE],
    },
  };
}

export default async function EngineeringPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getEngineeringPost(slug);
  const Body = POST_BODIES[slug];
  if (!post || !Body) {
    notFound();
  }
  const path = engineeringPostPath(post.slug);
  const url = `${SITE}${path}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BlogPosting",
        headline: post.title,
        description: post.description,
        datePublished: post.datePublished,
        dateModified: post.dateModified,
        url,
        mainEntityOfPage: url,
        image: OG_IMAGE,
        author: {
          "@type": "Person",
          name: ENGINEERING_AUTHOR.name,
          url: ENGINEERING_AUTHOR.url,
        },
        publisher: {
          "@type": "Organization",
          name: "Relocation Jobs",
          alternateName: "KUCHUP",
          url: `${SITE}/`,
          logo: {
            "@type": "ImageObject",
            url: LOGO,
          },
        },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: "Home",
            item: `${SITE}/`,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: "Engineering",
            item: `${SITE}/engineering`,
          },
          {
            "@type": "ListItem",
            position: 3,
            name: post.title,
            item: url,
          },
        ],
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="landing-shell pb-16">
        <main className="mx-auto mt-12 max-w-2xl">
        <p className="engineering-back">
          <a href="/engineering">Engineering</a>
        </p>
        <header className="mt-6">
          <p className="text-sm font-medium uppercase tracking-[0.08em] text-text-muted">
            {post.kicker}
          </p>
          <h1 className="engineering-title mt-2 text-fluid-hero text-text-primary">
            {post.title}
          </h1>
          <p className="engineering-byline mt-4">
            <time dateTime={post.datePublished}>
              {formatPostDate(post.datePublished)}
            </time>
            <span aria-hidden="true"> · </span>
            <a href={ENGINEERING_AUTHOR.url}>{ENGINEERING_AUTHOR.name}</a>
          </p>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            {post.metric}
          </p>
        </header>
        <article className="mt-10">
          <Body />
        </article>
        <p className="engineering-close mt-12">
          This worker is why the catalog of visa-sponsored software jobs
          refreshes about every six hours.{" "}
          <a href="/how-it-works">How Kuchup finds roles</a>
          {" · "}
          <a href="/engineering">More engineering notes</a>
        </p>
        </main>
      </div>
    </>
  );
}
