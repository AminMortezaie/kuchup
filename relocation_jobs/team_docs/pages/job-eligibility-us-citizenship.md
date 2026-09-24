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

The stamp is applied at read time. `matching_jobs` does not store a copy. Catalog sync and company upsert do not overwrite a non-empty value, so a re-scrape does not clear `US`. An empty value is filled on the next catalog write when the careers or ATS host is a GDIT Workday board.

## How GDIT was tagged

Migration `catalog_citizenship_required_v1` adds the column and sets `citizenship_required = 'US'` when `careers_url` or `ats_url` has a GDIT Workday host. The hostname's first label is `gdit` and the host ends with `.myworkdayjobs.com`, for example `gdit.wd5.myworkdayjobs.com`. A company inserted later with that host gets the same value. The match uses that host.

## Tag another company

Admins only. The check is `is_user_admin()`, the same admin gate as other Kuchup company edits. A signed-in non-admin gets `403` with `Only an admin can set a citizenship requirement`.

```
POST /api/companies/citizenship
{"country": "remote-ok", "company": "Leidos", "citizenship_required": "US"}
```

`citizenship_required` must be `US` or `""`. `""` clears the tag. A later catalog write fills an empty value again when the GDIT Workday host is still on the row.

SQL on the database host:

```sql
UPDATE companies
SET citizenship_required = 'US'
WHERE lower(name) = lower('Leidos');
```

Follow-up: scan job descriptions for citizenship phrases, and let the visa / relocation filter account for this tag.
