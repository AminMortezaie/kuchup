# Kuchup company ownership and edit permissions

## What a Kuchup company is

A Kuchup company is a catalog company curated by Kuchup, not a personal company added for one user.

The flag is `companies.owned_by_kuchup` (`1` = Kuchup, `0` = not Kuchup). The companies table had no owner or `added_by` column before this.

## How existing rows are tagged

Migration `catalog_owned_by_kuchup_v1` adds `owned_by_kuchup INTEGER NOT NULL DEFAULT 1` and sets `owned_by_kuchup = 1` on every company row. Catalog writes that do not set the flag (admin add, scrape, sync) stay Kuchup. A conflict update does not change the flag, so a later sync does not retag a non-Kuchup row.

## Who can edit

Godfather is the existing admin role. `users.is_admin` is checked with `is_user_admin()`, the same check `admin_required` uses. That covers the panel admin user, `PANEL_ADMIN_EMAILS`, and staff logins. There is no separate godfather role.

On a Kuchup company, only an admin may:

- Rename the company (`POST` or `PATCH /api/companies/name`)
- Edit the careers / ATS URL (`POST` or `PATCH /api/companies/careers`)
- Refresh jobs (`POST /api/companies/fetch`)
- Remove the company (`POST /api/companies/remove` or `DELETE /api/companies`)

A signed-in non-admin gets `403` with `Only an admin can change a Kuchup company`. The board company menu hides those four actions when `owned_by_kuchup` is set and `user.is_admin` is false.

## Add company

Admins keep the full add flow, including the careers URL and the ATS hint. Those new rows stay `owned_by_kuchup = 1`.

Non-admins cannot set a careers URL or a concrete ATS hint. The add sheet hides both fields and asks for a country. `POST /api/companies` returns `403` (`Only an admin can set a careers or ATS URL`) if a non-admin sends either. A name plus a country is allowed. That row is stored with `owned_by_kuchup = 0`.

The MCP `add_company` tool still requires a careers URL and creates a Kuchup company. It is the catalog tool, not the public add sheet.

## Later: user-owned companies

Not built yet. When the dashboard is public, a user should be able to rename, edit the careers URL, refresh, and delete companies they added. They must still be unable to do that on Kuchup companies unless they are an admin.

`owned_by_kuchup = 0` is the extension point. A later change can record which user added the row and allow those four actions only for that user. This version does not add that check: any signed-in user can still call the four actions on a row with `owned_by_kuchup = 0`.
