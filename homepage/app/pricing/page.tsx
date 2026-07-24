import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Free public preview of visa-sponsored software roles in Europe. Full board, tracking, and MCP CV tools are in design — sign in for early access.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "Pricing | Relocation Jobs",
    description:
      "Free public preview today. Paid full-board access with workspaces and CV reframe tools is coming soon.",
    url: "https://kuchup.com/pricing",
    siteName: "Relocation Jobs",
    type: "website",
    images: [
      {
        url: "https://kuchup.com/og-default.png",
        width: 1200,
        height: 630,
        alt: "Kuchup pricing",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricing | Relocation Jobs",
    description:
      "Free public preview today. Paid full-board access with workspaces and CV reframe tools is coming soon.",
    images: ["https://kuchup.com/og-default.png"],
  },
};

export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-site px-4 pb-8 pt-5 sm:px-5">
        <Header />
        <main className="mx-auto mt-12 max-w-2xl">
          <h1 className="text-fluid-hero text-text-primary">Plans & Pricing</h1>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            Relocation Jobs (Kuchup) is a curation-first tracker for
            visa-sponsored software engineering roles across Europe. The public
            preview is free while we harden the full board, company workspaces,
            and Claude/Cursor MCP pipeline. This page explains what you get
            today, what is coming, and who the product is for.
          </p>

          <section className="mt-10" aria-labelledby="who-heading">
            <h2
              id="who-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              Who it is for
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              International software engineers who need employer sponsorship —
              or clear relocation signals — in Germany, the Netherlands, the
              UK, Portugal, or Ireland. You want career-page truth instead of
              syndicated noise, and a place to keep decisions when the search
              stretches across months.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              It is not a visa agency and it does not guarantee that every role
              will sponsor you. Eligibility depends on the employer, country
              rules, and your circumstances. Always confirm the live job
              description before you apply.
            </p>
          </section>

          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            <Card className="px-5 py-6">
              <h2 className="font-display text-xl font-bold text-text-primary">
                Free Preview
              </h2>
              <p className="mt-1 font-display text-2xl font-extrabold text-text-primary">
                $0
              </p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                <li>Public catalog overview by country</li>
                <li>Company preview cards and search</li>
                <li>Country guides with visa context</li>
                <li>No sign-in required for the homepage preview</li>
              </ul>
              <Button as="a" href="/" variant="primary" className="mt-6">
                Browse preview
              </Button>
            </Card>

            <Card className="px-5 py-6" accentBar>
              <h2 className="font-display text-xl font-bold text-text-primary">
                Full Access
              </h2>
              <p className="mt-1 font-display text-2xl font-extrabold text-text-primary">
                Coming soon
              </p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                <li>Full company board with refresh cadence</li>
                <li>Per-user apply / reject / not-for-me tracking</li>
                <li>Company workspace + documents</li>
                <li>Claude / Cursor MCP for gated CV reframe</li>
                <li>Cover letter and PDF render in your workspace</li>
              </ul>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button as="a" href="/panel" variant="primary">
                  Sign in for early access
                </Button>
                <Button as="a" href="/mcp" variant="secondary">
                  Explore MCP
                </Button>
              </div>
            </Card>
          </div>

          <section className="mt-10" aria-labelledby="limits-heading">
            <h2
              id="limits-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              Preview limits
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              The free preview is meant for market discovery: which countries
              look active, which companies appear in the catalog, and how
              sponsorship language shows up on career pages. Deep per-role
              tracking, private documents, and the MCP reframe flow require an
              account. Paid packaging for full board access is still being
              designed; early signed-in users are intended to be grandfathered
              when plans launch.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              Catalog data refreshes from company career pages about every six
              hours. Sponsorship-positive labels are signals, not legal advice.
              Official immigration guidance always wins when it conflicts with
              a listing summary.
            </p>
          </section>

          <section className="mt-10" aria-labelledby="mcp-price-heading">
            <h2
              id="mcp-price-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              MCP and CV tools
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              Connecting Claude or Cursor via Kuchup MCP is part of the signed-in
              workspace path. The agent can load job context you pin, run a
              gated CV reframe with your approval, and leave tailored LaTeX/PDFs
              in the company workspace. Kuchup never auto-applies — you review
              and submit on the employer site yourself. See{" "}
              <a href="/mcp" className="font-medium text-text-primary underline-offset-2 hover:underline">
                MCP for Claude and Cursor
              </a>{" "}
              for the flow.
            </p>
          </section>

          <p className="mt-8 text-center text-xs text-text-muted">
            Pricing details will be announced when the full access plan launches.
            Current signed-in users get grandfathered access where possible.
          </p>
        </main>
        <Footer />
      </div>
    </div>
  );
}
