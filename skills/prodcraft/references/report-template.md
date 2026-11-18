# Report template (use exactly)

```markdown
# Prodcraft review — <repo or service name>

Date: YYYY-MM-DD · Lenses run: <list> · Commit: <short sha if available>

## Verdict
**<Ready | Ready with conditions | Not ready>** — one or two sentences on why, citing the blocking finding IDs.

## Context and assumptions
- What the system does, who calls it, expected load (or "unknown").
- Top characteristics this review optimised for, ranked: 1. … 2. … 3. … (mark as assumption if not confirmed).
- Architecture style found: <style>, quanta: <list>. Evidence: …
- Not verified: <things you could not check, e.g. backups, production config>.

## Findings summary
| ID | Severity | Lens | Characteristic | Title |
|----|----------|------|----------------|-------|
| PC-001 | Critical | Security | Security | … |

## Findings

### PC-001 [Critical] <Title> — <Characteristic>
**Evidence:** `path/to/file.py:42-47` (and/or command output)
**What happens:** concrete failure scenario — inputs/state → wrong outcome.
**Why it matters here:** tie to the ranked characteristics and load.
**Trade-off:** what the current approach buys, what it costs (skip for pure bugs).
**Fix:** smallest change that removes the risk; code sketch if short.
**Fitness function:** the check that stops it coming back.

(repeat, ordered by severity then blast radius)

## Architecture notes
Quanta, coupling map, data ownership, workflow coordination — with trade-off tables for significant choices.

## Proposed ADRs
- ADR NNNN: <title> — addresses PC-00X (full text below or in docs/adr/)

## Fitness functions to add
| Guards | Kind | Where it runs | Snippet/command |
|--------|------|---------------|-----------------|

## Highest-leverage next steps
1. …
2. …
3. …
```
