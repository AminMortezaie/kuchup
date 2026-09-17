# Apple Liquid Glass skill × Warm Horizon — marketing UI discipline

**Status:** proposed — awaiting Amin approval. Not approved for implementation.  
**Last updated:** 2026-09-17  
**Authors:** growth review (Kio, 2026-09-17) + agent; Amin decision pending

Related: [design.md](../../design.md), [frontend-health-check.md](../reference/frontend-health-check.md), [full-spa-ui-modernization-proposal.md](full-spa-ui-modernization-proposal.md) (orthogonal — not this work)

---

## Summary

Adopt the **discipline** of the external [apple-design-skill](https://github.com/naplesblue/apple-design-skill) (MIT) as an agent skill plus a Kuchup overlay — not an Apple rebrand. Marketing and conversion pages get unified paper panels, hairline dividers, glass only where layers overlap, and a restraint / anti-slop checklist. Brand tokens stay Warm Horizon: warm paper ground, logo orange accent, navy ink.

**Recommended direction (default):** Phase 1 is skill install + token overlay + homepage / 1–2 conversion surfaces, gated by a **side-by-side mock** Amin signs off **before** any production CSS merge.

**Not recommended:** blind Apple reskin (cool `#f5f5f7` ground, Apple blue `#0071e3`); panel SPA rewrite; applying this to ads / brag / organic video; dropping Lexend/Manrope without an explicit font decision.

**Decision needed:** approve adapted adoption; Phase 1 surface set; marketing fonts — see [Decision asked of Amin](#decision-asked-of-amin).

---

## Source

| Source | What it contributes |
|--------|---------------------|
| [naplesblue/apple-design-skill](https://github.com/naplesblue/apple-design-skill) (MIT) | Agent design skill for Apple-grade web UI / liquid glass: unified surfaces, glass-as-seasoning, hierarchy via weight/size/grayscale, anti-slop checklist. Not a component library. |
| Growth review — Kio (2026-09-17) | Yes to a **proposal**. No to a blind Apple reskin. |
| [design.md](../../design.md) Warm Horizon | Locked brand: warm paper, orange `#ff6b35` / logo orange, navy ink, Lexend / Manrope. |
| [frontend-health-check.md](../reference/frontend-health-check.md) | Hybrid panel stays. No panel SPA rewrite. Marketing (`homepage/`, Next) is a separate app from the panel board. |

---

## Problem statement

AI-generated and incremental UI drifts toward **fragmented cards**, overused `backdrop-filter` blur, and **multi-accent noise**. That reads as generic AI chrome, not premium trust.

Marketing and conversion pages need that trust **without** losing Kuchup’s Warm Horizon identity (open door, warm light, relocation warmth). The skill’s default self-check (cool grey ground `#f5f5f7`, one Apple blue `#0071e3`, system/SF type) would wash that identity if copied literally.

This proposal is **marketing UI discipline**. It is not the July SPA rewrite, and it does not reopen [frontend-health-check.md](../reference/frontend-health-check.md) non-goals (no SPA, no merging marketing + panel, no Tailwind port of panel `styles.css`).

---

## Proposal (adapted, not Apple rebrand)

Keep the skill’s **rules**; remap its **tokens** onto Warm Horizon.

### Discipline to keep

- **Unified white/paper panels + hairline dividers** — sibling items on one surface, not a pile of cards.
- **Glass / frost only where layers overlap** — sticky nav, modal, colored CTA. Plain content stays solid paper + soft shadow.
- **Hierarchy via weight, size, and grayscale** — color is accent only (one brand orange, not a second brand hue).
- **Restraint / anti-slop checklist** before shipping UI — whitespace and hierarchy before extra border, fill, or icon.

### Token remap (keep brand)

| Skill default (do not take as brand) | Warm Horizon (keep) |
|--------------------------------------|---------------------|
| Page ground `#f5f5f7` (cool Apple grey) | `--color-paper` `#fcfaf7` (warm ivory in [design.md](../../design.md)) |
| Accent `#0071e3` (Apple blue) | `--color-accent` `#ff6b35` (logo orange) |
| Near-black UI ink | `--color-ink` `#0e3a69` (logo navy); muted `#5d7488` |
| System / SF as the brand face | Open — see font decision below |

Optional: translate the skill’s **spacing / radius / shadow / motion grammar** onto existing named tokens (`design-tokens.css`, `--space-*`, `--radius-*`, `--ease-out`). Do not introduce a parallel token set that fights Warm Horizon.

**Fonts (open for Amin):** a system/SF stack on marketing only is allowed **only if** it does not fight the Lexend (display) / Manrope (body) lock in [design.md](../../design.md). Default assumption until decided: keep Lexend/Manrope.

### How it would live in the repo (after approval)

1. Vendor or submodule the skill into the agent skills path.
2. Add a short **Kuchup overlay** doc that maps tokens (table above) and says: never use Apple blue / cool grey as brand ground or accent.
3. Agents read overlay **after** the skill, then apply the adapted checklist to in-scope marketing surfaces.

No UI code ships with this proposal.

---

## Scope

### Phase 1 (in)

- Install/adapt the skill (vendored or submodule) + short Kuchup overlay mapping tokens.
- Homepage / marketing / 1–2 conversion surfaces (`homepage/` Next app): homepage, plus optionally **pricing** (`/pricing`) and the primary **pricing-CTA / signup landing** close.
- One **side-by-side mock** (current vs proposed) for Amin sign-off **before** any production CSS merge.

### Phase 2 (optional, later)

- Logged-in panel polish using the same discipline on **new surfaces only**.
- No hybrid board rewrite. Panel stays Flask + vanilla + React island per [frontend-health-check.md](../reference/frontend-health-check.md).

### Explicitly out of scope

- Ads / brag / organic video creative
- Full SPA or panel React rewrite ([full-spa-ui-modernization-proposal.md](full-spa-ui-modernization-proposal.md) stays not approved)
- Dropping Warm Horizon for Apple blue / cool grey brand
- Changing product copy or positioning

---

## Success criteria

- [ ] Proposal approved by Amin
- [ ] Side-by-side mock approved
- [ ] Phase 1 PR: skill + overlay + marketing surfaces pass the **adapted** checklist
- [ ] Brand orange + warm paper still obvious in screenshots

---

## Risks

| Risk | Mitigation |
|------|------------|
| Over-Appling washes relocation warmth (cool grey, Apple blue, SF-as-brand) | Token remap is mandatory. Mock gate before any production CSS. Overlay forbids skill defaults as brand. |
| Touching the panel hybrid without need | Phase 1 is marketing (`homepage/`) only. Phase 2 is optional and new surfaces only. |
| Agents follow the skill’s self-check literally (`#f5f5f7`, `#0071e3`) | Overlay is the gate; checklist is remapped, not copied. |
| Font stack fights design.md | Fonts are an explicit Amin decision; default is keep Lexend/Manrope. |

---

## Decision asked of Amin

1. **Approve adapted adoption as above?** Discipline + Warm Horizon remap; mock before CSS. Not a blind Apple reskin.
2. **Phase 1 surfaces:** homepage only vs homepage + pricing / CTA (and signup landing)?
3. **Marketing fonts:** keep Lexend / Manrope, or allow SF / system on marketing only?

Until those are answered, do not install the skill into the shipping path and do not change production CSS.
