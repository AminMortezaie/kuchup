import CompanyCard from "./CompanyCard";
import BoardSkeleton from "./BoardSkeleton";

function emptyHint(meta, isRemote) {
  if (isRemote) {
    return "Try another remote board or clear filters.";
  }
  if (meta?.positions_capped) {
    return "Your credit balance is empty. Tracking still works; add credits to receive more matched roles.";
  }
  if (meta?.board_capped && (meta?.opportunity_count === 0 || (meta?.total_companies ?? 0) === 0)) {
    return "No open-role companies in your Free slots yet. Wait for catalog refresh or add credits.";
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
