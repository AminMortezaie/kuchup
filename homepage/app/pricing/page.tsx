import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Start with 30 monthly credits, add non-expiring credit packs when needed, or choose Full Access for an uncapped matched board.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "Pricing | Relocation Jobs",
    description:
      "Free includes 30 monthly credits. Purchased credit packs never expire, and Full Access removes board caps.",
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
      "Free includes 30 monthly credits. Purchased credit packs never expire, and Full Access removes board caps.",
    images: ["https://kuchup.com/og-default.png"],
  },
};

export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-site px-4 pb-8 pt-5 sm:px-5">
        <Header />
        <main className="mx-auto mt-12 max-w-4xl">
          <h1 className="text-fluid-hero text-text-primary">Plans & Pricing</h1>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            Relocation Jobs (Kuchup) is a curation-first tracker for
            visa-sponsored software engineering roles across Europe. Browse the
            public preview without an account. Sign in for a preference-matched
            board, tracking, workspaces, and MCP. Free includes monthly credits;
            top up only when you need more matched roles.
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

          <div className="mt-10 grid gap-5 md:grid-cols-3">
            <Card className="px-5 py-6">
              <h2 className="font-display text-xl font-bold text-text-primary">
                Free
              </h2>
              <p className="mt-1 font-display text-2xl font-extrabold text-text-primary">
                $0
              </p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                <li>Public catalog overview by country</li>
                <li>Company preview cards and search</li>
                <li>Country guides with visa context</li>
                <li>10 sticky matched company slots</li>
                <li>3 stable active roles per company</li>
                <li>30 credits every UTC calendar month</li>
                <li>Personal apply / reject / not-for-me tracking</li>
                <li>MCP connect with 20 write/render requests per day</li>
              </ul>
              <Button as="a" href="/panel" variant="primary" className="mt-6">
                Sign in with Google
              </Button>
            </Card>

            <Card className="px-5 py-6" accentBar>
              <h2 className="font-display text-xl font-bold text-text-primary">
                Credit packs
              </h2>
              <p className="mt-1 font-display text-2xl font-extrabold text-text-primary">
                From $4.99
              </p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                <li>50, 150, or 400-credit packs</li>
                <li>Purchased credits never expire</li>
                <li>Free monthly credits are always used first</li>
                <li>1 credit only when a new matched role is delivered</li>
                <li>Tracking actions and failed deliveries stay free</li>
              </ul>
              <Button as="a" href="/panel?credits=1" variant="primary" className="mt-6">
                Add credits
              </Button>
            </Card>

            <Card className="px-5 py-6">
              <h2 className="font-display text-xl font-bold text-text-primary">
                Full Access
              </h2>
              <p className="mt-1 font-display text-2xl font-extrabold text-text-primary">
                Coming soon
              </p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                <li>No Free company cap on your matched board</li>
                <li>Higher MCP daily quota (hundreds of requests)</li>
                <li>Free already includes workspace, documents, and MCP</li>
                <li>Purchased credit balance remains on your account</li>
              </ul>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button as="a" href="/panel" variant="primary">
                  Sign in for Free access
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
              What Free includes today
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              After Google sign-in, new accounts start on Free. Your board is
              filtered to the countries you choose and capped at 10 matched
              companies with 3 stable active roles each. You receive 30
              promotional credits each UTC month. A credit is spent only when a
              replacement role is successfully delivered; purchased credits
              never expire. MCP keeps a separate daily anti-abuse quota.
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
              in the company workspace. Free accounts share a daily MCP quota;
              remaining usage appears on Connect MCP after you sign in. Kuchup
              never auto-applies — you review and submit on the employer site
              yourself. See{" "}
              <a href="/mcp" className="font-medium text-text-primary underline-offset-2 hover:underline">
                MCP for Claude and Cursor
              </a>{" "}
              for the flow.
            </p>
          </section>

          <p className="mt-8 text-center text-xs text-text-muted">
            Credits are usage units with no cash or redemption value. Full Access
            pricing will be announced separately.
          </p>
        </main>
        <Footer />
      </div>
    </div>
  );
}
