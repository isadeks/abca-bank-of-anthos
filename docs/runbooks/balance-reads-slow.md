# Runbook: `abca-boa-balance-reads-slow`

The CloudWatch alarm `abca-boa-balance-reads-slow` fires when balance reads in
production (namespace `boa`) are slow. Balance reads are what the home page does
to show the account balance, so users see a slow or hanging home page.

> **Verify against the alarm definition.** The alarm itself is not defined in
> this repository. The metric, threshold and period below are what to expect;
> open the alarm in the CloudWatch console (Alarms, then `abca-boa-balance-reads-slow`,
> Details) and correct this page if it differs.

## 1. What it measures

- **Path:** `frontend` calls `balancereader` `GET /balances/{accountId}`
  (`src/ledger/balancereader`). That call is the "balance read".
- **Signal:** latency of those reads (the `balancereader` HTTP server latency
  for `/balances/{accountId}`), exported over OTLP by the Java service and
  stored in CloudWatch namespace `BankOfAnthos`. The alarm is on the slow tail
  (p95/p99 or average, see the alarm details), not on errors.
- **Normal behaviour:** a read is answered from an in-memory Guava cache
  (`BalanceCache`, `CACHE_SIZE` default 1,000,000 accounts). A background
  `LedgerReader` thread polls `ledger-db` every `POLL_MS` (100 ms) and adjusts
  cached balances as new transactions arrive. Only a **cache miss** touches the
  database, with one aggregate query (`TransactionRepository.findBalance`) that
  uses the `(TO_ACCT, TO_ROUTE, TIMESTAMP)` / `(FROM_ACCT, FROM_ROUTE, TIMESTAMP)`
  indexes. So a healthy read is a few milliseconds and does no database work.
- **Impact:** slow home page and slow post-deposit/transfer reloads. Writes
  (`ledgerwriter`) are separate and should still work; confirm in step 2.

## 2. First five minutes

1. Open the alarm and check the graph: is it a step change (a deploy or a
   restart) or a slow climb (ledger growth, load)?
2. Is it only the balance read? Compare with `transactionhistory` and
   `ledgerwriter` latency for the same period. All three slow at once points at
   `ledger-db` or the node; only `balancereader` points at the service or its cache.
3. Check the pods (cluster access to the `boa` namespace):

   ```bash
   kubectl -n boa get pods -l app=balancereader        # restarts, readiness
   kubectl -n boa top pod -l app=balancereader         # CPU limit is 1000m, memory 512Mi
   kubectl -n boa logs deploy/balancereader --tail=200 # "Cache error", "Could not reach ledger database"
   kubectl -n boa get deploy balancereader -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
   ```

4. Was there a release? Merging to `main` releases to production, so look at
   recent merges (`git log --oneline -10 -- src/ledger/balancereader`) and the
   time of the last deploy against the start of the alarm. A slowdown that begins
   at a deploy is a rollback candidate (section 5).

## 3. Find the slow traces in X-Ray

Every service exports traces over OTLP to the collector, which forwards them to
AWS X-Ray. Spans carry the resource attribute `k8s.namespace.name`, so
production (`boa`) can be told apart from PR previews (`pr-<N>`).

1. AWS console, CloudWatch, **X-Ray traces** (Traces), set the time range to
   cover the alarm.
