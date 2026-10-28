# Monitoring EduSekai

Three free tools answer three questions: *what broke and where* (Sentry), *is it down* (an uptime
monitor), and *was the server out of CPU, memory or disk* (Netdata).

## 1. Errors and slow endpoints: Sentry

1. Create a Sentry account and a **Django** project. Copy its DSN.
2. Add to the backend `.env` (never commit it):

   ```
   SENTRY_DSN=https://...ingest.sentry.io/...
   SENTRY_TRACES_SAMPLE_RATE=0.05   # time 5% of requests; raise it on staging, lower it if you hit the plan limit
   SENTRY_RELEASE=                  # optional: the git commit being deployed
   EDUSEKAI_ENV=production          # shown as the Sentry environment
   ```

3. Restart the backend, worker and beat. Without `SENTRY_DSN` nothing is sent.

What is sent (see `backend/config/monitoring.py`):

- the error, its stack trace, the URL and the **school** (schema name) as the `school` tag;
- timings of sampled requests, including SQL query durations; Sentry flags repeated (N+1) queries.

What is **never** sent: request bodies (passwords, student records, payments), cookies, auth headers,
the user's identity, and any variable whose name looks secret (password, token, key, ...). This matters
because the data is about children: keep it that way. If the school requires data to stay in India,
self-host Sentry or GlitchTip instead of using the cloud service.

Free plans have monthly limits on errors and timed requests, and the limits change; check the current
plan. At 10,000 members, 5% sampling is a sensible start.

## 2. Is it down? Uptime monitor

Use UptimeRobot or Better Stack (cloud, free tier), or Uptime Kuma (self-hosted, free). Add:

| Monitor | URL | Expect |
|---|---|---|
| Backend | `https://<public domain>/api/health/` | HTTP 200 |
| A school | `https://<school>.<domain>/api/health/` | HTTP 200 |
| Dashboard | `https://<school>.<domain>/login` | HTTP 200 |

`/api/health/` answers 200 when the database and cache respond and 503 when either does not. It needs
no login and returns no data. The host name must be a registered school or the public domain; any other
host gets 404 before the check runs.

## 3. Server resources: Netdata

On the server: `wget -O /tmp/netdata-kickstart.sh https://get.netdata.cloud/kickstart.sh && sh /tmp/netdata-kickstart.sh`
(read the script first). It shows CPU, memory, disk, PostgreSQL connections and Redis, second by second,
and can alert when memory or disk is nearly full.

## Local query debugging

The query-count tests (`backend/core/tests_query_counts.py`) catch N+1 queries before deploy. For
digging into one request locally, django-debug-toolbar or Silk are fine **on your own machine only**:
they store request contents, including passwords, and must never run on staging or production.
