# Expired want-to-apply roles (future personalization)

**Status:** idea only. Not scheduled. May never be built.

This page is the product note for a possible **user personalization** module. It is not a spec for current panel behavior.

## What already happens

When someone hides a role with **Not for me**, they pick a reason:

| Reason | Meaning |
|--------|---------|
| Not for me | Role does not fit their goals |
| Expired | Posting closed or is no longer available |
| Wrong location | City or region is not relevant |
| No relocation | No visa or relocation support |

Any of those reasons sets `job_tracking.not_for_me` and stores `not_for_me_reason`. The role **leaves the Applications queue** (Apply, Applied, and Rejected). The position card shows that reason (Expired, Wrong location, and so on), not a bare "Not for me" label, once a reason is stored.

Restore is unchanged: it clears not-for-me and the role can re-enter a tab only if it still matches that tab's rule.

## The signal worth keeping

**Expired** on a role the user had **pinned** or marked **Want to apply** means: they wanted this posting and could not apply because it closed.

Those rows stay in `job_tracking`. Not-for-me does not clear `looking_to_apply` or `pinned`. So the combination is already stored:

- `not_for_me = 1`
- `not_for_me_reason = 'expired'`
- `looking_to_apply = 1` or `pinned = 1` from before the hide

No extra table is added for this idea.

## If personalization is built later

Use that combination as a positive hint: the user was interested, the listing died, and a **similar future role** may still fit (title family, stack, country, seniority). Suggestions should be new openings, not the closed posting.

This is optional. Shipping personalization is a separate decision. Until then, treat these rows as ordinary hide history and do not rank or recommend from them.
