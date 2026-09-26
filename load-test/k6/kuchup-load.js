import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = (__ENV.BASE_URL || "https://kuchup.com").replace(/\/+$/, "");
const AUTH_COOKIE = (__ENV.AUTH_COOKIE || "").trim();
const ENABLE_MUTATIONS = __ENV.ENABLE_MUTATIONS === "1";
const COUNTRY_RELOCATION = __ENV.COUNTRY_RELOCATION || "armenia";
const COUNTRY_REMOTE = __ENV.COUNTRY_REMOTE || "remote-ok";
const COMPANY_REMOTE_SLUG = __ENV.COMPANY_REMOTE_SLUG || "winatalent";
const COMPANY_ARMENIA_SLUG = (__ENV.COMPANY_ARMENIA_SLUG || "").trim();
const TIMEZONE_RELOCATION = __ENV.TIMEZONE_RELOCATION || "Asia/Yerevan";
const TIMEZONE_REMOTE = __ENV.TIMEZONE_REMOTE || "UTC";

const LOAD_STAGES = [
  { duration: "2m", target: 10 },
  { duration: "2m", target: 50 },
  { duration: "2m", target: 100 },
  { duration: "2m", target: 200 },
  { duration: "2m", target: 500 },
  { duration: "2m", target: 1000 },
  { duration: "2m", target: 2000 },
];

const SMOKE_STAGES = [{ duration: "45s", target: 2 }];

const isSmoke = __ENV.SMOKE === "1";

