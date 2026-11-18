# Decisions and guards: ADRs and fitness functions

Findings fade; decisions and automated checks stick. Every High/Critical architectural finding should leave behind an ADR draft, and every finding that can regress should leave behind a fitness function.

## ADR template (Architecture Decision Record)
Save as `docs/adr/NNNN-short-title.md` in the target repo (only if the user asks you to write files; otherwise include in the report).

```markdown
# NNNN. <Decision title in imperative form>

Status: Proposed
Date: YYYY-MM-DD
Related findings: PC-003, PC-007

## Context
What forces are at play (characteristics, load, constraints, team). Facts with evidence, not opinions.

## Options considered
1. <Option A> — gains: … / costs: …
2. <Option B> — gains: … / costs: …
3. Do nothing — gains: … / costs: …

## Decision
<Leave as "To be decided by the team" or state the recommended option and why it fits the top characteristics.>

## Consequences
What becomes easier, what becomes harder, what we must now monitor. Link the fitness functions that guard this decision.
```

## Fitness functions
An objective, automatable check that a characteristic still holds. Prefer the cheapest check that would have caught the finding, running in CI the repo already has.

| Kind | Example |
|---|---|
| Unit/integration test | Retry the same request twice with the same idempotency key → one charge |
| Architecture test | Module `domain/` must not import from `web/` or `db/` (import-linter for Python, ArchUnit for JVM, dependency-cruiser for JS/TS, `go list` + script for Go) |
| Static rule | Ban `subprocess(..., shell=True)`, `verify=False`, bare `except:` in given paths (ruff/semgrep/eslint rules) |
| Config check | Every outbound HTTP client is constructed with a timeout (grep/semgrep rule) |
| Migration check | CI fails on `DROP COLUMN` in the same release as code that stopped using it (script over migration diff) |
| Runtime/ops | Alert when consumer lag > N minutes; synthetic check on readiness endpoint |
| Performance | p95 latency budget asserted in a load test for the checkout endpoint |
| Dependency | Lockfile present and up to date; no dependency cycles between packages |

### Ready-made snippets

**Python layering (import-linter, `.importlinter`):**
```ini
[importlinter]
root_package = app

[importlinter:contract:layers]
name = Domain does not depend on web or persistence
type = forbidden
source_modules = app.domain
forbidden_modules = app.web
    app.db
```

**Semgrep: outbound requests must set a timeout (Python):**
```yaml
rules:
  - id: requests-without-timeout
    languages: [python]
    severity: ERROR
    message: Outbound HTTP call without timeout
    patterns:
      - pattern-either:
          - pattern: requests.$M(...)
      - pattern-not: requests.$M(..., timeout=$T, ...)
      - metavariable-regex:
          metavariable: $M
          regex: ^(get|post|put|patch|delete|head|request)$
```

**Idempotency test shape (pytest):**
```python
def test_create_payment_is_idempotent(client):
    headers = {"Idempotency-Key": "abc-123"}
    r1 = client.post("/payments", json={"order_id": 1, "amount": 500}, headers=headers)
    r2 = client.post("/payments", json={"order_id": 1, "amount": 500}, headers=headers)
    assert r1.json() == r2.json()
    assert count_charges(order_id=1) == 1
```

**GitHub Actions job to run guards:**
```yaml
  architecture-guards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install import-linter semgrep
      - run: lint-imports
      - run: semgrep --config .semgrep/ --error
```

Adapt to the repo's language and existing CI; don't introduce a new CI system.