2. Filter on production and the slow service, for example with a filter
   expression like:

   ```
   service("balancereader") AND responsetime > 1
   ```

   and add `k8s.namespace.name = "boa"` as a resource attribute filter (as in
   [deploy/eks/README.md](/deploy/eks/README.md#checking-telemetry)). Adjust the
   `responsetime` threshold (seconds) to the alarm's threshold. If your account
   cannot filter by that attribute, filter by trace group or service and check
   the namespace on the trace.
3. Open a slow trace. The trace is `frontend` then `balancereader`, with the
   same trace id across services (W3C `traceparent`). Look at where the time goes:

   | What you see | Meaning |
   |---|---|
   | Time inside `balancereader`, with a database child span / long gap | Cache miss or an expensive query: sections 4.1 to 4.3 |
   | Time inside `balancereader` with no database span | CPU or GC pressure, or thread starvation in the pod |
   | Time in `frontend` before it calls `balancereader` | Not the balance reader: look at the frontend and the node |
   | Gap between `frontend` and `balancereader` spans | Network, DNS, or the pod being throttled or restarting |

4. Compare one slow trace with a fast one from before the alarm. The difference
   (a database span that was not there, or one that got longer) usually names the cause.
5. For a pattern across traces, open the service map for `balancereader`
   and the slowest-traces list sorted by response time.

## 4. Likely causes

### 4.1 Cache bypass (most likely after a code change)

Reads are only fast if they hit the cache. Anything that drops entries or
reloads from the ledger on each read makes every read a database query.

- **Seen before:** PR #17 invalidated the account's cache entry on every read
  and rebuilt the balance by scanning the whole ledger (`findLatest(0)`). Each
  read became O(ledger size). It was reverted in PR #18 (DEM-224).
- **Signs:** every slow trace has a database span; the Guava cache metrics
  (`cache.gets` with `result=miss`, `cache.load`, exported with the name `Guava`)
  show a high miss rate or constant loads; database CPU rises with request rate.
  Debug log line "Cache loaded from db" appears on every request (needs
  `LOG_LEVEL=debug`).
- **Look for in the code:** `cache.invalidate*`, `cache.refresh`, a
  `maximumSize`/`CACHE_SIZE` that is too small, or anything in
  `BalanceReaderController.getBalance` that bypasses `cache.get`.
- **Also check:** pod restarts. A restart empties the cache, and all accounts
  then miss once. A crash loop (OOM at 512Mi, failing liveness) keeps it cold.
- **Fix:** roll back (section 5), then fix forward in a PR. Reads must go
  through the cache that the ledger poller keeps current.

### 4.2 Ledger growth

`findBalance` sums every transaction of an account, so a miss costs more as the
ledger grows, and `findLatest`/`MAX(transactionId)` run on every poll.

- **Signs:** a slow climb rather than a step; only misses are slow; the query
  appears in `ledger-db` slow logs or Performance Insights if enabled.
- **Check:** row count of `TRANSACTIONS` and the per-account count for hot
  accounts (for example a load generator account that deposits constantly);
  confirm the indexes still exist (`\d transactions` in `psql`); check the
  load generator volume and recent changes to it.
- **Fix:** short term, make sure the cache is warm and large enough; if the
  load generator is flooding the ledger, scale it down
  (`kubectl -n boa scale deploy/loadgenerator --replicas=0`). Longer term, a
  balance snapshot or rollup table. Do not delete ledger rows.

### 4.3 Database (`ledger-db`)

- **Signs:** `transactionhistory` and `ledgerwriter` are slow too; balancereader
  logs "Could not reach ledger database" or "Could not contact ledger database";
  the poller is behind, so balances are stale as well as slow.
- **Check:**

  ```bash
  kubectl -n boa get pods ledger-db-0               # restarts, readiness
  kubectl -n boa top pod ledger-db-0
  kubectl -n boa exec ledger-db-0 -- psql -U <user> -d postgresdb \
    -c "select pid, state, now()-query_start as age, left(query,80) from pg_stat_activity order by age desc limit 10;"
  ```

  Look for long-running queries, locks, and connection exhaustion. Check the
  node and the volume (disk full, I/O throttling).
- **Note:** if the poller thread dies ("Remote transaction id out of sync"),
  `/healthy` returns 500 and the pod is restarted by the liveness probe,
  which also empties the cache.
- **Fix:** kill a runaway query (`select pg_cancel_backend(<pid>)`); restart
  the database pod only as a last resort and after telling the escalation
  contact (it is a single StatefulSet pod with the ledger on it).

### 4.4 Other

- **Pod resources:** CPU throttling at the 1000m limit or GC at the 512Mi
  limit (`-Xmx512m`). Look at `kubectl top` and restarts.
- **Telemetry itself:** exporting to a slow collector should not block
  requests, but check `otel-collector` in the `observability` namespace if
  traces are missing for the period.

## 5. Roll back a release

Merging to `main` releases to production; CI builds the changed services,
deploys, smoke-tests and rolls back automatically on failure. A slow-but-working
release passes the smoke test, so a manual rollback may be needed.

Choose the quickest option that is safe:

1. **Immediate mitigation: revert the deployment** (seconds, no CI):

   ```bash
   kubectl -n boa rollout history deploy/balancereader
   kubectl -n boa rollout undo deploy/balancereader            # previous revision
   # or a specific one:
   kubectl -n boa rollout undo deploy/balancereader --to-revision=<N>
   kubectl -n boa rollout status deploy/balancereader
   ```

   Check that the image is the one you expect (command in section 2) and that
   latency recovers in X-Ray and on the alarm graph. Only `balancereader` is
   affected unless the release changed other services; roll those back the same way.

   This is a stopgap: the next release from `main` will deploy the bad code
   again, so do the next step straight away.

2. **Make it permanent: revert the change on `main`.** Revert the offending
   PR (`git revert <merge-sha>`, or the GitHub "Revert" button), open a PR
   (title like `revert: ... (DEM-xxx)`), get it merged. That triggers a normal
   production release of the previous code. For a one-service change, only
   that service is rebuilt. Revert PRs for source changes still need a test
   change to satisfy `abca-boa/tests`; adding a regression test is the right fix.
3. **Pin an image by hand** (when the deploy history is no use): from a
   checkout, `REGISTRY=... BOA_ALLOW_CIDRS=... deploy/eks/apply.sh boa balancereader=<good-tag>`
   (see [deploy/eks/README.md](/deploy/eks/README.md)). Use the tag of the last good
   release image from the registry (`<REGISTRY>/abca-boa/balancereader`).

After a rollback:

- Wait for the alarm to return to OK (allow a few evaluation periods).
- Log in as `testuser` / `bankofanthos` and check the home page balance loads
  quickly and a deposit changes the balance.
- Do not roll back `ledger-db` (data, not code). Do not restore it from a
  backup for a latency problem.

## 6. Escalate

Escalate when the alarm has not cleared 30 minutes after you started, when a
rollback did not help, when the cause looks like `ledger-db` (data risk), or
when balances are wrong rather than only slow.

| Who | When |
|---|---|
| Ledger team (owners of `balancereader`, `ledgerwriter`, `transactionhistory`, `ledger-db`; manifests are labelled `team: ledger`) | First escalation: cache, query or ledger behaviour |
| Repo maintainers (`@GoogleCloudPlatform/devrel-flagship-app-maintainers`, see `.github/CODEOWNERS`) | Release or rollback questions, approvals to merge a revert |
| Platform/infra on-call for the EKS cluster and AWS account | Node, volume, collector or X-Ray problems |

> **To fill in:** the repository does not record paging contacts. Replace this
> note with the on-call rotation or channel names for the ledger team and
> platform on-call.

When you escalate, include: the alarm time, what changed (last release time
and image), the slow-trace ids you looked at, what you checked in section 4,
and what you already tried (including any `rollout undo`).

## 7. After the incident

- Record the timeline, root cause and the fix in the Linear issue.
- If a cache-bypass or O(ledger size) read made it to production, add a
  regression test or a latency/DB-call-count guard on the balance read.
- Update this runbook with anything that was wrong or missing.
