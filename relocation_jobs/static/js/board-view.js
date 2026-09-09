/** Build the view model passed to the React board. */

import { state } from "./state.js";
import { $ } from "./utils.js";
import { getDisplayCompanies } from "./render.js";
import { boardTotalPages } from "./board.js";
import { publishBoardView } from "./board-sync.js";
import { renderBoardScopeBanner } from "./board-scope.js";

function paginationView(loading = false) {
  const pageSize = state.boardMeta?.page_size ?? 25;
  const totalCompanies = state.boardMeta?.total_companies ?? null;
  return {
    page: state.boardPage ?? 1,
    pageSize,
    totalCompanies,
    totalPages: boardTotalPages(),
    loading,
  };
}

let lastView = null;

export function syncBoardView({ loading = false, preserveContent = false } = {}) {
  const hideContent = loading && !preserveContent;
  renderBoardScopeBanner(state.boardMeta || {});
  if (preserveContent && lastView) {
    publishBoardView({
      ...lastView,
      loading: false,
      pagination: { ...lastView.pagination, ...paginationView(loading) },
    });
    return;
  }
  lastView = {
    loading: hideContent,
    pagination: paginationView(loading),
    companies: hideContent ? [] : getDisplayCompanies(),
    meta: { ...(state.boardMeta || {}) },
    ui: {
      collapsed: [...state.collapsedCompanies],
      showNotForMe: [...state.showNotForMeCompanies],
      showRejected: [...state.showRejectedCompanies],
      fetchingCompanyKey: state.fetchingCompanyKey,
      serverFetchRunning: state.serverFetchRunning,
      scrapeEnabled: (
        (state.scrapeConfig?.company_fetch_enabled
          ?? state.scrapeConfig?.scrape_enabled) !== false
        && (
          Boolean(state.authState?.user?.is_admin)
          || (state.boardMeta?.plan || "free") !== "free"
        )
      ),
      plan: state.boardMeta?.plan || "free",
      positionRejectedOnly: Boolean($("positionRejectedOnly")?.checked),
      visaOnly: Boolean($("visaOnly")?.checked),
    },
  };
  publishBoardView(lastView);
}
