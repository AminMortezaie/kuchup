# Agent playbook: tailor

Batch-tailor one job CV via Kuchup MCP: resolve the job → reframe phases 1–4 + anti-AI gate → **mandatory 16-competitor arena** → show the winner → one user acceptance → `save_tailored_tex` and `validate_tex` only.

## When to use

Load this playbook with `get_agent_skill("tailor")` (discover slugs via `list_agent_skills`). The user may hint which job to tailor: company name, country, title fragment, or posting URL.

Run in **batch mode** (phases 1–4, arena, then one user-facing draft in one turn before asking anything) unless the user asks for *interactive*, *one phase*, or *gate each step* — then run `get_reframe_pipeline` and execute **one pipeline prompt per turn** with user checkpoints. **Arena and standing standards below still apply** in interactive mode (arena runs after phase 4, before the user sees the draft).

## 1. Resolve the job

1. Call `list_looking_to_apply_jobs` and/or `list_application_queue` (optional `country` filter).
2. If the user named a company: pick that company's **newest** role by `posted_at` (else highest ATS id). Include **pinned** rows even when `looking_to_apply` is false.
3. If no company named: pick the newest `looking_to_apply` job by `posted_at`.
4. `get_job_context(country, company, url)` — use `description_text` as the JD. If `has_description` is false, stop and ask for a panel fetch (`save_position_description` / panel Fetch job description) or a JD paste.
5. `get_reframe_pipeline`, `list_master_resumes`, `list_project_masters`; `get_master_resume` / `get_project_master` as needed.
6. Prefer the ordered prompts from `get_reframe_pipeline` (up to five phases). Do not substitute one consolidated mega-prompt unless the profile pipeline is empty.
7. Load all four master resumes for the arena: **`go-final`**, **`java`**, **`python`**, **`fullstack`** via `get_master_resume`.

## 2. One turn — phases 1–4 + anti-AI (internal)

Do **all** of this before the arena and before showing the user a draft (batch mode):

1. **Phase 1** — JD + ATS lens (thesis, must-haves, requirements × evidence matrix weights=100, match score, ATS verdict, mirror target).
2. **Phase 2** — master slug, one mirror employer, pull list, skim-budget preview, interview gaps.
3. **Phase 3** — 1–2 NEW mirror bullets + KEEP/DROP for every role + skills reorder.
4. **Anti-AI gate** — rewrite any agent-written line that sounds generic/LLM (no leveraged/spearheaded/seamless/…; no abstract optimizer phrases). Kept master bullets stay **verbatim**.
5. **Phase 4** — full markdown CV candidate + change log (this is **orchestrator prep** for the arena; do **not** treat it as the user-facing draft).

**Standing rules (always — orchestrator, competitors, and judges):**

- If the master has **Founding Engineer / Kuchup**, keep it on the CV with **real production metrics** (do not drop it to force language purity).
- Skim budget: mirror role ~5–7 bullets (soft max 8); older roles taper; never ship 10–12 under one employer.
- Do not invent employers, dates, tools, or JD-domain work you cannot defend.
- Kept master bullets stay **verbatim** — no silent rewrites.
- Markdown only until acceptance — no `save_tailored_tex` yet; no `render_pdf`.
- On the **`go-final`** master, keep **Go Concurrency** in Skills — removing it is a negative signal for Go employers.

## 3. Mandatory CV arena (every application)

After the phase 1–4 candidate exists, run a **16-competitor, `--quick`, single-elimination** tournament **before** showing the user any draft.

### Non-negotiables

- **Every `/tailor` application** runs the arena. No skipping for speed, familiarity, or a “clear” master pick.
- **Cursor cloud agents only** — spawn competitors and judges with the Cursor **Task** tool (separate cloud-agent runs). **Forbidden:** an in-process self-judged loop where the orchestrator model drafts all entrants and picks the winner in one chat.
- The **orchestrator never competes** and **never judges**. It resolves the job, packages inputs, launches bracket tasks, collects results, and presents the champion.
- Each **competitor** receives: the same JD (`description_text`), the four masters (`go-final`, `java`, `python`, `fullstack`), and **all standing rules** in this playbook (Mr Adib, Reels, anti-slop, visa line, skim budget, anti-AI, Kuchup metrics, Go Concurrency on go-final).
- **16 entrants:** four variants per master slug (4 × 4 = 16). Variants may differ in mirror employer choice, mirror bullets, skim trim, or master slug emphasis — not in invented facts.
- **`--quick` bracket:** single-elimination 16 → 8 → 4 → 2 → 1. Each matchup: two competitor drafts → **one judge cloud agent** (not the orchestrator) picks the better CV for **this JD** with a one-paragraph rationale.
- Apply **Mr Adib**, **Reels**, and **anti-slop** inside every competitor draft; judges weigh JD fit, skim, ATS keywords, and truthfulness.

