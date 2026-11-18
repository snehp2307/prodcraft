# Lens 1 — Code quality: human-readable, clean, not broken

Goal: a new engineer can find the entry point, trace one request end to end, and know where to change behaviour — and the code does what it claims under failure, not just on the happy path.

## Check in this order (correctness first, style last)

### 1. Correctness hazards
- Unhandled error paths: swallowed exceptions (`except: pass`, empty `catch {}`), errors logged and then ignored, `Result`/`err` values discarded.
- Partial failure: a function that does A then B where B can fail, leaving A done and nobody compensating.
- Resource lifecycles: files, sockets, DB connections, locks, goroutines/threads opened without guaranteed release (`with`, `defer`, `try/finally`, `using`).
- Concurrency: shared mutable state without synchronisation; check-then-act on shared state; async code that blocks the event loop (sync I/O inside `async def`).
- Time and money: floats for currency, naive datetimes, local-time comparisons, timezone-less timestamps stored in the DB.
- Boundary conditions: empty collections, pagination off-by-one, integer overflow on counters/IDs, unbounded input sizes.
- Mutable default arguments (Python), shadowed variables, implicit type coercion bugs (JS `==`).

### 2. Structure and cohesion
- Functions over ~50 lines or with more than one reason to change. Name the reasons.
- God modules (`utils.py`, `helpers.ts`, `common/`) that everything imports — a coupling magnet.
- Business rules buried in controllers/handlers or SQL strings instead of a domain layer that can be tested alone.
- Layering violations: UI/handler code reaching straight into persistence, or domain code importing framework types.
- Duplication that encodes the same rule twice (risk: they drift). Duplication of incidental code is fine.

### 3. Readability
- Names say *what and why*, not *how* (`retry_payment_capture` > `do_loop2`).
- Magic numbers/strings → named constants with units in the name (`TIMEOUT_SECONDS = 5`).
- Comments explain *why* a non-obvious choice was made; delete comments that restate the code.
- Consistent error and logging style across the codebase.
- Dead code: unreachable branches, unused exports, commented-out blocks, stale feature flags.

### 4. Tests on what matters
- Is the critical path (money movement, auth, data writes) covered by a test that would fail if it broke?
- Are failure paths tested (timeouts, duplicates, partial failures), or only happy paths?
- Do tests depend on wall-clock time, network, or ordering in ways that make them flaky?
- Mocks that assert implementation details rather than behaviour (brittle to refactors).

## How to write a code-quality finding

```
[High] Payment capture error is swallowed — Reliability
Evidence: src/payments/capture.py:42-47 — `except Exception: logger.info(...)` then returns success.
Why it matters: the caller marks the order PAID even when the provider rejected the charge; you will ship goods for free and only find out at reconciliation.
Fix: let the exception propagate (or return an explicit failure), and mark the order PAYMENT_FAILED. Add a test that injects a provider error and asserts the order state.
Fitness function: unit test `test_capture_failure_does_not_mark_paid`; lint rule banning bare `except Exception` without re-raise in src/payments/.
```

## Tooling you may run (local, read-only)
Use what the repo already has before suggesting new tools: its linter config, type checker, and test runner. Examples: `ruff check`, `mypy`, `eslint`, `tsc --noEmit`, `go vet`, `cargo clippy`, the repo's test command. Report the command and its summarised output as evidence. Never auto-fix during a review unless asked.
