function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
}

export function PostgresRoundTripsPost() {
  return (
    <div className="engineering-prose">
      <p>
        In July 2026 the job board looked frozen. The server was up. The overlay
        stayed on “Loading board…” because <code>GET /api/board</code> was
        still working — for tens of seconds. Germany was worst, around{" "}
        <strong>90 seconds</strong>. It was easy to blame remote Postgres, or
        the job-description payloads we had just started storing. Neither was
        the bug.
      </p>
      <p>
        One Germany load made <strong>678 Postgres round-trips</strong> for 98
        companies. The jobs SQL was 0.67s. Location-label helpers ate ~44s.
      </p>

      <h2>What we saw</h2>
      <p>
        Timings on page 1, default newest sort, panel talking to EC2 Postgres:
      </p>
      <table>
        <caption>GET /api/board before and after the label cache</caption>
        <thead>
          <tr>
            <th scope="col">Request</th>
            <th scope="col">Before</th>
            <th scope="col">After</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Armenia</th>
            <td>~3s</td>
            <td>~0.6s</td>
          </tr>
          <tr>
            <th scope="row">Netherlands</th>
            <td>~32s</td>
            <td>~0.6s</td>
          </tr>
          <tr>
            <th scope="row">Germany</th>
            <td>~58–89s</td>
            <td>~1.7s</td>
          </tr>
          <tr>
            <th scope="row">Admin dashboard</th>
            <td>~143s</td>
            <td>Shell first; stats load async</td>
          </tr>
        </tbody>
      </table>
      <p>
        A first “fix” made Germany ~103s. The preview pass duplicated flatten
        work. Optimizations can regress.
      </p>

      <h2>What it was not</h2>
      <ul>
        <li>
          “Remote Postgres is slow.” WAN latency (~60ms) multiplied the bug. It
          was not the bug. Local Postgres would have hidden it longer.
        </li>
        <li>
          “Descriptions are huge now.” We had just stored job text for MCP.
          Germany’s description column was ~3.8&nbsp;MB. Worth omitting from
          list reads. Catalog SQL without descriptions was still 0.67s.
        </li>
        <li>
          “Newest sort loads everything.” True architectural cost. After the
          cache it was about 1–2s, not 90s.
        </li>
      </ul>
      <p>A profiler split it cleanly:</p>
      <pre>
        <code>{`SQL total                         0.67s
post-process (location sync × 98) 43.97s`}</code>
      </pre>
      <p>Postgres was fine. Python was not.</p>

      <h2>An innocent helper</h2>
      <p>
        The board is not a table read. Each request merges catalog companies
        with per-user tracking, then normalizes locations. Every company goes
        through <code>sync_company_location_fields()</code>. That calls{" "}
        <code>country_label()</code>, which called{" "}
        <code>all_country_labels()</code>, which ran this on every call:
      </p>
      <pre>
        <code>{`def all_country_labels() -> dict[str, str]:
    merged = dict(load_custom_countries())  # cached
    for key in list_catalog_country_keys():  # DB query EVERY call
        merged.setdefault(key, key.replace("-", " ").title())
    return merged`}</code>
      </pre>
      <p>
        <code>list_catalog_country_keys()</code> is{" "}
        <code>SELECT DISTINCT country</code> from companies and country meta.
        Custom-country labels were cached. The merge with catalog keys was not.
        Inside a per-company, per-city loop that is hundreds of identical
        queries.
      </p>
      <p>
        Counter on one Germany load: <strong>678 calls</strong> of{" "}
        <code>all_country_labels</code> for <strong>98 companies</strong>.
      </p>

      <h2>What we shipped</h2>
      <p>
        Cache the merged label dict in process memory. Invalidate on country
        writes and catalog writes. Stop re-sorting suffix labels per city.
        Board pagination omits <code>description_text</code>. Admin stats load
        on a separate request. MCP summaries select flags, not PDF bytes.
      </p>
      <table>
        <caption>Germany, after the cache, same remote Postgres</caption>
        <tbody>
          <StatRow
            label="Location sync × 98"
            value="0.51s (was 44s)"
          />
          <StatRow
            label="Full board, newest, page 1"
            value="1.7s (was 89–103s)"
          />
        </tbody>
      </table>
      <p>
        Ten days later a “cache invalidation” feature put Redis on that same
        helper and took the board down again. That write-up is{" "}
        <a href="/engineering/cache-check-in-the-hot-path">
          cache check in the hot path
        </a>
        .
      </p>

      <h2>The rule</h2>
      <p>
        Profile SQL versus post-process before blaming the database. Never put
        remote I/O inside a helper that runs per row of a list.{" "}
        <code>country_label()</code> looks free. In a loop over the board it
        is not.
      </p>
    </div>
  );
}