### Orchestrator output after arena

Do **not** show phase 1–4 internals, bracket trees, or non-winning drafts unless the user asks.

Show the user **only**:

1. Short note: **arena winner**, **`master_resume_slug`**, and one line on why it beat the field (from the final judge).
2. **Reels four-layer assessment** on the winner (see §4) — how well each layer landed.
3. The **winning markdown CV draft** (full body).
4. **Stop once with:**

> Reply **Accepted** to save `.tex`, or list edits.

## 4. Standing standards (every application)

Apply these to **every competitor draft**, the **arena winner**, and again before **save**.

### Mr Adib method (layout + scoring)

- **One page**, reverse chronological.
- Sections: **contact** + **title** + **summary** + **experience** + **skills** + **education** (no extra section sprawl).
- **Achievement bullets with metrics**; **Google XYZ** where honest.
- Each **action verb at most twice** across the CV.
- **No pronouns** in bullets.
- **No photo**, date of birth, marital status, or military service blocks.
- **Mirror JD keywords** for ATS (summary, skills, mirror bullets — not by rewriting kept master bullets).
- Before **`save_tailored_tex`**, score the draft against the **102-point checklist** (Mr Adib rubric). Report **total / 102** and any blocking misses; fix blocking items before save.

### Reels four layers (report on the user-facing draft)

Score how well the **winner** lands each layer; **say it explicitly** — do not silently “fix” a kept master bullet.

| Layer | What to assess |
|-------|----------------|
| **6-second scan** | Title, company lines, and top bullets readable at a glance; skim budget honored. |
| **ATS** | JD keywords present in summary/skills/mirror bullets without keyword stuffing or fake claims. |
| **XYZ / metric** | Bullets show outcome + measure + action; metrics are defensible. |
| **Humanize** | Anti-AI gate passed; sounds like the master voice, not generic LLM resume prose. |

### Anti-slop (summary + prose)

- **No** Specialty / Proof / Targeting **labels** (or similar tagged summary sections). Summary is **plain prose** in this order: **specialty** → **proof** → **intent** (target role/company).
- Still ban: *leveraged, spearheaded, seamless*, and abstract optimizer phrases.
- Kept master bullets: **verbatim** only.

### Visa line (must match the role)

Set from `get_job_context` country/location — **never mix EU and UK templates**.

| Region | Contact / summary visa line |
|--------|-----------------------------|
| **EU / Germany** | **EU Blue Card** — self-handled; candidate needs a qualifying contract and the standard German **Erklärung zum Beschäftigungsverhältnis**. Do **not** say employer “sponsorship required” like a UK Skilled Worker role. |
| **UK / London** | **Skilled Worker visa** — **employer sponsorship required**. Do **not** put a Blue Card line on a UK role. |

## 5. On Accepted / save / go ahead

1. Re-run **Mr Adib 102-point score** on the accepted draft; fix blocking gaps.
2. Convert to LaTeX using the **winner's** master preamble/macros/section order (`get_master_resume` for that slug).
3. `save_tailored_tex(country, company, url, content, master_resume_slug=...)` with `country`, `company`, and `url` from `get_job_context`.
4. `validate_tex(country, company, url, ...)` — fix blocking issues and re-save if needed.
5. Tell the user to **Re-render PDF** on the panel company workspace (CV tab).
6. **Do not** call `render_pdf`. **Do not** call `mark_applied` unless the user explicitly asks.
7. Short close: mirrored / skim / emphasized / interview-only / saved / arena master slug / 102-point score.
8. Offer the next tailor only if the user asks — **do not** start another job until requested.

## 6. Interactive escape hatch

If the user wants gated steps: call `get_reframe_pipeline`, run **one** phase per turn, and wait for **go ahead** between phases. Still run the **arena** after phase 4 and before the user-facing draft. Still use this playbook for standing rules and save steps.
