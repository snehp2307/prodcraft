# Lens 3 — Deployment readiness

Question to answer: *if we deploy this today and it misbehaves at 3 a.m., will we notice, understand it, and get back to safety quickly without losing data?*

## Checklist

### Configuration
- All environment-specific values come from env/config, not code. One build artifact promotes across environments.
- Startup **fails fast** with a clear message if required config is missing (no silent defaults for DB URLs, secrets, or feature-critical flags).
- Secrets come from a secret manager or injected env, never baked into images.

### Health and lifecycle
- Separate **liveness** (process is not wedged) and **readiness** (can serve traffic: DB reachable, migrations applied) checks. Readiness must not be a constant `200 OK`.
- **Graceful shutdown:** handles SIGTERM, stops accepting new work, drains in-flight requests/messages within a deadline, closes pools.
- Startup does not run long jobs that block readiness indefinitely.

### Resilience at the edges
- Every outbound network call has a **timeout**. No timeout = a slow dependency becomes your outage.
- Retries use **exponential backoff with jitter** and a cap, and only on idempotent operations or with idempotency keys (see lens 4).
- Circuit breaker or bulkhead around flaky dependencies on the critical path.
- Connection pools sized and bounded; queues and in-memory buffers bounded.

### Observability
- Structured logs with a request/correlation ID propagated across service and queue hops.
- Metrics for the four golden signals: latency, traffic, errors, saturation — per endpoint/consumer.
- Traces across service boundaries if more than one service is involved.
- Alerts on symptoms users feel (error rate, latency SLO burn), not only on CPU.

### Data and migrations
- Migrations are versioned, run as a separate step (not on every pod start racing each other), and are **backward compatible** with the previous app version (expand → migrate → contract).
- Destructive migrations (drop column/table) are split from the deploy that stops using them.
- Backups exist, and a restore has been tested (ask; "not verified" if unknown).

### Release safety
- Rollback path is documented and does not require a data migration reversal.
- Feature flags or staged rollout for risky changes.
- CI gates: build, lint, typecheck, tests, dependency/secret scan run on every PR; main is protected.
- Dependencies pinned via lockfile; base images pinned (ideally by digest).

### Containers / runtime (if present)
- Non-root user, minimal base image, multi-stage build, no build tools in the final image.
- CPU/memory requests and limits set (Kubernetes) or equivalent.
- `.dockerignore` excludes `.git`, `.env`, local data.

### Capacity
- Known load parameters (peak requests/s, payload sizes, data growth) and at least a rough load test or back-of-envelope estimate for the bottleneck resource.

## Readiness verdict
End this lens with one of: **Ready**, **Ready with conditions** (list them), or **Not ready** (list blockers). Base the verdict only on Critical/High findings from all lenses.
