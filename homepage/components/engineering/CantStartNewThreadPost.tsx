function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
}

export function CantStartNewThreadPost() {
  return (
    <div className="engineering-prose">
      <p>
        On 1 September 2026 the production board showed a fetch problem on most
        companies. It looked like employer career sites, or our scrapers, had
        died. They had not. The EC2 fetch worker could not start OS threads, so
        every six-hour country cycle failed in about a second and stamped a
        sticky “fetch problem” flag on the catalog.
      </p>
      <p>
        The catalog went stale from 30 August onward.{" "}
        <strong>186 of 394</strong> companies were flagged. Germany and the
        Netherlands took most of the hits (85 and 84). Last healthy country
        runs: <strong>29 August 2026</strong>.
      </p>

      <h2>What we saw</h2>
      <p>
        The worker container was still “Up.” The six-hour loop still ran.
        Cycles “finished,” so nothing in the process table looked wedged. The
        board then went red.
      </p>
      <table>
        <caption>Postgres on 1 September 2026, after a week of failures</caption>
        <tbody>
          <StatRow
            label="Attempt errors, last 7 days"
            value="357 / 358 were can't start new thread"
          />
          <StatRow
            label="Latest country cycle"
            value="All failed, exit 1, about 0s duration"
          />
          <StatRow
            label="Germany / Netherlands that cycle"
            value="111/111 and 95/95 “done”, new_jobs = 0"
          />
          <StatRow label="Companies flagged" value="186 / 394" />
          <StatRow
            label="Last successful country fetch"
            value="29 August 2026"
          />
        </tbody>
      </table>
      <p>
        <code>111/111</code> is bookkeeping, not a scrape. The pool dies
        immediately; finalize still sets progress to total. Same-second
        timestamps across countries are sequential scheduling: each country
        dies in under a second, so a 16-country cycle completes in about two
        seconds.
      </p>
      <p>
        First error: 28 August 12:50 UTC. Spike: 29 August 07:00 —{" "}
        <strong>173 errors in one hour</strong>. Every scheduled country run
        from 30 August onward failed in about a second.
      </p>

      <h2>What it was not</h2>
      <p>Three wrong explanations were easy to reach for:</p>
      <ul>
        <li>
          Employer ATS outages. The error string was the same for almost every
          company. Career sites do not fail in lockstep like that.
        </li>
        <li>
          “Python asyncio uses too much RAM.” Coroutines are cheap. OS threads
          (~8&nbsp;MiB stacks) and Chromium are not.
        </li>
        <li>
          A reason to rewrite the worker in Go. HTTP clients would get cheaper.
          The browser fallback would cost the same. The bug was the concurrency
          model, not the language.
        </li>
      </ul>
      <p>
        We run the worker on a <code>t4g.micro</code>. Low RAM is the{" "}
        <em>constraint</em>, not the bug. A bigger box would have delayed the
        same failure.
      </p>

      <h2>Nested threads, nested event loops</h2>
      <p>
        Fetch already runs in a separate container. The code is not a separate
        system: the worker imports the same fetch, scrape, and catalog packages
        as the panel and writes the same Postgres.
      </p>
      <p>The model on 1 September, simplified:</p>
      <pre>
        <code>{`scheduler (one country at a time)
  → OS thread for the country
    → asyncio.run  (event loop #1)
      → ThreadPoolExecutor(max_workers=4)
        → asyncio.run per company  (event loop #2)
          → HTTP to the career board
          → sometimes Playwright Chromium on yet another thread`}</code>
      </pre>
      <p>
        That is thread-per-company with a nested event loop, not a coroutine
        pool. Production default was <code>FETCH_SCHEDULE_CONCURRENCY=4</code>.
        Each of those four workers also sized HTTP limits up to 16.
      </p>
      <p>
        The sequential path (<code>workers &lt;= 1</code>) already did the right
        thing: <code>await</code> each company on the country loop. Concurrency
        4 never used that path. It opened a <code>ThreadPoolExecutor</code> and
        called <code>asyncio.run()</code> again inside each worker.
      </p>
      <pre>
        <code>{`# per company, inside the pool — the bug
async def _inner():
    async with make_fetch_client(concurrency=http_concurrency) as client:
        return await asyncio.wait_for(
            fetch_and_persist_company(...),
            timeout=company_timeout_seconds(),
        )

msg, new_count = asyncio.run(_inner())`}</code>
      </pre>
      <p>
        <code>RuntimeError: can&apos;t start new thread</code> means{" "}
        <code>pthread_create</code> failed — typically <code>ENOMEM</code> or a
        PID/nproc limit. It does not mean “asyncio RAM is uncontrollable.”
      </p>
      <p>
        Some career pages have no JSON API. Those fall through to a sync
        Chromium scrape via <code>asyncio.to_thread</code>. One in-flight
        generic company could be: country thread + pool thread + nested event
        loop + extra thread + a browser. That is the RAM and PID amplifier. It
        is also why the process was already unable to start threads after days
        of cycles. On 1 September the pool died before boards ran, so the
        exception string is the thread error, not a hung browser.
      </p>
      <p>
        A{" "}
        <a href="/engineering/playwright-hung-for-15-hours">July hang</a> had
        already taught us to put timeouts on every blocking
        boundary. Those timeouts do not bound how many OS threads and browsers
        exist. This incident is that next failure mode.
      </p>

      <h2>Why the board said the company was broken</h2>
      <p>
        Any attempt message matching <code> — Error: …</code> set a sticky
        catalog flag. There was no distinction between “this career board
        returned garbage” and “this process cannot create a thread.” Operators
        then debug Greenhouse or Ashby instead of the worker.
      </p>
      <p>
        Runs also looked complete. <code>companies_done == companies_total</code>
        , the scheduler logged a finished cycle, duration was ~0s,{" "}
        <code>new_jobs</code> was 0. The stats table does not show{" "}
        <code>error_message</code>.
      </p>
      <p>
        Application logs in Docker are not an archive: they vanish on{" "}
        <code>docker rm -f</code>. Metrics (disk, RAM, health) did not store
        fetch errors. Durable evidence was Postgres: per-company attempt rows
        and country-run summaries. Grouping <code>error_message</code> was
        enough.
      </p>
      <pre>
        <code>{`SELECT LEFT(error_message, 180), COUNT(*)
FROM company_fetch_attempts
WHERE status = 'error'
GROUP BY 1
ORDER BY 2 DESC;`}</code>
      </pre>

      <h2>What we shipped</h2>
      <p>
        On 2 September, country fetch stopped starting a{" "}
        <code>ThreadPoolExecutor</code> or calling <code>asyncio.run()</code>{" "}
        per company. The outer country thread remains so the scheduler can join
        it. Companies run on that thread’s one event loop, bounded by{" "}
        <code>asyncio.Semaphore</code>, sharing one HTTP client.
      </p>
      <pre>
        <code>{`scheduler (one country at a time)
  → OS thread for the country
    → asyncio.run  (one loop)
      → asyncio.Semaphore(workers)   default 2
        → await fetch_and_persist_company(shared client)
          → HTTP; Playwright capped at 1 browser`}</code>
      </pre>
      <ul>
        <li>
          Default <code>FETCH_SCHEDULE_CONCURRENCY</code> is <strong>2</strong>,
          not 4. Do not raise it on a <code>t4g.micro</code> without watching
          RSS.
        </li>
        <li>
          Infra errors such as <code>can&apos;t start new thread</code> no
          longer set the sticky company flag.
        </li>
        <li>
          A failed run no longer marks progress as fully “done.”
        </li>
      </ul>
      <p>
        We did not rewrite the worker in Go. Fetch is already a separate
        container. Splitting languages without a job contract would duplicate
        the ATS parsers and the scrape suite. A queued job table is still on
        the table; it was not this outage’s fix.
      </p>

      <h2>The rule</h2>
      <p>
        Timeouts bound how long a unit of work may run. They do not bound how
        many threads, event loops, and browsers you create while it runs. On a
        small box, <code>asyncio.run()</code> inside a thread pool is a way to
        spend the process before the timeout ever fires.
      </p>
      <p>
        One event loop per country. A semaphore for in-flight companies.
        Playwright at one. Treat “cannot start a thread” as infrastructure, not
        as a broken employer.
      </p>
    </div>
  );
}