export const options = {
  stages: isSmoke ? SMOKE_STAGES : LOAD_STAGES,
  thresholds: isSmoke
    ? {
        http_req_failed: [{ threshold: "rate<=0.01", abortOnFail: true }],
      }
    : {
        http_req_duration: [{ threshold: "p(95)<=500", abortOnFail: true }],
        http_req_failed: [{ threshold: "rate<=0.01", abortOnFail: true }],
      },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

function request(method, path, { name, body, contentType } = {}) {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const params = {
    tags: { name },
    headers: {},
  };
  if (AUTH_COOKIE) {
    params.headers.Cookie = AUTH_COOKIE;
  }
  if (contentType) {
    params.headers["Content-Type"] = contentType;
  }
  const payload = body != null ? JSON.stringify(body) : null;
  return http.request(method, url, payload, params);
}

function boardQueryString(country, timezone, { remote = false } = {}) {
  const params = {
    country,
    timezone,
    page: "1",
    page_size: "25",
    visa_only: "0",
    hide_applied: "0",
    hide_empty: "0",
    not_applied_only: "0",
    hide_position_applied: "0",
    hide_position_rejected: "0",
    position_applied_only: "0",
    position_rejected_only: "0",
    position_looking_to_apply_only: "0",
    fetch_ok_only: "0",
    fetch_problem_only: "0",
    sort: "newest",
  };
  if (remote) {
    params.visa_only = "0";
  }
  return new URLSearchParams(params).toString();
}

function apiPrefix(remote) {
  return remote ? "/api/remote" : "/api";
}

function pickCompanyWithJob(board) {
  const companies = board && board.companies;
  if (!Array.isArray(companies)) {
    return null;
  }
  for (const co of companies) {
    const jobs = co && co.jobs;
    if (co && co.name && Array.isArray(jobs) && jobs.length > 0 && jobs[0].url) {
      return {
        company: co.name,
        jobUrl: jobs[0].url,
        idempotencyKey: jobs[0].idempotency_key || jobs[0].id || "",
      };
    }
  }
  return null;
}

function parseBoard(res) {
  if (res.status !== 200) {
    return null;
  }
  try {
    return JSON.parse(res.body);
  } catch {
    return null;
  }
}

function companyHtmlPath(remote) {
  if (remote) {
    return `/company/${COUNTRY_REMOTE}/${COMPANY_REMOTE_SLUG}`;
  }
  if (COMPANY_ARMENIA_SLUG) {
    return `/company/${COUNTRY_RELOCATION}/${COMPANY_ARMENIA_SLUG}`;
  }
  return `/company/${COUNTRY_REMOTE}/${COMPANY_REMOTE_SLUG}`;
}

function maybeMutatePin(ctx, country) {
  if (!ENABLE_MUTATIONS || !AUTH_COOKIE || !ctx) {
    return;
  }
  if (Math.random() >= 0.02) {
    return;
  }
  const body = {
    country,
    company: ctx.company,
    url: ctx.jobUrl,
    pinned: true,
  };
  if (ctx.idempotencyKey) {
    body.idempotency_key = ctx.idempotencyKey;
  }
  const pin = request("POST", "/api/jobs/pin", {
    name: "POST /api/jobs/pin",
    body,
    contentType: "application/json",
  });
  check(pin, { "pin ok": (r) => r.status === 200 });

  const unpinBody = { ...body, pinned: false };
  const unpin = request("PATCH", "/api/jobs/pin", {
    name: "PATCH /api/jobs/pin",
    body: unpinBody,
    contentType: "application/json",
  });
  check(unpin, { "unpin ok": (r) => r.status === 200 });
}

export default function kuchupLoadTest() {
  const remoteShell = __ITER % 2 === 0;
  const shellPath = remoteShell
    ? `/remote?country=${encodeURIComponent(COUNTRY_REMOTE)}`
    : `/panel?country=${encodeURIComponent(COUNTRY_RELOCATION)}`;
  const shellName = remoteShell ? "GET /remote" : "GET /panel";

  if (__ITER % 7 === 0) {
    const home = request("GET", "/", { name: "GET /" });
    check(home, { "landing ok": (r) => r.status >= 200 && r.status < 400 });
  }

  const shell = request("GET", shellPath, { name: shellName });
  check(shell, {
    "board shell ok": (r) => r.status >= 200 && r.status < 400,
  });

  sleep(3 + Math.random() * 4);

  let pinCtx = null;

  if (AUTH_COOKIE) {
    const remote = remoteShell;
    const country = remote ? COUNTRY_REMOTE : COUNTRY_RELOCATION;
    const tz = remote ? TIMEZONE_REMOTE : TIMEZONE_RELOCATION;
    const qs = boardQueryString(country, tz, { remote });
    const boardPath = `${apiPrefix(remote)}/board?${qs}`;
    const boardRes = request("GET", boardPath, {
      name: remote ? "GET /api/remote/board" : "GET /api/board",
    });
    check(boardRes, { "board json ok": (r) => r.status === 200 });
    const board = parseBoard(boardRes);
    pinCtx = pickCompanyWithJob(board);
  } else {
    const coPath = companyHtmlPath(remoteShell);
    const coPage = request("GET", coPath, { name: "GET /company" });
    check(coPage, {
      "company page ok": (r) => r.status >= 200 && r.status < 400,
    });
  }

  sleep(3 + Math.random() * 5);

  if (AUTH_COOKIE && pinCtx) {
    const remote = remoteShell;
    const country = remote ? COUNTRY_REMOTE : COUNTRY_RELOCATION;
    const tz = remote ? TIMEZONE_REMOTE : TIMEZONE_RELOCATION;
    const qs = boardQueryString(country, tz, { remote });
    const rolesPath =
      `${apiPrefix(remote)}/board/company-roles?${qs}` +
      `&company_country=${encodeURIComponent(country)}` +
      `&company=${encodeURIComponent(pinCtx.company)}` +
      "&offset=0";
    const roles = request("GET", rolesPath, {
      name: remote
        ? "GET /api/remote/board/company-roles"
        : "GET /api/board/company-roles",
    });
    check(roles, { "company-roles ok": (r) => r.status === 200 });
  } else {
    const fixed = `/company/${COUNTRY_REMOTE}/${COMPANY_REMOTE_SLUG}`;
    const co2 = request("GET", fixed, { name: "GET /company/winatalent" });
    check(co2, {
      "company workspace ok": (r) => r.status >= 200 && r.status < 400,
    });
  }

  maybeMutatePin(
    pinCtx,
    remoteShell ? COUNTRY_REMOTE : COUNTRY_RELOCATION,
  );

  if (__ITER % 11 === 0) {
    const health = request("GET", "/api/health", { name: "GET /api/health" });
    check(health, {
      "health ok": (r) => r.status === 200 || r.status === 503,
    });
  }

  sleep(5 + Math.random() * 10);
}
