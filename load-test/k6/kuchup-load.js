import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = (__ENV.BASE_URL || "https://kuchup.com").replace(/\/+$/, "");
const AUTH_COOKIE_ENV = (__ENV.AUTH_COOKIE || "").trim();
const KUCHUP_EMAIL = (__ENV.KUCHUP_EMAIL || "").trim();
const KUCHUP_PASSWORD = (__ENV.KUCHUP_PASSWORD || "").trim();
const COUNTRY_RELOCATION = __ENV.COUNTRY_RELOCATION || "armenia";
const COUNTRY_REMOTE = __ENV.COUNTRY_REMOTE || "remote-ok";
const COMPANY_REMOTE_SLUG = __ENV.COMPANY_REMOTE_SLUG || "winatalent";
const COMPANY_ARMENIA_SLUG = (__ENV.COMPANY_ARMENIA_SLUG || "").trim();
const TIMEZONE_RELOCATION = __ENV.TIMEZONE_RELOCATION || "Asia/Yerevan";
const TIMEZONE_REMOTE = __ENV.TIMEZONE_REMOTE || "UTC";

const MUTATION_RATE = 0.02;

const SOFT_RAMP_STAGES = [
  { duration: "1m", target: 5 },
  { duration: "1m", target: 10 },
  { duration: "1m", target: 25 },
  { duration: "2m", target: 50 },
];

