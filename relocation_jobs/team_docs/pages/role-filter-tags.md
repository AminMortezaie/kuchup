# Role filter tags

Title filtering is data in `role_filter_tags`, not a hardcoded list in the scraper.

## Tables

`role_filter_tags` stores `keyword` and `kind` (`include` or `exclude`). Migration `role_filter_tags_v1` seeds every keyword from the previous `INCLUDE_KEYWORDS` and `EXCLUDE_KEYWORDS` lists, in that order.

`matching_jobs.matches_default_filter` is `1` when the title passes those tags (plus the small set of title rules that still live in code: CTO, staff except `senior/staff`, cloud engineer without backend/software, AI platform without backend/software, and the engineer-title skip for the `marketing` and `hr` exclude words). Existing rows default to `1`. The column is `NOT NULL`, so readers compare it with `= 1` or `= 0`.

`user_role_tag_prefs` stores a row only when a user turns an exclude tag off (`enabled = 0`). No row means that hide tag stays on. Include tags are not a per-user setting.

## Scrape

Each board scrape loads the keyword lists once and stamps every listing from the first board call. Roles with `matches_default_filter = 0` do not get a description fetch, visa detection, or enrich. Only open default matches continue through those steps, broadcast, and the role propagator.

The scrape loads every stored row for the company (`get_company`), so a non-default role keeps its original `fetched` and closes when it leaves the board. Reader queries that build the default board filter to `matches_default_filter = 1`.

Matching is still a case-folded substring check on the title. There is no process-wide keyword cache. The web process loads the lists on each request, and the scrape worker loads them once per board, so an admin edit applies on the next scrape without a restart.

## User override

Job preferences lists hide tags with toggles and include tags as a read-only list. Turning an exclude tag off shows open roles whose title contains that keyword on that user's board (title, link, location). Those roles are mixed in at read time. They do not create `user_opportunities` or `position_broadcast_assignments`, and they do not count against free-plan caps. Other exclude tags and the code title rules still apply. A request to turn an include tag off is rejected.

Companies that are not already on the user's board are not added.

## Left out of the default flows

Readers that power the default board, freemium broadcast, role-propagator inputs, public job pages, MCP company positions, and job counts only see `matches_default_filter = 1`. The Go propagator queries the same flag and does not assign the other rows. Its assignment and cap logic is unchanged.

Admins can add or edit tags from Job preferences or `POST`/`PATCH /api/admin/role-filter-tags`.
