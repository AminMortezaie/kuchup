import CompanyCard from "./CompanyCard";
import BoardSkeleton from "./BoardSkeleton";

function emptyHint(meta, isRemote) {
  if (meta?.needs_preferences) {
    return "Choose your target countries in Where to work to match companies with open roles.";
  }
  if (isRemote) {
    return "Try another remote board or clear filters. Remote listings are separate from your relocation country preferences.";
  }
  const targets = meta?.target_countries || [];
  const selected = meta?.country;
  if (selected && selected !== "all" && targets.length && !targets.includes(selected)) {
    const labels = targets.join(", ");
    return `Your preferences include ${labels}. Switch the country filter to one of those, or open Where to work to add more.`;
  }
  if (meta?.positions_capped) {
    return "Your credit balance is empty. Tracking still works; add credits to receive more matched roles.";
  }
  if (meta?.board_capped && (meta?.opportunity_count === 0 || (meta?.total_companies ?? 0) === 0)) {
    return "No open-role companies in your Free slots yet. Update Where to work or wait for catalog refresh.";
  }
  if ((meta?.total_companies ?? 0) === 0 && targets.length) {
    return `No open roles match ${targets.join(" or ")} with the current filters. Clear filters or edit Where to work.`;
  }
  return "Try another country or adjust your visa and location filters.";
}

export default function App({ view }) {
  if (view.loading) {
    return <BoardSkeleton />;
  }

  const meta = view.meta || {};
  const isRemote = meta.catalog_kind === "remote";

  if (!view.companies?.length) {
    return (
      <div className="empty empty--branded">
        <div className="empty-icon" aria-hidden="true">
          <img src="/static/icons/kuchup-bird.png" alt="" width="48" height="45" />
        </div>
        <p className="empty-title">No companies on this page</p>
        <p className="empty-hint text-sm text-muted">
          {emptyHint(meta, isRemote)}
        </p>
      </div>
    );
  }

  return view.companies.map((company) => (
    <CompanyCard
      key={`${company.country}:${company.name}`}
      company={company}
      ui={view.ui}
    />
  ));
}
