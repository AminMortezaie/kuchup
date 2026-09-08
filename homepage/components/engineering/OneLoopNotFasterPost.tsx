function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
}

export function OneLoopNotFasterPost() {
  return (
    <div className="engineering-prose">
      <p>
        On 2 September country fetch stopped starting an OS thread per company.
        Companies now run on one event loop, bounded by{" "}
        <code>asyncio.Semaphore</code>. The{" "}
        <a href="/engineering/cant-start-new-thread">
          outage
        </a>{" "}
        was <code>RuntimeError: can&apos;t start new thread</code>. That is the
        number this change is allowed to claim.
      </p>
      <p>
        A first version of this note compared Germany’s median duration before
        and after. That comparison is wrong. The healthy week ran at
        concurrency 4 on the thread pool. The after window runs at concurrency
        2 on the event loop. Two knobs moved. Failed outage runs lasted about
        a second with <code>new_jobs = 0</code>; those are not a speed
        baseline. Duration is not scored here.
      </p>

      <h2>The same error, before and after</h2>
      <p>
        Grafana Cloud on this box is host health: disk, available RAM, a probe
        of <code>/api/health</code>. It does not store per-company fetch
        outcomes. Counts are Postgres — <code>company_fetch_attempts</code>{" "}
        and <code>fetch_runs</code> — queried on 6 September 2026.
      </p>
      <p>
        Production picked up <code>FETCH_SCHEDULE_CONCURRENCY=2</code> at{" "}
        <strong>16:09 UTC on 3 September</strong> (first run: Armenia). That
        is the after cut for “is the thread error gone,” not a claim that two
        is faster or slower than four.
      </p>
      <table>
        <caption>
          Same failure string. Outage window is 28 August through 1 September.
          After starts 3 September 16:09 UTC.
        </caption>
        <tbody>
          <StatRow
            label="Outage attempt errors"
            value="357 / 358 were can't start new thread"
          />
          <StatRow
            label="Attempts since 3 September 16:09 UTC"
            value="3,375 / 3,375 ok"
          />
          <StatRow label="Thread errors in that window" value="0" />
          <StatRow label="Attempt errors in that window" value="0" />
          <StatRow
            label="Board flags, 1 September"
            value="186 / 394 companies"
          />
          <StatRow
            label="Board flags, 6 September"
            value="3 / 401 companies"
          />
        </tbody>
      </table>
      <p>
        The three flags left are today’s ATS problems — arculus in Germany, bol
        and Channable in the Netherlands — dated 6 September. They are not
        leftover “cannot start a thread” stamps. Successful fetches cleared
        those.
      </p>

      <h2>Did real catalogs finish</h2>
      <p>
        Empty scheduler countries (<code>austria</code>, <code>joblet</code>,{" "}
        <code>mauritius</code>, <code>uae</code>, <code>united-state</code>)
        still fail every cycle with “No catalog.” They failed in August too.
        They are excluded. What remains is whether a country that has a catalog
        completed.
      </p>
      <table>
        <caption>
          Real catalogs only. Collapse is 30–31 August, when every scheduled
          country run failed in about a second. After is the same question
          with the new loop.
        </caption>
        <thead>
          <tr>
            <th scope="col">Window</th>
            <th scope="col">Runs</th>
            <th scope="col">OK</th>
            <th scope="col">New jobs</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Healthy, 20–27 August</th>
            <td>352</td>
            <td>345 (98.0%)</td>
            <td>383</td>
          </tr>
          <tr>
            <th scope="row">Collapse, 30–31 August</th>
            <td>91</td>
            <td>0</td>
            <td>0</td>
          </tr>
          <tr>
            <th scope="row">After, from 3 September 16:09 UTC</th>
            <td>154</td>
            <td>153 (99.4%)</td>
            <td>160</td>
          </tr>
        </tbody>
      </table>
      <p>
        The one miss after the cut is Germany run 3991, 5 September 11:00 UTC:{" "}
        <code>90/111</code> done, exit 1, no duration. A scrape that stopped,
        not <code>can&apos;t start new thread</code>. The next Germany cycle
        was <code>111/111</code> again. New jobs per day are back in the
        pre-outage band, about 37–51, against zero on 30 and 31 August.
      </p>
      <p>
        Completing versus not completing is the same question in all three
        rows. How many seconds Germany took at concurrency 4 versus 2 is not.
      </p>

      <h2>Still true</h2>
      <p>
        Five scheduler countries still have no catalog. Drop them from the
        schedule. One event loop did not invent that, and it did not fix it.
      </p>
      <p>
        Concurrency 2 and one Chromium are RAM knobs on a{" "}
        <code>t4g.micro</code>. They shipped in the same deploy. They are not
        evidence about event-loop speed. Judge the model on whether{" "}
        <code>can&apos;t start new thread</code> returns.
      </p>
    </div>
  );
}
