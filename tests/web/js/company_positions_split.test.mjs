import assert from "node:assert/strict";
import test from "node:test";

import {
  isHistoryPosition,
  partitionCompanyPositions,
  preferredWorkspacePosition,
} from "../../relocation_jobs/static/js/company-positions.js";

test("rejected and closed roles are history", () => {
  assert.equal(isHistoryPosition({ rejected: true }), true);
  assert.equal(isHistoryPosition({ closed_at: "2026-09-07T00:00:00+00:00" }), true);
  assert.equal(isHistoryPosition({ rejected: false, closed_at: "  " }), false);
  assert.equal(isHistoryPosition({ looking_to_apply: true, pinned: true, seen: true }), false);
});

test("partition splits active working list from history", () => {
  const { active, history } = partitionCompanyPositions([
    { idempotency_key: "want", looking_to_apply: true },
    { idempotency_key: "adjoe-supply", title: "Supply Integrations", rejected: true },
    { idempotency_key: "closed-applied", applied: true, closed_at: "2026-09-07" },
    { idempotency_key: "open" },
  ]);
  assert.deepEqual(active.map((p) => p.idempotency_key), ["want", "open"]);
  assert.deepEqual(history.map((p) => p.idempotency_key), ["adjoe-supply", "closed-applied"]);
});

test("preferred workspace position stays on active even if history has a PDF", () => {
  const preferred = preferredWorkspacePosition([
    { idempotency_key: "rejected-pdf", rejected: true, has_pdf: true },
    { idempotency_key: "active-open" },
  ]);
  assert.equal(preferred.idempotency_key, "active-open");
});

test("preferred workspace position uses history when nothing is active", () => {
  const preferred = preferredWorkspacePosition([
    { idempotency_key: "rejected-pdf", rejected: true, has_pdf: true },
    { idempotency_key: "closed", closed_at: "2026-09-07" },
  ]);
  assert.equal(preferred.idempotency_key, "rejected-pdf");
});
