# Role filter tags

Title filtering is data in `role_filter_tags`, not a hardcoded list in the scraper.

## Tables

`role_filter_tags` stores `keyword`, `kind` (`include` or `exclude`), and `is_default`. Migration `role_filter_tags_v1` seeds every keyword from the previous `INCLUDE_KEYWORDS` and `EXCLUDE_KEYWORDS` lists, in that order, with `is_default = 1`.

`matching_jobs.matches_default_filter` is `1` when the title passes those default tags (plus the small set of title rules that still live in code: CTO, staff except `senior/staff`, cloud engineer without backend/software, AI platform without backend/software, and the engineer-title skip for the `marketing` and `hr` exclude words). Existing rows default to `1`.

`user_role_tag_prefs` stores a row only when a user turns a tag off (`enabled = 0`). No row means the tag stays on, which is the default for every user.

## Scrape

The listing call is stored in full: title, url, location, and whatever else that first response already included. Roles with `matches_default_filter = 0` do not get a description fetch, visa detection, a public slug, or a stored description. Only default matches continue through enrich, broadcast, and the role propagator.

Matching is still a case-folded substring check on the title.

## User override

Job preferences lists the tags. Turning an **exclude** tag off shows open roles whose title contains that keyword on that user's board (title, link, location). Those roles are mixed in at read time. They do not create `user_opportunities` or `position_broadcast_assignments`, and they do not count against free-plan caps. Other exclude tags and the code title rules still apply. Turning an include tag off is saved and does not add or remove roles on the board yet.

Companies that are not already on the user's board are not added.

## Left out of the default flows

Readers that power the default board, freemium broadcast, role-propagator inputs, public job pages, MCP company positions, and job counts only see `matches_default_filter = 1`. The Go propagator queries the same flag and does not assign the other rows. Its assignment and cap logic is unchanged.

Admins can add or edit tags from Job preferences or `POST`/`PATCH /api/admin/role-filter-tags`. A new tag is part of the global default on the next scrape.
