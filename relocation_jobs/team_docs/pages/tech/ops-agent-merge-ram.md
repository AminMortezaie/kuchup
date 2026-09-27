# Ops-agent cutover and the merge follower

**When:** 27 Sep 2026  
**Status:** merge writes listings again. The next task is to start it with the SQS queue URL so role refresh is enqueued.

## What we changed

Grafana Alloy on the EC2 box was replaced by a small **ops-agent**. It scrapes host, container, and health metrics about once a minute, remote-writes them to Grafana Cloud, and stores the same samples in Postgres (`ops_metric_samples`).

The first deploy that was supposed to make that switch failed before the new agent started (Bake looked for a target named `default` and the panel/MCP build aborted). Alloy stayed up. Grafana showed two copies of each gauge: Alloy series used `job="integrations/unix"`, ops-agent uses `job="integrations/node_exporter"`.

After Alloy was removed, the memory that mattered was **`relocation-fetch-merge`**, not the metrics agent. That container is the only writer that turns Go fetch results into `matching_jobs`. The Go worker only stores raw `ok` / `empty` / `error` rows.

## Why the board stopped updating

On the panel image, merge tried to prefetch job descriptions by shelling out to `go`. `go` is not installed in that image, so the exception aborted the whole pass. The process sat around 260 MiB, used CPU, and wrote nothing to the board.

Stopping the container freed RAM (available memory went to about 760 MiB on the 1.8 GiB host) and also froze the board. That was the wrong tradeoff.

The follower was started again with one change: if `go` is missing, skip description prefetch and still merge listings. A deploy was required because the panel image copies source before the MCP stage installs Tectonic, so that image re-downloaded the TeX bundle even though pip stayed cached.

## What the catch-up looked like

Queued results were merged with several workers at once. On 2 CPUs the load average went to about 6. `relocation-fetch-merge` used more than one core. The Postgres **container** gauge climbed from about 200 MiB to about 400 MiB.

That gauge includes file cache. `docker stats` still showed the Postgres process around 220 MiB. `shared_buffers` is 128 MiB and did not change. The extra hundreds of MiB were cache from the burst, not the database process growing. Load fell once the burst finished; the cache number drops only when the kernel reclaims it.

## Next task — start the merge follower with the queue URL

`relocation-fetch-merge` is the process to start. After a country's pending fetch rows are all merged, it already calls `enqueue_country_opportunity_refresh`. That sends one SQS message:

`{"type":"country","country":"<country key>"}`

on the queue `user-opportunity-refresh`. `relocation-role-propagator` is already the consumer when the same URL is set. Nothing else should be started for this.

The merge container is currently started with `DATABASE_URL` only, so that call raises:

`assignment writer missing: set SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL or ROLE_PROPAGATOR_BIN`

Listings still land on the board. The refresh message never leaves the box.

To start it:

1. Put `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` in gitignored `.env` (the `user-opportunity-refresh` URL, same value the panel and fetch worker already get). Also pass `AWS_REGION`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` so `send_message` can run.
2. Pass those four variables into the `relocation-fetch-merge` `docker run`, the same way `scripts/ec2_app_deploy.sh` already passes them to the panel.
3. Start that container (`python3 -m relocation_jobs.fetch.merge_consumer`). On the next completed country run it enqueues the message; the propagator consumes it. Do not put the queue URL in this doc or any committed file.
