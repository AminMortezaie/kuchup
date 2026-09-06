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
        On 2 September we stopped starting an OS thread per company. Country
        fetch now runs on one event loop, bounded by{" "}
        <code>asyncio.Semaphore</code>, with production concurrency at{" "}
        <strong>2</strong> instead of 4. The question four days later is not
        whether the code looks cleaner. It is whether the catalog moved.
      </p>
      <p>
        It did. Germany did not get faster. That is the performance result.
      </p>
      <p>
        The outage write-up is{" "}
        <a href="/engineering/cant-start-new-thread">
          can&apos;t start new thread
        </a>
        . This is the after.
      </p>

      <h2>What we counted</h2>
      <p>
        Grafana Cloud on this box is host health: disk, available RAM, a probe
        of <code>/api/health</code>. It does not store per-company fetch
        outcomes. The numbers below are Postgres —{" "}
        <code>fetch_runs</code> and <code>company_fetch_attempts</code> —
        queried on 6 September 2026. That is the same place the outage showed
        up when Docker logs had been wiped.
      </p>
      <p>
        The worker kept recording <code>concurrency = 4</code> through the
        morning of 3 September. The first production run with{" "}
        <code>concurrency = 2</code> is Armenia at{" "}
        <strong>16:09 UTC on 3 September</strong>. That is the after cut. Empty
        scheduler countries (<code>austria</code>, <code>joblet</code>,{" "}
        <code>mauritius</code>, <code>uae</code>, <code>united-state</code>)
        still fail every cycle with “No catalog.” They are excluded from the
        success rates. They were failing before the outage too.
      </p>
      <table>
        <caption>
          Real catalogs only. Healthy window is 20–27 August. Collapse is 30–31
          August. After starts 3 September 16:09 UTC.
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
            <th scope="row">Healthy, concurrency 4, thread pool</th>
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
            <th scope="row">After, concurrency 2, one loop</th>
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
        was <code>111/111</code> again.
      </p>

      <h2>The error that went away</h2>
      <table>
        <caption>
          Company attempts after the concurrency-2 cut, against the outage
          window
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

      <h2>Germany got 27 seconds slower</h2>
      <p>
        In-flight work dropped from four OS threads to two coroutines on a{" "}
        <code>t4g.micro</code>. Large countries take longer. They also finish.
      </p>
      <table>
        <caption>
          Median duration for runs longer than 30 seconds. Healthy window:
          concurrency 4. After: concurrency 2.
        </caption>
        <thead>
          <tr>
            <th scope="col">Country</th>
            <th scope="col">Healthy p50</th>
            <th scope="col">After p50</th>
            <th scope="col">OK after</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Germany (~111 companies)</th>
            <td>103s</td>
            <td>130s</td>
            <td>11 / 12</td>
          </tr>
          <tr>
            <th scope="row">Netherlands (~95 companies)</th>
            <td>111s</td>
            <td>205s</td>
            <td>12 / 12</td>
          </tr>
        </tbody>
      </table>
      <p>
        Germany’s p50 went from 103 seconds to 130. The Netherlands from 111 to
        205. Both still sit well under the 45-minute country join. New jobs per
        day are back in the pre-outage band, about 37–51, against{" "}
        <strong>zero</strong> on 30 and 31 August. The six-hour schedule still
        fits.
      </p>
      <p>
        That is the trade we wanted on this box. Timeouts already bounded how
        long a company may run. They did not bound how many threads and
        browsers existed while it ran. Two companies in flight, one Chromium,
        one loop: the cycle is slower and it returns.
      </p>

      <h2>What Grafana did not tell us</h2>
      <p>
        Alloy ships node and container metrics to Grafana Cloud. That is how we
        watch disk and whether origin answers. Fetch success, duration,{" "}
        <code>new_jobs</code>, and the error string live in Postgres. During
        the outage the board said companies were broken and Grafana had no
        fetch log. Grouping <code>error_message</code> was enough then. It is
        enough now: the thread error is gone, and the remaining red flags are
        three career sites, not the worker.
      </p>

      <h2>Still true</h2>
      <p>
        Five scheduler countries still have no catalog. They fail in about a
        tenth of a second every cycle, same as in August. Drop them from the
        schedule. The concurrency change did not invent that, and it did not
        fix it.
      </p>
      <p>
        One event loop per country. A semaphore for in-flight companies.
        Playwright at one. Judge the next cycle in Postgres, not by whether
        Germany’s wall clock went down.
      </p>
    </div>
  );
}
