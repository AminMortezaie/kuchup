import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { CountryCatalogPanel } from "@/components/CountryCatalogPanel";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { MARKETING_COUNTRY_KEYS, countryLabel } from "@/lib/countries";
import { COUNTRY_PAGES } from "@/lib/country-pages";
import { countrySnapshot } from "@/lib/country-snapshots";

type PageProps = {
  params: Promise<{ slug: string }>;
};

function countryKeyFromSlug(slug: string): string | null {
  const prefix = "relocation-jobs-";
  if (!slug.startsWith(prefix)) {
    return null;
  }
  const key = slug.slice(prefix.length);
  return key && COUNTRY_PAGES[key] ? key : null;
}

export function generateStaticParams() {
  return MARKETING_COUNTRY_KEYS.map((country) => ({
    slug: `relocation-jobs-${country}`,
  }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const country = countryKeyFromSlug(slug);
  if (!country) {
    return { title: "Not found" };
  }
  const content = COUNTRY_PAGES[country];
  const title = content.title;
  const path = `/relocation-jobs-${country}`;
  const description =
    content.metaDescription.length > 158
      ? `${content.metaDescription.slice(0, 155).trim()}…`
      : content.metaDescription;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title: `${title} | Relocation Jobs`,
      description,
      url: `https://kuchup.com${path}`,
      siteName: "Relocation Jobs",
      type: "website",
      images: [
        {
          url: "https://kuchup.com/og-default.png",
          width: 1200,
          height: 630,
          alt: content.h1,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} | Relocation Jobs`,
      description,
      images: ["https://kuchup.com/og-default.png"],
    },
  };
}

export default async function CountryJobsPage({ params }: PageProps) {
  const { slug } = await params;
  const country = countryKeyFromSlug(slug);
  if (!country) {
    notFound();
  }
  const label = countryLabel(country)!;
  const content = COUNTRY_PAGES[country];
  const snap = countrySnapshot(country);
  const otherCountries = MARKETING_COUNTRY_KEYS.filter((key) => key !== country).map(
    (key) => ({
      href: `/relocation-jobs-${key}`,
      title: COUNTRY_PAGES[key].title,
    }),
  );

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: content.faq.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: "https://kuchup.com/",
      },
      {
        "@type": "ListItem",
        position: 2,
        name: content.h1,
        item: `https://kuchup.com/relocation-jobs-${country}`,
      },
    ],
  };

  return (
    <div className="min-h-screen">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <div className="mx-auto max-w-site px-4 pb-8 pt-5 sm:px-5">
        <Header />
        <main className="mx-auto mt-12 max-w-2xl">
          <p className="section-kicker">{content.kicker}</p>
          <h1 className="text-fluid-hero text-text-primary">{content.h1}</h1>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            {content.lede}
          </p>
          <ul className="country-chip-row mt-4" aria-label={`${label} hubs`}>
            {content.hubs.map((hub) => (
              <li key={hub}>{hub}</li>
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button as="a" href={`/panel?country=${country}`} variant="primary">
              Browse {label} roles
            </Button>
            <Button as="a" href={content.officialHref} variant="secondary">
              Official guidance
            </Button>
          </div>

          <CountryCatalogPanel
            country={country}
            label={label}
            initial={snap}
          />

          <section className="mt-12" aria-labelledby="market-heading">
            <h2
              id="market-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              {content.marketTitle}
            </h2>
            {content.marketBody.map((paragraph) => (
              <p
                key={paragraph.slice(0, 48)}
                className="mt-3 text-sm leading-relaxed text-text-secondary"
              >
                {paragraph}
              </p>
            ))}
          </section>

          <section className="mt-12" aria-labelledby="sponsor-heading">
            <h2
              id="sponsor-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              {content.sponsorTitle}
            </h2>
            {content.sponsorBody.map((paragraph) => (
              <p
                key={paragraph.slice(0, 48)}
                className="mt-3 text-sm leading-relaxed text-text-secondary"
              >
                {paragraph}
              </p>
            ))}
          </section>

          <section className="mt-12" aria-labelledby="visa-heading">
            <h2
              id="visa-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              {content.visaTitle}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              {content.visaIntro}
            </p>
            <div className="mt-5 grid gap-4">
              {content.visaRoutes.map((item) => (
                <Card key={item.title} className="px-5 py-5">
                  <h3 className="font-display text-lg font-semibold text-text-primary">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                    {item.body}
                  </p>
                </Card>
              ))}
            </div>
            <div className="country-stat-rail mt-6" aria-label="Key figures">
              {content.thresholds.map((item) => (
                <div key={item.label}>
                  <strong className="!text-base !leading-snug">{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-relaxed text-text-muted">
              {content.visaDisclaimer}{" "}
              <a
                href={content.officialHref}
                className="font-bold text-text-primary"
                target="_blank"
                rel="noopener noreferrer"
              >
                {content.officialLabel} ↗
              </a>
            </p>
          </section>

          <section className="mt-12" aria-labelledby="flow-heading">
            <h2
              id="flow-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              {content.flowTitle}
            </h2>
            <ol className="workflow mt-8">
              {content.flowSteps.map((step, index) => (
                <li key={step.title} className="workflow-step">
                  <span className="workflow-number" aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <Card className="workflow-card px-5 py-6">
                    <p className="workflow-label">Step {index + 1}</p>
                    <h3 className="font-display text-xl font-semibold text-text-primary">
                      {step.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      {step.body}
                    </p>
                  </Card>
                </li>
              ))}
            </ol>
          </section>

          <section className="mt-12" aria-labelledby="mcp-heading">
            <Card className="px-5 py-6" accentBar>
              <p className="section-kicker">After you pick a role</p>
              <h2
                id="mcp-heading"
                className="mt-2 font-display text-xl font-semibold text-text-primary"
              >
                Prepare the application — then the visa follows the employer’s process
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Use Kuchup to track {label} roles and connect Claude or Cursor via
                MCP for a gated CV reframe. Immigration filings stay between you,
                the employer, and the authorities.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button as="a" href={`/panel?country=${country}`} variant="primary">
                  Open {label} board
                </Button>
                <Button as="a" href="/mcp" variant="secondary">
                  Explore MCP
                </Button>
              </div>
            </Card>
          </section>

          <section className="mt-12" aria-labelledby="country-faq-heading">
            <h2
              id="country-faq-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              {label} sponsorship FAQ
            </h2>
            <div className="faq-list mt-5">
              {content.faq.map((item) => (
                <details key={item.question}>
                  <summary>
                    <span>{item.question}</span>
                    <span className="faq-marker" aria-hidden="true">
                      +
                    </span>
                  </summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </div>
          </section>

          <section className="mt-12" aria-labelledby="other-countries-heading">
            <h2
              id="other-countries-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              Compare other countries
            </h2>
            <ul className="mt-4 flex flex-col gap-2">
              {otherCountries.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    className="text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
                  >
                    {item.title}{" "}
                    <span aria-hidden="true">→</span>
                  </a>
                </li>
              ))}
            </ul>
          </section>

          <div className="mt-12 flex flex-wrap items-center justify-center gap-3 text-center">
            <Button as="a" href={`/panel?country=${country}`} variant="primary">
              Browse {label} companies
            </Button>
            <Button as="a" href="/how-it-works" variant="secondary">
              How Kuchup works
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    </div>
  );
}