const FULL_RAMP_STAGES = [
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
const isFullRamp = __ENV.FULL_RAMP === "1";

function resolveStages() {
  if (isSmoke) {
    return SMOKE_STAGES;
  }
  if (isFullRamp) {
    return FULL_RAMP_STAGES;
  }
  return SOFT_RAMP_STAGES;
}

export const options = {
  stages: resolveStages(),
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

function cookieHeaderFromResponse(res) {
  const parts = [];
  const jar = res.cookies || {};
  for (const name of Object.keys(jar)) {
    for (const c of jar[name]) {
      parts.push(`${c.name}=${c.value}`);
    }
  }
  return parts.join("; ");
}

export function setup() {
  if (AUTH_COOKIE_ENV) {
    return { cookieHeader: AUTH_COOKIE_ENV };
  }
  if (!KUCHUP_EMAIL || !KUCHUP_PASSWORD) {
    return { cookieHeader: "" };
  }
  const res = http.post(
    `${BASE_URL}/api/auth/staff`,
    JSON.stringify({ email: KUCHUP_EMAIL, password: KUCHUP_PASSWORD }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { name: "POST /api/auth/staff" },
    },
  );
  check(res, { "staff login ok": (r) => r.status === 200 });
  const cookieHeader = cookieHeaderFromResponse(res);
  if (!cookieHeader) {
    console.warn(
      "KUCHUP_EMAIL/KUCHUP_PASSWORD login did not return session cookies; use AUTH_COOKIE from browser",
    );
  }
  return { cookieHeader };
}

function request(method, path, cookieHeader, { name, body, contentType } = {}) {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const params = {
    tags: { name },
    headers: {},
  };
  if (cookieHeader) {
    params.headers.Cookie = cookieHeader;
  }
  if (contentType) {
    params.headers["Content-Type"] = contentType;
  }
  const payload = body != null ? JSON.stringify(body) : null;
  return http.request(method, url, payload, params);
}

function boardQueryString(country, timezone) {
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
  return new URLSearchParams(params).toString();
}

function apiPrefix(remote) {
  return remote ? "/api/remote" : "/api";
}

function pickCompanyWithJob(board, jobIndex = 0) {
  const companies = board && board.companies;
  if (!Array.isArray(companies)) {
    return null;
  }
  for (const co of companies) {
    const jobs = co && co.jobs;
    if (
      co &&
      co.name &&
      Array.isArray(jobs) &&
      jobs.length > jobIndex &&
      jobs[jobIndex].url
    ) {
      const job = jobs[jobIndex];
      return {
        company: co.name,
        jobUrl: job.url,
        idempotencyKey: job.idempotency_key || job.id || "",
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

function jobMutationBody(ctx, country, extra) {
  const body = {
    country,
    company: ctx.company,
    url: ctx.jobUrl,
    ...extra,
  };
  if (ctx.idempotencyKey) {
    body.idempotency_key = ctx.idempotencyKey;
  }
  return body;
}

function maybeMutatePin(ctx, country, cookieHeader) {
  if (!cookieHeader || !ctx || Math.random() >= MUTATION_RATE) {
    return;
  }
  const body = jobMutationBody(ctx, country, { pinned: true });
  const pin = request("POST", "/api/jobs/pin", cookieHeader, {
    name: "POST /api/jobs/pin",
    body,
    contentType: "application/json",
  });
  check(pin, { "pin ok": (r) => r.status === 200 });

  const unpin = request("PATCH", "/api/jobs/pin", cookieHeader, {
    name: "PATCH /api/jobs/pin",
    body: jobMutationBody(ctx, country, { pinned: false }),
    contentType: "application/json",
  });
  check(unpin, { "unpin ok": (r) => r.status === 200 });
}

function maybeMutateLta(ctx, country, cookieHeader) {
  if (!cookieHeader || !ctx || Math.random() >= MUTATION_RATE) {
    return;
  }
  const on = request("POST", "/api/jobs/looking-to-apply", cookieHeader, {
    name: "POST /api/jobs/looking-to-apply",
    body: jobMutationBody(ctx, country, { looking_to_apply: true }),
    contentType: "application/json",
  });
  check(on, { "lta on ok": (r) => r.status === 200 });

  const off = request("PATCH", "/api/jobs/looking-to-apply", cookieHeader, {
    name: "PATCH /api/jobs/looking-to-apply",
    body: jobMutationBody(ctx, country, { looking_to_apply: false }),
    contentType: "application/json",
  });
  check(off, { "lta off ok": (r) => r.status === 200 });
}

export default function kuchupLoadTest(data) {
  const cookieHeader = (data && data.cookieHeader) || AUTH_COOKIE_ENV;
  const authenticated = Boolean(cookieHeader);

  const remoteShell = __ITER % 2 === 0;
  const shellPath = remoteShell
    ? `/remote?country=${encodeURIComponent(COUNTRY_REMOTE)}`
    : `/panel?country=${encodeURIComponent(COUNTRY_RELOCATION)}`;
  const shellName = remoteShell ? "GET /remote" : "GET /panel";

  if (__ITER % 7 === 0) {
    const home = request("GET", "/", cookieHeader, { name: "GET /" });
    check(home, { "landing ok": (r) => r.status >= 200 && r.status < 400 });
  }

  const shell = request("GET", shellPath, cookieHeader, { name: shellName });
  check(shell, {
    "board shell ok": (r) => r.status >= 200 && r.status < 400,
  });

  sleep(3 + Math.random() * 4);

  let pinCtx = null;
  let ltaCtx = null;

  if (authenticated) {
    const remote = remoteShell;
    const country = remote ? COUNTRY_REMOTE : COUNTRY_RELOCATION;
    const tz = remote ? TIMEZONE_REMOTE : TIMEZONE_RELOCATION;
    const qs = boardQueryString(country, tz);
    const boardPath = `${apiPrefix(remote)}/board?${qs}`;
    const boardRes = request("GET", boardPath, cookieHeader, {
      name: remote ? "GET /api/remote/board" : "GET /api/board",
    });
    check(boardRes, { "board json ok": (r) => r.status === 200 });
    const board = parseBoard(boardRes);
    pinCtx = pickCompanyWithJob(board, 0);
    ltaCtx = pickCompanyWithJob(board, 1) || pinCtx;
  } else {
    const coPath = companyHtmlPath(remoteShell);
    const coPage = request("GET", coPath, cookieHeader, { name: "GET /company" });
    check(coPage, {
      "company page ok": (r) => r.status >= 200 && r.status < 400,
    });
  }

  sleep(3 + Math.random() * 5);

  if (authenticated && pinCtx) {
    const remote = remoteShell;
    const country = remote ? COUNTRY_REMOTE : COUNTRY_RELOCATION;
    const tz = remote ? TIMEZONE_REMOTE : TIMEZONE_RELOCATION;
    const qs = boardQueryString(country, tz);
    const rolesPath =
      `${apiPrefix(remote)}/board/company-roles?${qs}` +
      `&company_country=${encodeURIComponent(country)}` +
      `&company=${encodeURIComponent(pinCtx.company)}` +
      "&offset=0";
    const roles = request("GET", rolesPath, cookieHeader, {
      name: remote
        ? "GET /api/remote/board/company-roles"
        : "GET /api/board/company-roles",
    });
    check(roles, { "company-roles ok": (r) => r.status === 200 });
  } else if (!authenticated) {
    const fixed = `/company/${COUNTRY_REMOTE}/${COMPANY_REMOTE_SLUG}`;
    const co2 = request("GET", fixed, cookieHeader, {
      name: "GET /company/winatalent",
    });
    check(co2, {
      "company workspace ok": (r) => r.status >= 200 && r.status < 400,
    });
  }

  const country = remoteShell ? COUNTRY_REMOTE : COUNTRY_RELOCATION;
  maybeMutatePin(pinCtx, country, cookieHeader);
  maybeMutateLta(ltaCtx, country, cookieHeader);

  if (__ITER % 11 === 0) {
    const health = request("GET", "/api/health", cookieHeader, {
      name: "GET /api/health",
    });
    check(health, {
      "health ok": (r) => r.status === 200 || r.status === 503,
    });
  }

  sleep(5 + Math.random() * 10);
}
