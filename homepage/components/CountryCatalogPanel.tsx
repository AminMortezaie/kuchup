"use client";

import { useEffect, useState } from "react";
import type { CountrySnapshot } from "@/lib/country-snapshots";

type Props = {
  country: string;
  label: string;
  initial: CountrySnapshot | null;
};

type LiveState = {
  companies: number;
  jobs: number;
  visa_jobs: number;
  sample_names: string[];
  sample_positions: CountrySnapshot["sample_positions"];
  last_fetch: string;
};

function fromSnapshot(snapshot: CountrySnapshot | null): LiveState {
  if (!snapshot) {
    return {
      companies: 0,
      jobs: 0,
      visa_jobs: 0,
      sample_names: [],
      sample_positions: [],
      last_fetch: "",
    };
  }
  return {
    companies: snapshot.companies,
    jobs: snapshot.jobs,
    visa_jobs: snapshot.visa_jobs,
    sample_names: snapshot.sample_companies
      .map((row) => row.name)
      .filter(Boolean)
      .slice(0, 4),
    sample_positions: snapshot.sample_positions.slice(0, 5),
    last_fetch: snapshot.last_fetch || "",
  };
}

function formatCatalogDate(iso: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function CountryCatalogPanel({ country, label, initial }: Props) {
  const [state, setState] = useState<LiveState>(() => fromSnapshot(initial));

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [overviewRes, previewRes] = await Promise.all([
          fetch("/api/public/overview"),
          fetch(`/api/public/preview?country=${encodeURIComponent(country)}&limit=6`),
        ]);
        if (!overviewRes.ok || !previewRes.ok) return;
        const overview = await overviewRes.json();
        const preview = await previewRes.json();
        if (cancelled) return;

        const row = (overview.countries || []).find(
          (item: { country?: string }) => item.country === country,
        );
        const companies = (preview.companies || []) as Array<{ name?: string }>;
        const featuredScope = preview.meta?.featured_scope || "";
        const featured =
          featuredScope === "country"
            ? ((preview.featured_companies || []) as Array<{ name?: string }>)
            : [];
        const names = (companies.length ? companies : featured)
          .map((item) => item.name || "")
          .filter(Boolean)
          .slice(0, 4);

        setState((prev) => ({
          ...prev,
          companies: Number(row?.companies || 0),
          jobs: Number(row?.jobs || 0),
          visa_jobs: Number(row?.visa_jobs || 0),
          sample_names: names.length ? names : prev.sample_names,
        }));
      } catch {
        /* keep snapshot */
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [country]);

  if (
    state.companies <= 0 &&
    state.sample_names.length === 0 &&
    state.sample_positions.length === 0
  ) {
    return null;
  }

  const asOf = formatCatalogDate(state.last_fetch);

  return (
    <section className="mt-10" aria-label={`${label} catalog snapshot`}>
      <div className="country-stat-rail">
        <div>
          <strong>{state.companies}</strong>
          <span>Companies tracked</span>
        </div>
        <div>
          <strong>{state.jobs}</strong>
          <span>Roles indexed</span>
        </div>
        <div>
          <strong>{state.visa_jobs}</strong>
          <span>Sponsorship-positive signals</span>
        </div>
      </div>
      {asOf ? (
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          Catalog as of {asOf}. Counts refresh as company career pages update.
        </p>
      ) : null}
      {state.sample_names.length > 0 ? (
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          Examples currently in the {label} catalog:{" "}
          {state.sample_names.join(" · ")}. Names change as career pages
          refresh — open the board for the full list.
        </p>
      ) : null}
      {state.sample_positions.length > 0 ? (
        <div className="mt-5">
          <h2 className="font-display text-lg font-semibold text-text-primary">
            Sample roles from company career pages
          </h2>
          <ul className="mt-3 space-y-2">
            {state.sample_positions.map((role) => (
              <li key={`${role.company_name}-${role.title}-${role.url}`}>
                <a
                  href={role.url}
                  className="text-sm font-medium text-text-primary underline-offset-2 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {role.title}
                </a>
                <span className="text-xs text-text-muted">
                  {" "}
                  — {role.company_name}
                  {role.location ? ` · ${role.location}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
