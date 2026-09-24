import assert from "node:assert/strict";
import test from "node:test";

import {
  buildFrozenOrderMap,
  recomputeNewestJobFetched,
  sortCompaniesNewest,
} from "../../../relocation_jobs/static/js/company-display-order.js";

function company(name, newest, jobs = null) {
  return {
    country: "germany",
    name,
    newest_job_fetched: newest,
    latest_fetched: newest,
    jobs: jobs ?? [{ fetched: newest, url: `https://example.com/${name}` }],
  };
}

function names(list) {
  return list.map((c) => c.name);
}

test("position interaction updates calculated rank but frozen visible order stays", () => {
  const a = company("A", "2026-01-03");
  const b = company("B", "2026-01-02", [
    { fetched: "2026-01-02", url: "https://example.com/b1" },
    { fetched: "2026-01-01", url: "https://example.com/b2" },
  ]);
  const c = company("C", "2026-01-01");
  const catalog = [a, b, c];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [b.jobs[1]];
  recomputeNewestJobFetched(b);
  assert.equal(b.newest_job_fetched, "2026-01-01");

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "B", "C"]);
});

test("rank move upward does not jump visible company during freeze", () => {
  const a = company("A", "2026-01-03");
  const b = company("B", "2026-01-01");
  const c = company("C", "2026-01-02");
  const catalog = [a, c, b];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [{ fetched: "2026-01-09", url: "https://example.com/b-new" }, ...b.jobs];
  recomputeNewestJobFetched(b);
  assert.equal(b.newest_job_fetched, "2026-01-09");

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "C", "B"]);

  const unfrozen = sortCompaniesNewest(catalog);
  assert.deepEqual(names(unfrozen), ["B", "A", "C"]);
});

test("rank move downward does not jump visible company during freeze", () => {
  const a = company("A", "2026-01-01");
  const b = company("B", "2026-01-03", [
    { fetched: "2026-01-03", url: "https://example.com/b-new" },
    { fetched: "2026-01-01", url: "https://example.com/b-old" },
  ]);
  const c = company("C", "2026-01-02");
  const catalog = [b, c, a];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [b.jobs[1]];
  recomputeNewestJobFetched(b);
  assert.equal(b.newest_job_fetched, "2026-01-01");

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["B", "C", "A"]);
});

test("fetch-more bucket load can change calculated rank without reshuffling", () => {
  const a = company("A", "2026-01-03");
  const b = company("B", "2026-01-01", [
    { fetched: "2026-01-01", url: "https://example.com/b1" },
  ]);
  const c = company("C", "2026-01-02");
  const catalog = [a, c, b];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs.push(
    { fetched: "2026-01-08", url: "https://example.com/b4" },
    { fetched: "2026-01-07", url: "https://example.com/b5" },
    { fetched: "2026-01-06", url: "https://example.com/b6" },
  );
  recomputeNewestJobFetched(b);
  assert.equal(b.newest_job_fetched, "2026-01-08");

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "C", "B"]);
});

test("multiple position interactions keep company in place while open roles remain", () => {
  const a = company("A", "2026-01-04");
  const b = company("B", "2026-01-03", [
    { fetched: "2026-01-03", url: "https://example.com/b1" },
    { fetched: "2026-01-02", url: "https://example.com/b2" },
    { fetched: "2026-01-01", url: "https://example.com/b3" },
  ]);
  const c = company("C", "2026-01-01");
  const catalog = [a, b, c];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs.shift();
  recomputeNewestJobFetched(b);
  b.jobs.shift();
  recomputeNewestJobFetched(b);
  assert.equal(b.jobs.length, 1);
  assert.equal(b.newest_job_fetched, "2026-01-01");

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "B", "C"]);
});

test("exhausted loaded jobs may leave while others stay stable under freeze", () => {
  const a = company("A", "2026-01-03");
  const b = company("B", "2026-01-02", [
    { fetched: "2026-01-02", url: "https://example.com/b1" },
  ]);
  const c = company("C", "2026-01-01");
  const catalog = [a, b, c];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [];
  recomputeNewestJobFetched(b);

  const remaining = catalog.filter((row) => (row.jobs || []).length > 0);
  const visible = sortCompaniesNewest(remaining, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "C"]);
  assert.equal(remaining.some((row) => row.name === "B"), false);
});

test("changing company B does not reorder unrelated companies under freeze", () => {
  const a = company("A", "2026-01-04");
  const b = company("B", "2026-01-03");
  const c = company("C", "2026-01-02");
  const d = company("D", "2026-01-01");
  const catalog = [a, b, c, d];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [{ fetched: "2026-01-09", url: "https://example.com/b-hot" }];
  recomputeNewestJobFetched(b);

  const visible = sortCompaniesNewest(catalog, { frozenOrder: frozen });
  assert.deepEqual(names(visible), ["A", "B", "C", "D"]);
});

test("releasing freeze reconciles visible order to latest calculated ranking", () => {
  const a = company("A", "2026-01-03");
  const b = company("B", "2026-01-01");
  const c = company("C", "2026-01-02");
  const catalog = [a, c, b];
  const frozen = buildFrozenOrderMap(catalog);

  b.jobs = [{ fetched: "2026-01-09", url: "https://example.com/b-new" }];
  recomputeNewestJobFetched(b);

  assert.deepEqual(names(sortCompaniesNewest(catalog, { frozenOrder: frozen })), ["A", "C", "B"]);
  assert.deepEqual(names(sortCompaniesNewest(catalog, { frozenOrder: null })), ["B", "A", "C"]);
});
