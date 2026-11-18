# Prodcraft review — order-service (demo)

Date: 2026-11-19 · Lenses run: inventory, code quality, security, deployment readiness, data-intensive, architecture · Commit: n/a (demo)

## Verdict
**Not ready** — blocked by a hard-coded production credential (PC-001), SQL injection (PC-002), a payment path that reports failed charges as paid and can double-charge (PC-004, PC-005), and an IDOR that exposes other customers' orders (PC-003).

## Context and assumptions
- An HTTP API that creates and reads orders, reserves stock, and captures payment through an external provider; a separate billing worker marks orders invoiced. Load is unknown — **assumed** a consumer checkout at tens of orders per second at peak.
- Top characteristics, ranked (assumption): 1. Data integrity (money and stock must be correct) 2. Security 3. Availability 4. Deployability 5. Observability.
- Architecture style found: two deployables (`app/` API, `billing_worker/`) presented as separate services, but they share one database → **one architecture quantum** (a small distributed monolith). Evidence: `billing_worker/worker.py:9-15` writes `orders` directly.
- Not verified: production config, backups/restore, the real authentication provider (`app/auth.py` is a stub that trusts the bearer token as the user's identity).

## Findings summary
| ID | Severity | Lens | Characteristic | Title |
|----|----------|------|----------------|-------|
| PC-001 | Critical | Security | Security | Hard-coded production DB credential and committed `.env` |
| PC-002 | Critical | Security | Security | SQL injection in order search |
| PC-003 | High | Security | Security | IDOR: any user can read any order / search any customer |
| PC-004 | Critical | Code quality | Data integrity | Failed payments are reported as successful |
| PC-005 | High | Data-intensive | Data integrity | Non-idempotent payment retries can double-charge |
| PC-006 | High | Data-intensive | Data integrity | Stock reservation race oversells inventory |
| PC-007 | High | Data-intensive | Data integrity | Dual write: DB commit then in-memory event publish |
| PC-008 | High | Architecture | Deployability / Data integrity | Billing worker writes the order service's private table |
| PC-009 | Medium | Architecture | Maintainability | Magic status string shared across services |
| PC-010 | Medium | Data-intensive | Reliability | Unbounded in-memory event queue |
| PC-011 | Medium | Deployment | Availability | No timeout on payment provider call |
| PC-012 | Medium | Deployment | Availability | Health check always returns 200 |
| PC-013 | Medium | Deployment | Security / Deployability | Container runs as root on an unpinned image and bakes in `.env` |
| PC-014 | Medium | Deployment | Deployability | Unpinned dependencies, no lockfile |
| PC-015 | Medium | Deployment | Maintainability | No tests and no CI pipeline |
| PC-016 | Medium | Architecture | Data integrity | No compensation when payment fails after stock is reserved |

## Findings

### PC-001 [Critical] Hard-coded production credential and committed .env — Security
**Evidence:** `app/db.py:6` assigns `DB_PASSWORD` a literal value; `.env:2` contains `PAYMENT_API_KEY`; inventory flagged both. `Dockerfile:5` (`COPY . .`) also copies `.env` into the image.
**What happens:** anyone with repo or image access holds a working database password and payment API key; rotation requires a code change.
**Fix:** delete both values from source and history, rotate them now, load secrets from the environment/secret manager, add `.env` to `.gitignore` and `.dockerignore`.
**Fitness function:** secret scan (e.g. gitleaks) as a required CI step; inventory's secret check in pre-commit.

### PC-002 [Critical] SQL injection in order search — Security
**Evidence:** `app/db.py:18-20` builds `SELECT ... WHERE customer_name = '{customer_name}'` with an f-string; reachable via `GET /orders?customer_name=` at `app/main.py:28-30`.
**What happens:** an authenticated user (attacker) sends `customer_name=' OR '1'='1` (path) and receives every order in the system (impact).
**Fix:** use a parameter: `conn.execute("SELECT * FROM orders WHERE customer_name = ?", (customer_name,))`.
**Fitness function:** semgrep/ruff rule banning f-strings or `%`/`+` formatting inside `.execute(` calls.

### PC-003 [High] IDOR: orders readable by any user — Security
**Evidence:** `app/main.py:20-25` loads `db.get_order(order_id)` and returns it without checking ownership; `app/main.py:29-30` lets any user search by any customer name.
**What happens:** user A iterates order IDs and reads user B's orders (broken access control, OWASP A01).
**Fix:** scope queries by owner — `WHERE id = ? AND customer_id = ?` — and return 404 (not 403) when the caller is not the owner; restrict search to the caller's own orders unless they have an admin role.
**Fitness function:** API test: user B requesting user A's order gets 404.

### PC-004 [Critical] Failed payments are reported as successful — Data integrity
**Evidence:** `app/payments.py:22-26` swallows every exception (`except Exception` + `logger.info`) and the function **always returns True** after the loop; `app/main.py:46-47` then marks the order PAID.
**What happens:** when the provider rejects a card or is down, the order is marked PAID and fulfilled for free; the only trace is an info-level log.
**Fix:** return `False` (or raise) after the final failed attempt, log at error level with the order id, and mark `PAYMENT_FAILED`.
**Fitness function:** unit test that injects a provider error and asserts the order is not PAID; lint rule banning `except Exception` without re-raise or explicit failure return in `app/payments.py`.

### PC-005 [High] Non-idempotent payment retries can double-charge — Data integrity
**Evidence:** `app/payments.py:14-25` retries `requests.post` up to 3 times with no idempotency key.
**What happens:** the provider charges the card, the response is lost (timeout/network blip), the loop retries and charges again → **double charge**.
**Trade-off:** retries buy resilience to transient errors; without idempotency they convert transient errors into duplicate side effects.
**Fix:** send a stable `Idempotency-Key` derived from the order id on every attempt; store the provider charge id with the order; retry with exponential backoff and jitter.
**Fitness function:** test that two captures with the same key produce one charge (see `references/07`).

### PC-006 [High] Stock reservation race oversells inventory — Data integrity
**Evidence:** `app/inventory.py:8-15` reads `available`, checks it in Python, then writes `available - quantity` — a read-modify-write.
**What happens:** two concurrent orders both read `available = 1`, both pass the check, both write `0` → two units sold, one in stock (lost update / oversell).
**Fix:** make it one atomic statement: `UPDATE stock SET available = available - ? WHERE sku = ? AND available >= ?` and check `rowcount == 1`.
**Fitness function:** concurrency test firing N parallel reservations against stock N-1 and asserting exactly N-1 succeed.

### PC-007 [High] Dual write: DB commit then in-memory publish — Data integrity
**Evidence:** `app/main.py:48-52` commits the status update, then calls `events.publish(...)` separately.
**What happens:** a crash or restart between the commit and the publish (or anytime before the in-memory queue is drained, see PC-010) leaves the order PAID with no `order.created` event; downstream systems never hear about it.
**Fix:** transactional **outbox** — insert the event into an `outbox` table in the same transaction as the order update; a relay publishes and marks rows sent; consumers dedupe by event id.
**Fitness function:** test that kills the process after commit and asserts the event is still delivered after restart; reconciliation job comparing orders vs. events.

### PC-008 [High] Billing worker writes the order service's private table — Deployability / Data integrity
**Evidence:** `billing_worker/worker.py:9-15` opens the order database and runs `UPDATE orders SET status = ...`.
**What happens:** two deployables share one table with no single **data owner**. Any schema change to `orders` forces a lockstep release of both; the worker can overwrite statuses the API just set. They are one architecture quantum pretending to be two (distributed monolith).
**Trade-off:**

| Option | Gains | Costs | Fits this system because… |
|---|---|---|---|
| Billing calls an order-service endpoint | Single owner, validation in one place | Runtime coupling to order API availability | Low call volume; integrity matters most |
| Billing consumes `order.*` events and keeps its own invoice table | Independent deploys and data | Eventual consistency, needs outbox (PC-007) | Best long-term once the outbox exists |
| Merge billing into order service | Simplest consistency | Loses independent scaling/deploys | Reasonable if billing stays tiny |

**Fix:** pick an option via ADR 0001; at minimum stop direct writes.
**Fitness function:** CI check that no module outside `app/` contains SQL touching `orders`.

### PC-009 [Medium] Magic status string shared across services — Maintainability
**Evidence:** `billing_worker/worker.py:15` writes `'INVOICED_V2'`; `app/main.py:40,47` writes `'NEW'`, `'PAID'`, `'PAYMENT_FAILED'` as raw strings.
**What happens:** connascence of meaning across a deploy boundary — both sides must agree on unvalidated strings; a typo silently creates a new status.
**Fix:** a single versioned contract (enum in a shared schema package, or a DB check constraint) owned by the order service.
**Fitness function:** DB `CHECK (status IN (...))` plus a test that every status written is in the enum.

### PC-010 [Medium] Unbounded in-memory event queue — Reliability
**Evidence:** `app/events.py:7` uses `queue.Queue()` with no maxsize and nothing drains it.
**What happens:** events are lost on every restart or deploy, and memory grows without limit under load (no backpressure).
**Fix:** replace with the outbox (PC-007) feeding a durable broker; if a buffer is kept, bound it and reject or block when full.
**Fitness function:** alert on outbox backlog age; test that `publish` persists durably.

### PC-011 [Medium] No timeout on payment provider call — Availability
**Evidence:** `app/payments.py:17-19` calls `requests.post` with no `timeout`.
**What happens:** a slow provider holds every request worker indefinitely; the API stops serving all traffic, not just checkout.
**Fix:** `requests.post(..., timeout=(3, 10))`; add a circuit breaker around the provider.
**Fitness function:** semgrep rule `requests-without-timeout` from `references/07`.

### PC-012 [Medium] Health check always returns 200 — Availability
**Evidence:** `app/main.py:13-16` returns `{"status": "ok"}` unconditionally.
**What happens:** the orchestrator keeps routing traffic to instances whose DB is unreachable; readiness and liveness are indistinguishable.
**Fix:** `/livez` returns 200 if the process is alive; `/readyz` checks a cheap DB query and returns 503 on failure.
**Fitness function:** integration test with the DB stopped asserts `/readyz` returns 503.

### PC-013 [Medium] Container runs as root on an unpinned image — Security / Deployability
**Evidence:** `Dockerfile:3` `FROM python:latest`; no `USER` directive; `Dockerfile:5` copies the whole context including `.env`.
**What happens:** builds are not reproducible (`latest` drifts), a container escape starts as root, and secrets ship inside the image.
**Fix:** pin a slim base by version/digest, multi-stage build, add a non-root `USER`, add `.dockerignore`, and a `HEALTHCHECK` hitting `/readyz`.
**Fitness function:** hadolint in CI.

### PC-014 [Medium] Unpinned dependencies, no lockfile — Deployability
**Evidence:** `requirements.txt` lists `fastapi`, `uvicorn`, `requests` with no versions; inventory found no lockfile.
**What happens:** two builds of the same commit install different versions; a breaking or compromised release ships without review.
**Fix:** pin versions and generate a lockfile (`uv lock` / `pip-compile`); update via reviewed PRs.
**Fitness function:** CI fails if the lockfile is missing or out of date.

### PC-015 [Medium] No tests and no CI pipeline — Maintainability
**Evidence:** inventory found **no test** folders and no CI configuration.
**What happens:** every finding above could be fixed and silently regress; there is no gate before production.
**Fix:** add a CI workflow running lint, type check, tests, secret scan, and the fitness functions listed below; start tests with the money and stock paths.

### PC-016 [Medium] No compensation when payment fails after stock is reserved — Data integrity
**Evidence:** `app/main.py:35-49` reserves stock, inserts the order, then captures payment; on `PAYMENT_FAILED` nothing releases the reserved stock.
**What happens:** every failed payment permanently removes units from sale.
**Trade-off:** this is a small saga (reserve → create → charge). Orchestrating it in one handler is fine at this size, but each step needs a compensating action.
**Fix:** on payment failure, release the reservation in the same code path (or reserve with an expiry and a sweeper job).
**Fitness function:** test that a failed payment leaves `available` unchanged.

## Architecture notes
- **Quanta:** one. `app/` and `billing_worker/` deploy separately but share the `orders` table, so they cannot evolve independently.
- **Data ownership:** `orders` has two writers (API, billing worker) — no owner. `stock` has one writer (API).
- **Workflow coordination:** create-order is a synchronous, orchestrated saga inside one request handler with no compensations (PC-016). Downstream notification is meant to be choreographed via events, but the event path is not durable (PC-007, PC-010).
- **Coupling:** connascence of meaning on status strings across the boundary (PC-009).

## Proposed ADRs
- **ADR 0001: Make the order service the sole owner of `orders`** — addresses PC-008, PC-009. Options and trade-offs as in PC-008's table. Status: Proposed.
- **ADR 0002: Publish domain events through a transactional outbox** — addresses PC-007, PC-010. Options: outbox + relay; CDC from the DB log; keep direct publish (rejected: loses events). Status: Proposed.

## Fitness functions to add
| Guards | Kind | Where it runs | Snippet/command |
|--------|------|---------------|-----------------|
| PC-001 | Secret scan | CI + pre-commit | `gitleaks detect --source .` |
| PC-002 | Static rule | CI | semgrep: no string formatting in `.execute(` |
| PC-003 | API test | CI | user B gets 404 on user A's order |
| PC-004, PC-005 | Unit tests | CI | provider error ⇒ not PAID; same idempotency key ⇒ one charge |
| PC-006 | Concurrency test | CI | N parallel reservations vs stock N-1 |
| PC-008 | Architecture check | CI | no SQL on `orders` outside `app/` |
| PC-011 | Static rule | CI | semgrep `requests-without-timeout` |
| PC-013 | Dockerfile lint | CI | `hadolint Dockerfile` |
| PC-014 | Lockfile check | CI | `uv lock --check` |

## Highest-leverage next steps
1. Rotate and remove the leaked secrets, and parameterise the search query (PC-001, PC-002) — today.
2. Fix the payment path: return failure correctly, add an idempotency key and a timeout (PC-004, PC-005, PC-011) — before any real traffic.
3. Make stock reservation atomic and add the outbox (PC-006, PC-007), then decide ADR 0001 to stop the billing worker's direct writes.
