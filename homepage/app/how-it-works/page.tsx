import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const STEPS = [
  {
    title: "Browse the public preview",
    body: "See which countries and companies are actively hiring. The homepage shows a live overview of supported countries and sampled company preview cards — no sign-in required.",
  },
  {
    title: "Sign in to unlock tracking",
    body: "Once you sign in, you get a preference-matched board with company-level tracking, per-user apply/reject/not-for-me state, and a company workspace for CVs and documents. Free accounts include a company cap; Full Access removes it when paid plans launch.",
  },
  {
    title: "Tailor your CV per job",
    body: "Connect Claude or Cursor to Kuchup MCP to align your CV with specific job descriptions. Project masters, cover letters, and LaTeX exports stay in the company workspace — you review and submit.",
  },
  {
    title: "Stay current",
    body: "The catalog refreshes automatically every 6 hours. New roles from company career pages appear in the board the same day. No stale syndicated listings.",
  },
] as const;

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "How Kuchup tracks visa-friendly software jobs in Europe: public preview, signed-in board tracking, and Claude/Cursor MCP for per-role CV prep.",
  alternates: { canonical: "/how-it-works" },
  openGraph: {
    title: "How It Works | Relocation Jobs",
    description:
      "Search the public preview, then sign in to track applications and prepare CVs with MCP across major European hubs.",
    url: "https://kuchup.com/how-it-works",
    siteName: "Relocation Jobs",
    type: "website",
    images: [
      {
        url: "https://kuchup.com/og-default.png",
        width: 1200,
        height: 630,
        alt: "How Kuchup works",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "How It Works | Relocation Jobs",
    description:
      "Search the public preview, then sign in to track applications and prepare CVs with MCP across major European hubs.",
    images: ["https://kuchup.com/og-default.png"],
  },
};

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-site px-4 pb-8 pt-5 sm:px-5">
        <Header />
        <main className="mx-auto mt-12 max-w-2xl">
          <h1 className="text-fluid-hero text-text-primary">How It Works</h1>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            Relocation Jobs is a curated search tool for software engineers
            looking for visa-sponsored roles in Europe. We read company career
            pages on a regular cadence so you see openings as they appear —
            not listings recycled from aggregators. The product is built around
            three layers: a public preview, a signed-in board for tracking, and
            an optional MCP connection for CV prep.
          </p>

          <section className="mt-10" aria-labelledby="problem-heading">
            <h2
              id="problem-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              The problem it solves
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              A relocation search usually fragments across career sites,
              spreadsheets, chat threads, and half-finished CV drafts. Sponsorship
              language is inconsistent, country rules differ, and by the time you
              return to a promising role the posting may already be gone. Kuchup
              keeps the market view, the decision state, and the application
              artifacts in one workspace so the thread does not break.
            </p>
          </section>

          <section className="mt-10" aria-label="Four steps">
            <h2 className="font-display text-2xl font-semibold text-text-primary">
              Four steps
            </h2>
            <ol className="workflow mt-6">
              {STEPS.map((step, index) => (
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

          <section className="mt-10" aria-labelledby="sources-heading">
            <h2
              id="sources-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              Where the jobs come from
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              The catalog is built from employer career pages and known applicant
              tracking systems. Kuchup detects the board type where possible and
              refreshes openings on a schedule (about every six hours). That is
              why country pages can show sample companies and roles that match
              what is currently indexed — and why counts change as sites update.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              Sponsorship-positive signals are heuristics derived from the
              posting and company context. They are not a guarantee. Country
              landing pages add visa context (Blue Card, HSM, Skilled Worker,
              and similar) so you can compare destinations before you deepen a
              search.
            </p>
          </section>

          <section className="mt-10" aria-labelledby="mcp-heading">
            <h2
              id="mcp-heading"
              className="font-display text-2xl font-semibold text-text-primary"
            >
              Where MCP fits
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              After you pin roles worth applying to, connect Claude or Cursor to
              the Kuchup MCP server. The agent loads job context from your
              catalog, runs a gated CV reframe with your approval between
              phases, and stores tailored PDFs in the company workspace. You
              still submit the application yourself. Details live on the{" "}
              <a
                href="/mcp"
                className="font-medium text-text-primary underline-offset-2 hover:underline"
              >
                MCP page
              </a>
              .
            </p>
          </section>

          <div className="mt-10 text-center">
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button as="a" href="/panel" variant="primary">
                Sign in to start tracking
              </Button>
              <Button as="a" href="/mcp" variant="secondary">
                Explore MCP
              </Button>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    </div>
  );
}
