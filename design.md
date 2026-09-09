# Design — Kuchup / Relocation Jobs

A locked design system for this app. Every page redesign reads this file before
emitting code. Do not regenerate per page — extend or amend this file when the
system needs to grow.

## Genre

modern-minimal with an optimistic, human relocation tone. The system should
feel like an open door: warm light, clear guidance, approachable typography,
and enough energy to help people act without making the interface loud.

## Macrostructure family

- Marketing pages: Feature-stack / long-document with open spacing, soft
  elevation, and direct orange actions
- App pages: Workbench (dense board, filters, cards) — function carries the page
- Content pages: typography only

## Theme

Warm Horizon: a light palette derived from the Kuchup bird logo and the idea of
open skies, movement, and opportunity. Interaction and shape borrow from
Hallmark Hum, but the Hum pear/cyan/coral palette is deliberately not used.

- `--color-paper`   #fcfaf7 (warm ivory)
- `--color-paper-2` #f2f7fa (open-sky surface)
- `--color-paper-3` #e4f0f6
- `--color-ink`     #0e3a69 (logo navy)
- `--color-ink-2`   #345c7c
- `--color-muted`   #5d7488
- `--color-rule`    #a9c1d1
- `--color-accent`  #ff6b35 (logo orange)
- `--color-accent-hover` #ff7f52
- `--color-accent-deep` #d94f1f (button shadow, not small text)
- `--color-accent-text` #b84018 (AA small accent text on paper / paper-2)
- `--color-accent-2` #0e3a69 (secondary brand role)
- `--color-accent-ink` #082743 (AA text on orange)
- `--color-focus`   #ff6b35

Paper mode: **light** warm paper with sky-tinted supporting surfaces. Dark navy
is reserved for readable text and high-emphasis structure—never large
background fields. Brand chrome stays navy + orange. Do not introduce a second
brand accent (no Hum pear, coral, lavender, or page-scale rainbow). A chip-scale
**status layer** is required on the workbench so adjacent job actions stay
distinguishable — those hues are meaning, not competing brand color.

## Status layer (workbench)

Chip-scale only: tinted controls, badges, and card-edge tints. Combined status
fills stay well under the 5% accent budget. Never use these as page or section
fills.

| Meaning | Token | OKLCH | Use |
| --- | --- | --- | --- |
| Intent | `--intent` | `oklch(48% 0.12 240)` sky | Looking to apply |
| Success | `--success` | `oklch(44% 0.13 150)` green | Mark applied, Restore |
| Pending | `--pending` | `oklch(46% 0.11 295)` violet | Waiting referral, awaiting response |
| Danger | `--danger` | `oklch(48% 0.16 20)` crimson | Mark rejected |
| Dismiss | `--dismiss` | `oklch(55% 0.13 80)` ochre | Not for me, pin, warn |
| Memory | `--memory` | `oklch(46% 0.03 250)` slate | Seen before |
| Visa | `--visa` | `oklch(45% 0.08 195)` teal | Visa / relocation badge only |

Status control states (same pill/chip shape):

- Idle: ~8% tint, 1px hue border, hue text
- Hover: ~14% tint
- Active/on: ~20% tint, stronger border

Text on tinted fills must meet WCAG 4.5:1. Labels (not hue alone) carry meaning.

## Typography

- Display: Lexend, weight 600–700, style normal
- Body:    Manrope, weight 400–600
- Mono:    JetBrains Mono, weight 400–500
- Display tracking: -0.035em (hero) / -0.025em (section)
- Type scale anchor: `--text-display` = clamp(2.25rem, 4vw + 1rem, 3.5rem)

## Spacing

4-point named scale in `design-tokens.css`. Pages must use named tokens
(`var(--space-md)`), never raw values for system rhythm.

## Motion

- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`; `--ease-in`, `--ease-in-out`
- Reveal pattern: fade + short slide on marketing; none required on app chrome
- Reduced-motion fallback: opacity-only, ≤ 150 ms

## Microinteractions stance

- Silent success (celebratory toasts: never)
- Focus delay 0 ms; hover transitions ≤ 200 ms
- Press feedback: translateY(1px) / scale on `:active`
- Touch targets ≥ 44px

## CTA voice

- Primary CTA: orange fill (`--color-accent`), ink text (`--color-accent-ink`),
  pill radius, a restrained solid orange edge-shadow, and a physical press
- Secondary CTA: paper fill, 1px sky-blue outline, navy text, pill radius

### Marketing nav

Full-bleed sticky bar flush to the top (hairline bottom rule, no floating
island). Desktop: wordmark + links + compact Sign in / Board CTA. Mobile:
wordmark + menu only; the primary CTA and identity live inside the sheet.
The wordmark never shrinks or clips under chrome.

### Tab rails (app)

Horizontal tab rows (apply sections, company document type) scroll instead of
wrapping labels. Labels stay one line; the row is the thing that reflows.
Touch height stays `--control-height`.

### Control sizes (app chrome)

Named tokens in `design-tokens.css`. Chrome buttons, dialogs, tabs, selects, and
status chips in the same row share one box model so mixed `<a>` / `<button>`
pairs (e.g. Application data vs Sign out) match.

- `--control-height: 2.75rem` (44px touch target)
- `--control-pad-x: 0.85rem`
- `--control-font: 0.8125rem`
- `--control-line: 1`

Text-style `.link-btn` does not use this height. Icon-only squares that already
set an explicit size (avatar, pin) override it.

### App chrome (workbench)

Shared shell for `/panel`, `/remote`, `/admin`, `/apply`, and `/company`. Classes live in
`relocation_jobs/static/app-shell.css`. Palette tokens do not change.

- **Rail (N3):** sky paper (`--color-paper-2`), wordmark, collapse to icons.
  Active item uses `--color-accent-soft` pill — not a second brand hue.
  Below 900px the rail is a hamburger drawer; credits, add-company, and account
  controls move into that menu.
- **Page:** large Lexend title (`.app-page-title`), then a toolbar, then one
  workbench pane. Admin uses `location.hash` to show one pane; section IDs stay
  in the DOM.
- **Topbar:** existing credits control as `.app-usage-chip`; account menu stays
  on the right. Primary CTA remains orange; secondary remains outlined navy.
- **Paid/locked:** ochre status chip (`.app-lock`), never a gold crown or purple
  meter. Status hues stay chip-scale meaning only.
- **Cards/tables:** hairline `--border-subtle`, `--radius-card`, no gradient
  header stripe, almost no shadow.

## Hum adaptations

- Rounded, welcoming surfaces and pills in the Kuchup palette
- Primary buttons lift 1px on hover and press down 2px on active
- Cards deepen their tint and lift on hover; reduced motion removes translation
- Marketing workflow pages use a numbered narrative rail
- Orange owns primary action; sky-tinted surfaces support content; navy carries
  trust and readability
- No Hum pear, coral, lavender, or a second brand accent. Status chips (sky,
  green, violet, crimson, ochre, slate, teal) are allowed at control scale only.

## Per-page allowances

- Marketing pages MAY use enrichment (Tier-A CSS art, Tier-B SVG).
- App pages MUST NOT use enrichment — function carries the page.
- Content pages: typography only.

## What pages MUST share

- The wordmark / logotype (KUCHUP bird)
- Logo navy `#0e3a69` for ink and high-emphasis structure
- Brand orange as the clear primary accent (≤ 5 % per viewport as fill)
- Display + body fonts above
- CTA voice (button shape, border-radius, padding rhythm)
- 1px boundaries, rounded surfaces, and restrained soft elevation
- Tactile primary-button press feedback
- Workbench job-state chips use the status layer (intent / success / pending /
  danger / dismiss / memory / visa) — never brand navy as a stand-in

## What pages MAY differ on

- Macrostructure within the page-type family
- Hero archetype on marketing only
- Enrichment — marketing only, Tier-A or Tier-B

## Exports

Canonical CSS lives in:

- `relocation_jobs/static/design-tokens.css` (panel)
- `homepage/app/design-tokens.css` (marketing — keep in lockstep)

### tokens.css

```css
:root {
  --color-paper:      #fcfaf7;
  --color-paper-2:    #f2f7fa;
  --color-paper-3:    #e4f0f6;
  --color-ink:        #0e3a69;
  --color-ink-2:      #345c7c;
  --color-muted:      #5d7488;
  --color-rule:       #a9c1d1;
  --color-accent:     #ff6b35;
  --color-accent-ink: #082743;
  --color-focus:      #ff6b35;

  --color-status-sky:     oklch(48% 0.12 240);
  --color-status-green:   oklch(44% 0.13 150);
  --color-status-violet:  oklch(46% 0.11 295);
  --color-status-crimson: oklch(48% 0.16 20);
  --color-status-ochre:   oklch(55% 0.13 80);
  --color-status-slate:   oklch(46% 0.03 250);
  --color-status-teal:    oklch(45% 0.08 195);

  --font-display: "Lexend", sans-serif;
  --font-body:    "Manrope", sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, monospace;

  --space-3xs: 0.25rem;  --space-2xs: 0.5rem;  --space-xs: 0.75rem;
  --space-sm:  1rem;     --space-md:  1.5rem;  --space-lg: 2rem;
  --space-xl:  3rem;     --space-2xl: 4.5rem;  --space-3xl: 7rem;

  --radius-card: 16px; --radius-button: 999px; --radius-input: 12px;
  --control-height: 2.75rem; --control-pad-x: 0.85rem;
  --control-font: 0.8125rem; --control-line: 1;
  --shadow-card: 0 8px 24px rgba(14, 58, 105, 0.10);
}
```
