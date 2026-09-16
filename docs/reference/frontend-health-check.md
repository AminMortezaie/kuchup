# Frontend health check (panel UI)

**Status:** review (doc only — no UI refactor in this change)  
**Last updated:** 2026-09-16  
**Scope:** `frontend/` (Vite + React island), how `board.js` lands in the panel, leftover vanilla JS on the board, homepage only where it shares a surface

Related: [architecture.md](architecture.md) (panel client map), [board.md](board.md), [contributing.md](../contributing.md), [full-spa-ui-modernization-proposal.md](../proposals/full-spa-ui-modernization-proposal.md) (proposal, not approved — see [Non-goals](#non-goals)).

This is a light audit for someone who is not a frontend specialist. It describes the current hybrid honestly and lists small incremental wins. It is **not** a rewrite plan.

---

## Current state

The panel is a **working hybrid multi-page app**, not a React SPA. Flask serves HTML shells; vanilla ES modules own auth, filters, dialogs, board load, and almost all clicks; a small React 19 island (~1,200 lines in `frontend/src/`) paints company cards, pagination, and the fetch progress UI on `/panel` and `/remote` only. That split is the main maintenance cost — React markup and vanilla `events.js` class-name delegation have to stay in sync — but the board itself is usable, paginated, and free of client secrets. Do not rewrite it. Learn the bridge, add a CI build so agents cannot merge broken JSX, and chip away at the few concrete footguns below.

The July 2026 SPA proposal is **stale in its route map** (production `/` is the Next marketing site; the panel lives at `/panel` and `/remote`) and in its “dark theme only / ~6k CSS / ~29 modules” counts. Its pain-point diagnosis (hybrid coupling, no frontend tests) is still true. Treat that proposal as background, not a backlog.

---

## Three UIs (do not mix them)

| Surface | Stack | Output | Same app as the panel? |
|---------|-------|--------|------------------------|
| **Panel board** (`/panel`, `/remote`) | Vanilla ES modules + React island | `static/js/*` + `static/dist/board.js` | Yes — this audit |
| **Panel other pages** (`/company/…`, `/apply`, `/admin`) | Vanilla only (`company.js`, `apply.js`, `admin.js`) | same `static/js/` | Same product, **no React** |
| **Marketing homepage** (`/`) | Next 15 + TypeScript + Tailwind | `static/homepage/` | **No** — separate app, shared brand tokens only |
| **Public job pages** (`/jobs`, `/jobs/<slug>`) | Jinja | `web/templates/` | **No** — server HTML |

Homepage: `homepage/package.json` has `next lint` and TypeScript. The panel React island has neither. Do not “unify” them. A change to the marketing site does not require a panel change, and vice versa.

---

## Panel map

```text
Flask  relocation_jobs/web/server.py
  /panel, /remote  →  static/index.html          (no-store)
  /company/…       →  static/company.html
  /apply           →  static/apply.html
  /admin           →  static/admin.html
  /                →  static/homepage/ (Next export; public.html fallback)

index.html script order:
  position-card.js   ← <position-card> web component (job rows)
  /static/dist/board.js   ← React 19 island (Vite)
  main.js            ← vanilla boot (auth, filters, events, board fetch)
         │
         └── window.relocationJobs  (the bridge)
```

### React island (`frontend/src/`, ~1,216 lines)

| File | Lines | Role |
|------|------:|------|
| `main.jsx` | 79 | Two roots (`#jobs`, fetch chrome) + portals |
| `App.jsx` | 58 | Loading skeleton, empty hints, company list |
| `CompanyCard.jsx` | 469 | Company header, badges, job lists — largest file |
| `FetchPanel.jsx` | 305 | Fetch progress / review modal |
| `BoardPagination.jsx` | 65 | Page controls → `goToBoardPage` |
| `FetchHeader.jsx` | 51 | Refresh button / progress chip |
| `format.js` / `sort.js` / `companyWorkspace.js` | 75 / 25 / 14 | Display helpers (duplicated on the vanilla side) |
| `JobCard.jsx` | 16 | Sets `.job` / `.variant` on `<position-card>` |
| `BoardSkeleton.jsx` | 20 | First-load placeholder |
| `CvApplicationBadges.jsx`, `constants.js` | 37 / 12 | **Dead** — nothing imports them |

Mount points in `static/index.html`: `#jobs`, `#board-pagination-root`, `#fetch-header-root`, `#fetch-panel-root`. `FetchPanel` currently portals to `document.body` (`main.jsx`), not the placeholder div.

**No React Router. No React Query. No API calls from React.** HTTP lives in `static/js/api.js` (`apiFetch`, `credentials: "same-origin"`). Vanilla pushes a view model through `board-sync.js` / `fetch-sync.js`; React registers `window.relocationJobs.setBoardView` / `setFetchView` (with `_pendingView` so load-order races do not drop the first paint).

### Vanilla still owns the board

`static/js/` is **37 modules, ~11k lines**. Biggest: `dialogs.js` (1,188), `position-card.js` (940), `events.js` (899), `company.js` (899), `scrape.js` (831), `api.js` (700). `renderCompanies()` no longer builds card HTML; it calls `syncBoardView()` and React paints. Clicks for rename / remove / collapse / not-for-me / rejected / edit-city still go through **document-level delegation** in `events.js`. Job-row UI is the `<position-card>` web component, not React.

`styles.css` is ~8,028 lines and imports `design-tokens.css` (light “Warm Horizon” palette). The SPA proposal’s “dark only, 6k lines” is outdated.

---

## How to change the board without breaking it

This is the #1 footgun. Several React buttons have **no `onClick`**. Vanilla finds them by CSS class.

| Class / hook | Owner | File |
|--------------|-------|------|
| `.collapse-company-btn` | vanilla | `events.js`, `CompanyCard.jsx` |
| `.show-not-for-me-btn`, `.show-rejected-btn` | vanilla | same |
| `.edit-city-btn`, `.edit-name-btn`, `.edit-careers-btn`, `.remove-company-btn` | vanilla | same |
| `.fetch-company-btn` | **both** — React `onClick` plus `data-*` | `CompanyCard.jsx`, `fetch-actions.js` |
| `.expand-roles-btn`, `.expand-cities-btn` | React `onClick` (local UI state) | `CompanyCard.jsx` |
| Pagination Previous / Next / page numbers | React → `window.relocationJobs.goToBoardPage` | `BoardPagination.jsx`, `main.js` |
| Fetch refresh / cancel / close | React → `window.relocationJobs.fetchActions` | `FetchHeader.jsx`, `FetchPanel.jsx`, `fetch-actions.js` |
| Apply / reject / pin / ATS / hide | `<position-card>` + `events.js` | `position-card.js` |

Rules of thumb:

1. **Do not rename those classes** without changing `events.js` in the same PR.
2. **Do not add a React `onClick`** on a vanilla-owned button without removing the delegated handler (double-fire).
3. After JSX changes: `cd frontend && npm run build`, then hard-refresh. `npm run dev` is **not** wired to Flask (no Vite proxy, no HTML entry). The panel always loads the built `static/dist/board.js`.
4. Bump `?v=` on the script tag in `index.html` when the bundle changes (`board.js?v=18` today) so a sticky module cache cannot serve the previous file. Flask already sends `Cache-Control: no-store` for `/static/` (`web/server.py`); the query param is extra insurance. The service worker (`static/sw.js`) is a no-op.

---

## What's already fine

- **Tiny React dependency tree** — `react` + `react-dom` + Vite only (`frontend/package.json`). Low supply-chain surface.
- **No client secrets** — no `VITE_*`, no `import.meta.env`, no tokens in `localStorage` from React. Google OAuth is a server redirect (`/api/auth/google`); the UI only calls `/api/auth/status` with cookies.
- **Session cookies** — `HttpOnly`, `SameSite=Lax`, `Secure` in production (`core/auth.py`). React never sees the session.
- **XSS in the React layer** — no `dangerouslySetInnerHTML`. Text is React-escaped. External links use `rel="noopener noreferrer"`.
- **Empty + loading states** — `BoardSkeleton.jsx`; `App.jsx` empty hints cover preferences, credits, remote vs relocation.
- **Server pagination** (~25 companies/page) plus `memo()` on `CompanyCard` / `JobCard`. Virtualization is not needed at this page size.
- **Deploy path** — `scripts/ec2_app_deploy.sh` `maybe_build_frontend()` rebuilds when `frontend/` is newer than `board.js` (`FORCE_FRONTEND=1` to force). Static tree is bind-mounted into the panel container.
- **Fetch modal Escape** — already handled in vanilla `events.js` (closes / settles the fetch session). Do not “fix” that only in React and drop the vanilla path.
- **Vanilla HTML builders mostly escape** — `utils.js` `escapeHtml` / `escapeAttr`; `position-card.js` and `dialogs.js` use them on titles, URLs, city labels. Residual attribute quoting is a small follow-up, not an emergency.

---

## Tooling snapshot

| Tool | Panel `frontend/` | Notes |
|------|-------------------|--------|
| TypeScript | No | All `.jsx` / `.js`. Homepage *does* use TS — leave that as-is. |
| ESLint / Prettier | No | No config under `frontend/` |
| Tests (Vitest / RTL / Playwright) | No | pytest covers API + flatten only (`.github/workflows/ci.yml`) |
| React Router / React Query | No | Correct for an island that does not own routing or fetching |
| a11y library | No | Some `aria-*` already on pagination, collapse, fetch dialog |
| Source maps | Off | Vite default; prod `board.js` is ~220 KB minified, one file |
| `npm run build` in CI | **No** | Agents can merge JSX that does not compile |

---

## DX / build / deploy

Vite writes a **fixed filename** into the Flask tree:

```7:20:frontend/vite.config.js
  build: {
    outDir: path.resolve(__dirname, "../relocation_jobs/static/dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "src/main.jsx"),
      output: {
        entryFileNames: "board.js",
        ...
      },
    },
  },
  base: "/static/dist/",
```

`index.html` loads it as `/static/dist/board.js?v=18`. The built file is committed so a clone can run the panel without Node; deploy still rebuilds when sources are newer.

Smells (not blockers):

- **`npm run dev` does nothing useful** for the panel — no proxy to `:5051`, Flask does not load the Vite dev server.
- **No hashed filenames**, so cache-bust is a manual `?v=` bump.
- **No code splitting** — acceptable at ~220 KB for two routes that already need React.
- CI never runs `npm run build` (or the homepage Next export).

---

## Quality, security, performance (cited)

**Hybrid coupling** — `CompanyCard.jsx` is 469 lines of presentational markup whose behavior lives in `events.js`. Fine until a class rename or a well-meaning `onClick` lands.

**Duplication** — `frontend/src/format.js` matches `static/js/utils.js` date helpers; `companyWorkspace.js` matches `static/js/company-workspace.js` (and a third copy inside `position-card.js`). Drift is more likely than a runtime bug. Do not invent a shared package to fix this unless you are already touching both sides.

**Dead files** — `CvApplicationBadges.jsx` and `constants.js` are unused. Rollup will tree-shake them out of `board.js`; they still confuse the next editor. Live CV badges are `cvBadges()` in `position-card.js`.

**Error states** — board errors toast from vanilla; React only has `view.loading`. That is OK if toasts keep working. There is no React error boundary.

**CSRF** — no token header anywhere in the JS. Mutating `fetch` calls rely on same-origin cookies + `SameSite=Lax`. That is a reasonable MPA stance in 2026; not a P0 unless you add a cross-site form poster. Do not put API tokens in the frontend to “fix” this.

**XSS leftover (vanilla, not React)** — `_attrRow()` in `position-card.js` puts URLs in HTML attributes via `escapeHtml`, not `escapeAttr` (quotes). `cvBadges()` interpolates `href` without escaping. Job URLs are mostly ATS-controlled; still the real XSS surface, because React never builds those strings.

**Performance** — `useMobileBoard()` in every `CompanyCard` attaches its own `matchMedia` listener (`CompanyCard.jsx`). At ~25 cards/page this is waste, not a freeze. `new Set(ui.collapsed || [])` is rebuilt per card per render. Skip list virtualization.

**a11y** — pagination (`aria-current`, `<nav aria-label>`), collapse (`aria-expanded`), fetch dialog (`role="dialog"` `aria-modal`) are in good shape. Gaps: expand-roles/cities buttons lack `aria-expanded`; fetch dialog has no focus trap (Escape works via `events.js`); i18n is hardcoded English everywhere — ignore unless you actually ship another locale.

**Auth in the UI** — `auth.js` owns login chrome and 401 → re-login. React only sees flags like `ui.scrapeEnabled` on the view model.

---

## Prioritized backlog

Effort: **S** = small focused PR, **M** = a few files / a careful pass, **L** = multi-week. Impact is for Amin-as-owner and for agents editing the board, not for a design-system résumé.

### P0 — do these; skip the rest until they hurt

| Item | Effort | Impact | Why this, not a rewrite |
|------|--------|--------|-------------------------|
| **CI: `cd frontend && npm ci && npm run build`** on PRs | S | High | `.github/workflows/ci.yml` never touches JS. Broken JSX merges today; pytest stays green. Optional extra: fail if `npm run build` dirties committed `board.js`. |
| **Write the hybrid selector contract next to the code** | S | High | 10–20 line comment (or a tiny table) at the top of `CompanyCard.jsx` and `events.js` listing vanilla-owned classes. This doc is the spec; the comment is what an agent actually reads. |
| **Keep `?v=` and `npm run build` in the same change** | S | Medium | Local panel serves stale `board.js` if you skip the build. Contributing already says this; treat it as a checklist, not a new system. Hashed filenames can wait. |

Three items. If only one happens, make it the CI build.

### P1 — small incremental wins

| Item | Effort | Impact |
|------|--------|--------|
| Delete `CvApplicationBadges.jsx` and `constants.js` | S | Low clutter, zero behavior change |
| Hoist `useMobileBoard()` to `App.jsx` and pass `isMobile` down | S | Drops N `matchMedia` listeners |
| `escapeAttr` (not `escapeHtml`) for `data-*` / `href` in `position-card.js` `cvBadges` / `_attrRow` | S | Closes the remaining HTML-attribute hole |
| Fetch dialog focus trap (keep vanilla Escape) | S–M | Keyboard users; do not duplicate close logic |
| `aria-expanded` on expand-roles / expand-cities buttons | S | Cheap a11y |
| One shared copy of `companyWorkspacePath` (vanilla module; React can duplicate until a later cleanup) — **or** just delete the extra copy in `position-card.js` and import `company-workspace.js` | S | Stops URL-slug drift |
| Optional ESLint + `eslint-plugin-jsx-a11y` on `frontend/` only, no TypeScript | S–M | Catches a11y + unused vars in CI; do not boil the ocean with a vanilla lint |

### P2 — later / only if you are already in the file

| Item | Effort | Impact |
|------|--------|--------|
| Split `CompanyCard.jsx` (header vs job lists) | M | Readability; easy to over-abstract |
| Vite `server.proxy` → `:5051` so `npm run dev` hot-reloads the island | M | DX; not required while the island is small |
| Hidden source maps for production debug | S | Only useful if you actually debug minified `board.js` |
| 3 Playwright smokes: login-gated board, pagination, fetch button visible | M | Safety net; do **not** retro-test all of `static/js/` |
| Deduplicate `format.js` ↔ `utils.js` | M | Easy to get wrong across two bundlers |
| Sync `homepage/app/design-tokens.css` with `static/design-tokens.css` | S | They already drift; only when a token change is visible on both |
| List virtualization | L | Not justified at ~25 companies/page |

---

## Non-goals

Leave these alone unless the product goal changes. Several showed up in [full-spa-ui-modernization-proposal.md](../proposals/full-spa-ui-modernization-proposal.md); this review **does not** approve that proposal.

- **No SPA rewrite** — no React Router shell, no Flask SPA fallback, no deleting `static/js/` “after cutover.”
- **No framework hop** — do not move the panel to Next.js because the homepage already uses Next. Two apps is correct.
- **No TypeScript conversion** of `frontend/` or `static/js/`. Homepage TS stays in `homepage/`.
- **No Tailwind port** of the 8k-line `styles.css`. Tokens already exist (`design-tokens.css`).
- **No React Query / Redux** — vanilla already owns server state.
- **No i18n framework** until there is a second locale.
- **No retroactive unit tests** of the vanilla layer. If you add tests, add them on the next React change (helpers in `format.js` / `sort.js`) or a couple of Playwright smokes.
- **No merging marketing + panel** into one frontend.
- **No dark/light theme project** as a prerequisite for other work — the panel already uses the light token palette.
- **No API contract changes** for UI cleanliness.

---

## Suggested next PR (when you want code)

1. CI job: Node + `npm ci && npm run build` in `frontend/`.  
2. In the same or a follow-up: delete the two dead React files; hoist `useMobileBoard`; `escapeAttr` on position-card attributes.  

That is a day’s work of actual help. A six-week SPA is not.
