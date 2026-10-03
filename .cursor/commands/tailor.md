# /tailor

Optional Cursor entry point. **Source of truth:** Kuchup MCP `get_agent_skill("tailor")` (playbook file: `relocation_jobs/mcp/agent_skills/tailor.md`, also seeded into Postgres). **The command and the MCP playbook must stay aligned** — same batch flow, arena, and standing standards.

Batch-tailor one job CV (resolve job → phases 1–4 + anti-AI → **16-competitor arena** → show winner → one acceptance → save).

## Invoke

```text
/tailor
/tailor SumUp
/tailor newest looking to apply
/tailor germany Sumup Senior Backend Engineer
```

Optional args after `/tailor`: company name, country, title fragment, or posting URL.

## Instructions for the agent

Follow the **`get_agent_skill("tailor")`** playbook in **batch mode** (not interactive one-phase-per-turn). All rules below are **mandatory on every application**.

### 1. Resolve the job

1. Call Kuchup MCP: `list_looking_to_apply_jobs` and/or `list_application_queue`.
2. If a company was named: take that company's **newest** role by `posted_at` (else highest ATS id). Include **pinned** rows even when `looking_to_apply` is false.
3. If none named: newest `looking_to_apply` by `posted_at`.
4. `get_job_context(country, company, url)` — use `description_text` as the JD. If `has_description` is false, stop and ask for panel fetch or JD paste.
5. `get_reframe_pipeline`, `list_master_resumes`, `list_project_masters`; `get_master_resume` / `get_project_master` as needed.
6. Prefer skill default five phases over an old consolidated DB mega-prompt.
7. Load all four masters for the arena: **`go-final`**, **`java`**, **`python`**, **`fullstack`**.

### 2. One turn — phases 1–4 + anti-AI (internal)

Do **all** of this before the arena and before showing the user a draft:

1. **Phase 1** — JD + ATS lens (thesis, must-haves, requirements × evidence matrix weights=100, match score, ATS verdict, mirror target).
2. **Phase 2** — master slug, one mirror employer, pull list, skim-budget preview, interview gaps.
3. **Phase 3** — 1–2 NEW mirror bullets + KEEP/DROP for every role + skills reorder.
4. **Anti-AI gate** — rewrite any agent-written line that sounds generic/LLM (no leveraged/spearheaded/seamless/…; no abstract optimizer phrases). Kept master bullets stay **verbatim**.
5. **Phase 4** — full markdown candidate + change log (**not** the user-facing draft yet).

**Standing rules (orchestrator, competitors, judges):**

- If the master has **Founding Engineer / Kuchup**, keep it on the CV with **real production metrics** (do not drop it to force language purity).
- Skim budget: mirror ~5–7 (soft max 8); older roles taper; never ship 10–12 under one employer.
- Do not invent employers, dates, tools, or JD-domain work you cannot defend.
- Kept master bullets stay **verbatim**.
- Markdown only until acceptance — no `save_tailored_tex` yet; no `render_pdf`.
- On **`go-final`**, keep **Go Concurrency** in Skills — removing it is a negative for Go employers.

### 3. Mandatory CV arena (every application)

After phase 1–4, run a **16-competitor `--quick` single-elimination** tournament **before** any user-facing draft.

- **16 entrants:** four variants per master (`go-final`, `java`, `python`, `fullstack`).
- Each competitor gets the same **JD**, all **four masters**, and **all standing rules** (this section + §4).
- **Cursor cloud agents only:** use Cursor **Task** to spawn separate cloud agents for competitors and for each judge matchup. **Forbidden:** in-process self-judged loops (orchestrator drafts all 16 and picks the winner in-chat). **Orchestrator never competes and never judges.**
- **`--quick` bracket:** single-elimination 16 → 8 → 4 → 2 → 1; each match judged by a **separate judge cloud agent** for this JD.

**Show the user only the arena winner:**

- One line: winning **`master_resume_slug`** and why it won.
- **Reels four-layer** assessment (§4).
- Full **markdown draft** of the winner.

**Stop once with:**

> Reply **Accepted** to save `.tex`, or list edits.

Do not show phase 1–4 internals, bracket details, or losing drafts unless asked.

### 4. Standing standards (every application)

**Mr Adib method:** one page, reverse chronological; sections contact + title + summary + experience + skills + education; achievement bullets with metrics; each action verb ≤2×; no pronouns in bullets; no photo / DOB / marital / military; mirror JD keywords for ATS. **Before save:** score against the **102-point checklist**; report total / 102 and fix blocking misses.

**Reels four layers** on the winner — state how well each landed (do **not** silently rewrite kept master bullets):

1. **6-second scan** — skim-readable hierarchy and skim budget.
2. **ATS** — JD keywords without stuffing or fake claims.
3. **XYZ / metric** — defensible outcomes and measures.
4. **Humanize** — anti-AI gate; master voice.

**Anti-slop:** no Specialty / Proof / Targeting labels. Summary = plain prose: specialty → proof → intent. Still ban leveraged, spearheaded, seamless, abstract optimizer phrases.

**Visa line (match the role):**

- **EU / Germany:** EU Blue Card self-handled; qualifying contract + **Erklärung zum Beschäftigungsverhältnis**. Never UK-style “sponsorship required.”
- **UK / London:** employer **Skilled Worker sponsorship required**. Never a Blue Card line on a UK role.

### 5. On Accepted / save / go ahead

1. Re-score **102-point checklist**; fix blocking items.
2. Convert to LaTeX using the **winner's** master preamble/macros/section order.
3. `save_tailored_tex(...)` with `url`/`country`/`company` from `get_job_context`.
4. `validate_tex` — fix and re-save if blocking.
5. Tell the user to **Re-render PDF** on the panel company workspace (CV tab).
6. **Do not** `render_pdf`. **Do not** `mark_applied` unless the user explicitly asks.
7. Short close: mirrored / skim / emphasized / interview-only / saved / arena master / 102 score.
8. Offer: `Next /tailor <company>?` — do not start another job until asked.

### 6. Interactive escape hatch

If the user says *interactive*, *one phase*, or *gate each step*, switch to mcp-resume-reframe interactive mode (one phase per turn). Still run the **arena** after phase 4. Still apply all standing standards above.
