import countriesJson from "@/data/countries.json";
import { COUNTRY_PAGES } from "@/lib/country-pages";

export type CountryLabels = Record<string, string>;

export const COUNTRY_LABELS: CountryLabels = countriesJson;

/** Marketing country guides that have real content (not soft-404 stubs). */
export const MARKETING_COUNTRY_KEYS = Object.keys(COUNTRY_PAGES).sort((a, b) =>
  a.localeCompare(b),
);

export function countryLabel(key: string): string | undefined {
  return COUNTRY_LABELS[key];
}

const MARKETING_LABEL_FALLBACK: Record<string, string> = {
  germany: "Germany",
  ireland: "Ireland",
  netherlands: "Netherlands",
  portugal: "Portugal",
  uk: "United Kingdom",
};

export function countryLinks(): { href: string; label: string }[] {
  return MARKETING_COUNTRY_KEYS.map((key) => ({
    href: `/relocation-jobs-${key}`,
    label: COUNTRY_LABELS[key] ?? MARKETING_LABEL_FALLBACK[key] ?? key,
  }));
}
