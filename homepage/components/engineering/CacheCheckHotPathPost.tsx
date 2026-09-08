export function CacheCheckHotPathPost() {
  return (
    <div className="engineering-prose">
      <p>
        Ten days after we cached country labels, the board went from ~1.7s back
        to unusable. The trigger was a reasonable feature: countries added
        through MCP should show up in the panel without a restart. The panel
        and the MCP server are separate processes. A process-local cache does
        not see another process’s write.
      </p>
      <p>
        We made the cache generation-aware. On every read it asked Redis
        whether the generation had moved. That check ran inside{" "}
        <code>country_label()</code>, which runs per company on every board
        load. Same shape as{" "}
        <a href="/engineering/678-postgres-round-trips">
          678 Postgres round-trips
        </a>
        . Redis instead of Postgres.
      </p>

      <h2>What we saw</h2>
      <p>
        With Redis on (the real deploy), overview and preview climbed into
        seconds. With Redis unset, nothing happened. Tests were green. The
        expensive branch was invisible in the environments where we looked.
      </p>
      <table>
        <caption>Warm paths, EC2 Postgres + Redis</caption>
        <thead>
          <tr>
            <th scope="col">Endpoint</th>
            <th scope="col">Broken</th>
            <th scope="col">After</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">
              <code>country_label()</code> in the board loop
            </th>
            <td>2 Redis round-trips × N companies</td>
            <td>in-memory, 0 I/O</td>
          </tr>
          <tr>
            <th scope="row">Public overview</th>
            <td>seconds, climbing</td>
            <td>~1.35s</td>
          </tr>
          <tr>
            <th scope="row">Public preview, limit 50</th>
            <td>seconds, climbing</td>
            <td>~1.6s</td>
          </tr>
        </tbody>
      </table>
      <p>
        Board back to <strong>~1.3–1.7s</strong>. Cross-process propagation
        lags at most 5 seconds.
      </p>

      <h2>A cache hit that was not a hit</h2>
      <p>
        Postgres stays the source of truth. Writes also bump a Redis generation
        counter. Any process can reload when the counter moves. That design is
        fine. The read side was not:
      </p>
      <pre>
        <code>{`# ran on every all_country_labels() / country_label() call
def _countries_generation_is_current() -> bool:
    if not countries_use_redis():        # Redis PING
        return True
    current = get_countries_generation() # Redis GET
    return _countries_cache_generation == current`}</code>
      </pre>
      <p>
        Two round-trips on every “hit.” For ~100 companies that is hundreds of
        PINGs and GETs per board load. The in-memory cache from the previous
        incident was still there. It never got to matter.
      </p>
      <p>
        <code>if not countries_use_redis(): return True</code> short-circuits
        when <code>REDIS_URL</code> is unset. Local dev and the unit tests took
        that path. Production did not.
      </p>

      <h2>What we shipped</h2>
      <p>
        Cross-process propagation does not need to be instantaneous. A new
        country appearing a few seconds later is acceptable. Throttle the Redis
        check to at most once every 5 seconds. Every other call compares an
        in-memory timestamp and returns. Local writes still clear the cache
        immediately. Other processes converge within 5s.
      </p>
      <pre>
        <code>{`if now - _checked_at < 5.0:
    return True   # hot path: zero I/O`}</code>
      </pre>
      <p>
        The test that would have caught it is not “does the new country show
        up.” That passes with the bug. The test is: 500 calls to{" "}
        <code>country_label()</code> inside the TTL cause <strong>zero</strong>{" "}
        extra Redis reads.
      </p>

      <h2>The rule</h2>
      <p>
        A cache read that does I/O is not a cache. If a path behaves differently
        with Redis on, test it with Redis on. Instant cross-process consistency
        is a product choice. Here it was not worth a per-call network round
        trip. Five seconds of staleness removed the entire problem.
      </p>
    </div>
  );
}
