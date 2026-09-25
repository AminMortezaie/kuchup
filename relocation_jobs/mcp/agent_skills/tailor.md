# Agent playbook: tailor

Batch-tailor one job CV via Kuchup MCP: resolve the job → reframe phases 1–4 + anti-AI gate → one user acceptance → `save_tailored_tex` and `validate_tex`.

## When to use

Load this playbook with `get_agent_skill("tailor")` (discover slugs via `list_agent_skills`). The user may hint which job to tailor: company name, country, title fragment, or posting URL.

Run in **batch mode** (all phases below in one turn before asking anything) unless the user asks for *interactive*, *one phase*, or *gate each step* — then run `get_reframe_pipeline` and execute **one pipeline prompt per turn** with user checkpoints.

## 1. Resolve the job

1. Call `list_looking_to_apply_jobs` and/or `list_application_queue` (optional `country` filter).
2. If the user named a company: pick that company's **newest** role by `posted_at` (else highest ATS id). Include **pinned** rows even when `looking_to_apply` is false.
3. If no company named: pick the newest `looking_to_apply` job by `posted_at`.
4. `get_job_context(country, company, url)` — use `description_text` as the JD. If `has_description` is false, stop and ask for a panel fetch (`save_position_description` / panel Fetch job description) or a JD paste.
5. `get_reframe_pipeline`, `list_master_resumes`, `list_project_masters`; `get_master_resume` / `get_project_master` as needed.
6. Prefer the ordered prompts from `get_reframe_pipeline` (up to five phases). Do not substitute one consolidated mega-prompt unless the profile pipeline is empty.

## 2. One turn — phases 1–4 + anti-AI

Do **all** of this before asking anything (batch mode):

1. **Phase 1** — JD + ATS lens (thesis, must-haves, requirements × evidence matrix weights=100, match score, ATS verdict, mirror target).
2. **Phase 2** — master slug, one mirror employer, pull list, skim-budget preview, interview gaps.
3. **Phase 3** — 1–2 NEW mirror bullets + KEEP/DROP for every role + skills reorder.
4. **Anti-AI gate** — rewrite any agent-written line that sounds generic/LLM (no leveraged/spearheaded/seamless/…; no abstract optimizer phrases). Kept master bullets stay **verbatim**.
5. **Phase 4** — full markdown CV draft + change log.

**Standing rules:**

- If the master has **Founding Engineer / Kuchup**, keep it on the CV with **real production metrics** (do not drop it to force language purity).
- Skim budget: mirror role ~5–7 bullets (soft max 8); older roles taper; never ship 10–12 under one employer.
- Do not invent employers, dates, tools, or JD-domain work you cannot defend.
- Markdown only until acceptance — no `save_tailored_tex` yet; no `render_pdf`.

**Stop once with:**

> Reply **Accepted** to save `.tex`, or list edits.

## 3. On Accepted / save / go ahead

1. Convert to LaTeX using the **chosen master's** preamble/macros/section order (`get_master_resume`).
2. `save_tailored_tex(country, company, url, content, master_resume_slug=...)` with `country`, `company`, and `url` from `get_job_context`.
3. `validate_tex(country, company, url, ...)` — fix blocking issues and re-save if needed.
4. Tell the user to **Re-render PDF** on the panel company workspace (CV tab).
5. Short close: mirrored / skim / emphasized / interview-only / saved.
6. Offer the next tailor only if the user asks — do not start another job until requested.

## 4. Interactive escape hatch

If the user wants gated steps: call `get_reframe_pipeline`, run **one** phase per turn, and wait for **go ahead** between phases. Still use this playbook for standing rules and save steps.
