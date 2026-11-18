---
name: prodcraft
description: Architecture-aware production review of a codebase or service. Use when the user asks "is this production ready", wants a senior-level code review, security audit, deployment readiness check, or system design review of real code, or asks how ideas from Designing Data-Intensive Applications, Fundamentals of Software Architecture, or Software Architecture - The Hard Parts apply to their code. Produces evidence-backed findings tied to architecture characteristics, ADRs, and runnable fitness functions.
---

# Prodcraft: architecture-aware production review

Most reviews stop at "this line is bad". A senior reviewer goes one step further: *which property of the system does this weaken, what is the trade-off, and how do we stop it coming back?* Prodcraft runs that full loop over five lenses and ends with decisions and automated guards, not a wall of warnings.

## Ground rules

1. **Evidence or it didn't happen.** Every finding cites `path:line` (or a config key, or a command output). If you could not check something, say "not verified" — never guess.
2. **Characteristics, not opinions.** Tag every finding with the architecture characteristic it threatens (see `references/04-architecture-characteristics.md`). A finding that threatens nothing the system cares about is a nit.
3. **Trade-offs, not best practices.** For anything above a nit, state what the current design buys and what it costs. "Use microservices" is never a finding; "this module is shared by two deploy units, so a schema change forces a lockstep release" is.
4. **Fix the first failure, not every symptom.** Cascading issues get one root finding with the symptoms listed under it.
5. **Respect scope.** If the user asks for one lens (e.g. "security only"), run only that lens plus the report.
6. **Don't run destructive or networked commands** (deploys, migrations, `curl | sh`, scanners that upload code). Read-only analysis and local tooling only, and ask before installing anything.

## Workflow

### Step 0 — Inventory (always)
Run the bundled inventory script from the skill directory against the target repo:

```bash
python3 scripts/inventory.py <repo-path>            # human-readable
python3 scripts/inventory.py <repo-path> --json     # machine-readable
```

It reports languages, entry points, dependency manifests, Docker/CI/IaC files, env files, migration folders, test folders, and quick secret-pattern hits. Use it to plan which files to read. Then establish **context** before judging anything — ask or infer:
- What does the system do, who calls it, expected load (requests/s, data volume, read/write ratio)?
- Which 3–5 architecture characteristics matter most here? (If unknown, propose a ranked list and state it as an assumption at the top of the report.)

### Step 1 — Code quality lens
Read `references/01-code-quality.md`. Focus on: correctness hazards, error handling, resource lifecycles, naming and cohesion, dead code, test gaps on critical paths. Human-readable means a new engineer can find the entry point, follow one request end to end, and know where to change behaviour.

### Step 2 — Security lens
Read `references/02-security-audit.md`. Walk the trust boundaries: every input from outside the process, every secret, every authz decision, every outbound call. Map findings to OWASP categories where they apply. Severity follows exploitability × impact, not how scary the code looks.

### Step 3 — Deployment readiness lens
Read `references/03-deployment-readiness.md`. Check config, health checks, graceful shutdown, observability, migrations, rollback, resource limits, dependency pinning, and CI gates.

### Step 4 — Data-intensive systems lens (DDIA ideas)
Read `references/05-data-intensive.md`. Look for the classic distributed-data bugs: non-idempotent retries, dual writes, read-modify-write races, wrong isolation assumptions, unbounded queues, missing backpressure, clock-based ordering, unsafe schema evolution, and replication-lag surprises.

### Step 5 — Architecture lens (Fundamentals + Hard Parts ideas)
Read `references/04-architecture-characteristics.md` and `references/06-hard-parts.md`. Identify the architecture style actually in use (not the one in the README), the quanta (independently deployable units with their own data), coupling between them (static and dynamic), service granularity forces, data ownership, and how distributed workflows are coordinated.

### Step 6 — Decisions and guards
Read `references/07-adrs-and-fitness-functions.md`.
- For every **High/Critical** finding that requires a design choice, draft an ADR (context, options with trade-offs, decision, consequences). Leave the decision as "Proposed" — the team owns it.
- For every finding that could regress, write a **fitness function**: a runnable check (test, lint rule, CI script, architecture test) that fails if the problem returns. Prefer checks that run in the existing CI.

### Step 7 — Report
Use `references/report-template.md` exactly. Write it to `PRODCRAFT_REPORT.md` in the target repo (or reply inline if the user prefers). Order findings by severity, then by blast radius. End with the three highest-leverage changes, not a generic offer.

## Severity scale

| Severity | Meaning |
|---|---|
| Critical | Exploitable now, or data loss/corruption in normal operation. Block release. |
| High | Likely to cause an outage, breach, or data inconsistency under realistic load or failure. Fix before release. |
| Medium | Degrades a key characteristic or makes the next incident harder to diagnose. Plan a fix. |
| Low | Maintainability or clarity cost with no near-term production risk. |
| Nit | Style. Mention only if the user asked for a full review. |

## Lens selection shortcuts

| User says | Run |
|---|---|
| "is this production ready", "pre-launch review", "full review" | All lenses |
| "security audit", "pentest-style review" | 0, 2, 7 |
| "can we deploy this", "deployment checklist" | 0, 3, 7 |
| "review this design", "system design review", "will this scale" | 0, 4, 5, 6, 7 |
| "clean up this code", "code review" | 0, 1, 7 |

## Anti-patterns to avoid in your own output

- A score with no evidence behind it.
- Treating green CI or passing tests as proof of production readiness.
- Recommending a pattern (CQRS, event sourcing, microservices, Kubernetes) without naming the force that justifies it here.
- Rewriting the whole codebase in the suggestions. Prefer the smallest change that removes the risk.
- Quoting the source books at length. Apply the idea to this code in your own words and name the concept so the reader can look it up.
