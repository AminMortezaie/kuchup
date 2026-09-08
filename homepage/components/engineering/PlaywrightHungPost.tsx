function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
}

export function PlaywrightHungPost() {
  return (
    <div className="engineering-prose">
      <p>
        On 10 July 2026 the scheduled Germany fetch started at 00:11 UTC. One
        generic career page needed a browser. Playwright started at 00:11:58 and
        never returned. At 00:13:37 the worker logged 97 of 98 companies done.
        The last one was still in flight.
      </p>
      <p>
        The container stayed “Up.” The scheduler was blocked on{" "}
        <code>wait_for_fetch_thread()</code> with <strong>no timeout</strong>.
        Country fetches did not run again until a manual restart at 15:50 —
        more than <strong>15 hours</strong> later. Chromium children from 00:12
        were still running until that restart.
      </p>

      <h2>What we saw</h2>
      <table>
        <caption>Germany run 341, 10 July 2026, UTC</caption>
        <tbody>
          <StatRow
            label="00:11:53"
            value="Country fetch started, 98 companies"
          />
          <StatRow
            label="00:11:58"
            value="Generic Playwright scrape started — never returned"
          />
          <StatRow
            label="00:13:37"
            value="Last log: 97/98 done"
          />
          <StatRow
            label="00:36:13"
            value={'Postgres: failed, “server restarted” (there was no restart)'}
          />
          <StatRow
            label="15:50:30"
            value="docker restart of the fetch worker; scheduler resumed"
          />
        </tbody>
      </table>
      <p>
        The 00:36 failure message was the panel. Panel and worker are separate
        processes sharing <code>fetch_runs</code>. The panel reaped the row as
        an orphan while the worker thread was still alive. The database said
        failed. The worker kept waiting forever.
      </p>

      <h2>What it was not</h2>
      <p>
        HTTP timeouts were already 15s. Playwright <code>page.goto</code> had a
        timeout. A stuck renderer does not care. The process watchdog did not
        exist. The country join did not exist as a ceiling either. One company
        owned the six-hour cycle.
      </p>

      <h2>Layered timeouts</h2>
      <p>
        Every blocking boundary gets a hard ceiling. Inner layers must be
        strictly shorter than outer layers.
      </p>
      <pre>
        <code>{`HTTP client                         15s
Playwright process (whole fallback) 90s
Per-company wait_for               300s
Scheduler join on the country     2700s
Scheduler sleep                      6h  (only after join returns)`}</code>
      </pre>
      <p>
        On timeout the company is skipped and logged. Remaining companies in
        that country continue. The scheduler joins, finalizes, and sleeps. It
        does not wait for a browser that will never come back.
      </p>
      <p>
        The panel no longer reaps running fetches it does not own. Orphan reap
        stays on worker bootstrap, after a real restart.
      </p>

      <h2>What timeouts do not bound</h2>
      <p>
        Timeouts bound how long a unit of work may run. They do not bound how
        many OS threads and browsers you create while it runs. In September the
        worker ran out of threads anyway. That write-up is{" "}
        <a href="/engineering/cant-start-new-thread">
          can&apos;t start new thread
        </a>
        .
      </p>

      <h2>The rule</h2>
      <p>
        Nothing in the fetch path may block without a bounded timeout. One
        hung career page must not block the rest of the country, the rest of
        the cycle, or the scheduler loop. “Up” is not a health signal when the
        join has no deadline.
      </p>
    </div>
  );
}
