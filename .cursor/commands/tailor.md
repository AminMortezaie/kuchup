# /tailor

Optional Cursor entry point. **Source of truth:** Kuchup MCP `get_agent_skill("tailor")` (playbook also seeded in Postgres).

Batch-tailor one job CV (resolve job → phases 1–4 + anti-AI → one acceptance → save).

## Invoke

```text
/tailor
/tailor SumUp
/tailor newest looking to apply
/tailor germany Sumup Senior Backend Engineer
```

Optional args after `/tailor`: company name, country, title fragment, or posting URL.

## Instructions for the agent

Follow the **`get_agent_skill("tailor")`** playbook in **batch mode** (not interactive one-phase-per-turn).

### 1. Resolve the job

1. Call Kuchup MCP: `list_looking_to_apply_jobs` and/or `list_application_queue`.
2. If a company was named: take that company's **newest** role by `posted_at` (else highest ATS id). Include **pinned** rows even when `looking_to_apply` is false.
3. If none named: newest `looking_to_apply` by `posted_at`.
4. `get_job_context(country, company, url)` — use `description_text` as the JD. If `has_description` is false, stop and ask for panel fetch or JD paste.
5. `get_reframe_pipeline`, `list_master_resumes`, `list_project_masters`; `get_master_resume` / `get_project_master` as needed.
6. Prefer skill default five phases over an old consolidated DB mega-prompt.

### 2. One turn — phases 1–4 + anti-AI

Do **all** of this before asking anything:

1. **Phase 1** — JD + ATS lens (thesis, must-haves, requirements × evidence matrix weights=100, match score, ATS verdict, mirror target).
2. **Phase 2** — master slug, one mirror employer, pull list, skim-budget preview, interview gaps.
3. **Phase 3** — 1–2 NEW mirror bullets + KEEP/DROP for every role + skills reorder.
4. **Anti-AI gate** — rewrite any agent-written line that sounds generic/LLM (no leveraged/spearheaded/seamless/…; no abstract optimizer phrases). Kept master bullets stay **verbatim**.
5. **Phase 4** — full markdown draft + change log.

**Standing rules (from production use):**

- If the master has **Founding Engineer / Kuchup**, keep it on the CV with **real production metrics** (do not drop it to force language purity).
- Skim budget: mirror ~5–7 (soft max 8); older roles taper; never ship 10–12 under one employer.
- Do not invent employers, dates, tools, or JD-domain work you cannot defend.
- Markdown only until acceptance — no `save_tailored_tex` yet; no `render_pdf`.

**Stop once with:**

> Reply **Accepted** to save `.tex`, or list edits.

### 3. On Accepted / save / go ahead

1. Convert to LaTeX using the **chosen master's** preamble/macros/section order.
2. `save_tailored_tex(...)` with `url`/`country`/`company` from `get_job_context`.
3. `validate_tex` — fix and re-save if blocking.
4. Tell the user to **Re-render PDF** on the panel company workspace (CV tab).
5. Short close: mirrored / skim / emphasized / interview-only / saved.
6. Offer: `Next /tailor <company>?` — do not start another job until asked.

### 4. Interactive escape hatch

If the user says *interactive*, *one phase*, or *gate each step*, switch to mcp-resume-reframe interactive mode (one phase per turn).
