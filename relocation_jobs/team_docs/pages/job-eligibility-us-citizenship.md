# Job eligibility tags: US Citizenship Required

## What the tag means

`US Citizenship Required` marks a hard eligibility blocker. It is for roles that need US citizenship, which is typical of US federal and defense contractors and is often paired with a security clearance. Kuchup users are mostly relocating non-US engineers, so the tag is meant to be visible on the job card.

Visa sponsorship stays on its own badge. The role stays on the board.

## Where it shows

The board job card renders `<span class="badge citizenship">US Citizenship Required</span>` beside the existing Visa / relocation badge. That card is the relocation board, the remote board, and the company workspace position card. The company workspace position list uses the same label.

## Data model

`companies.citizenship_required` is `TEXT NOT NULL DEFAULT ''`.

- `US` — every job at that company is stamped `citizenship_required: "US"` when the board or workspace payload is built
- empty — no citizenship tag

The stamp is applied at read time. `matching_jobs` does not store a copy. Catalog sync and company upsert set the column on insert from the company payload, default empty, and leave it out of the conflict update, so a re-scrape keeps the stored value.

## How GDIT was tagged

Migration `catalog_citizenship_required_v1` adds the column and runs once. It sets `citizenship_required = 'US'` where `careers_url` or `ats_url` matches `%://gdit.%myworkdayjobs.com%`, for example `https://gdit.wd5.myworkdayjobs.com/en-US/External_Career_Site`. A company added later is not tagged by that host.

## Tag another company

Admins only. The check is `is_user_admin()`, the same admin gate as other Kuchup company edits. A signed-in non-admin gets `403` with `Only an admin can set a citizenship requirement`.

```
POST /api/companies/citizenship
{"country": "remote-ok", "company": "Leidos", "citizenship_required": "US"}
```

`citizenship_required` must be `US` or `""`. `""` clears the tag. The next catalog sync keeps that value.

SQL on the database host:

```sql
UPDATE companies
SET citizenship_required = 'US'
WHERE lower(name) = lower('Leidos');
```

Follow-up: scan job descriptions for citizenship phrases, and let the visa / relocation filter account for this tag.
