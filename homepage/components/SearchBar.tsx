import { MARKETING_COUNTRY_KEYS, countryLabel } from "@/lib/countries";

export function SearchBar({ id }: { id?: string }) {
  return (
    <form id={id} action="/jobs" method="get" className="hero-search-form">
      <div className="hero-search-fields">
        <div className="hero-search-field">
          <label className="hero-search-label" htmlFor="hero-destination">
            Destination
          </label>
          <div className="hero-search-control">
            <GlobeIcon />
            <select
              id="hero-destination"
              name="country"
              defaultValue=""
              className="hero-search-select"
            >
              <option value="">All countries</option>
              {MARKETING_COUNTRY_KEYS.map((key) => (
                <option key={key} value={key}>
                  {countryLabel(key) ?? key}
                </option>
              ))}
            </select>
            <Chevron />
          </div>
        </div>
      </div>

      <button type="submit" className="btn-primary hero-search-submit">
        <span>Find roles</span>
        <ArrowIcon />
      </button>
    </form>
  );
}

function GlobeIcon() {
  return (
    <svg
      className="hero-search-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" />
    </svg>
  );
}

function Chevron() {
  return (
    <svg
      className="hero-search-chevron"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      className="hero-search-arrow"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
