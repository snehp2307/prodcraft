# prodcraft

[![ci](https://github.com/snehp2307/prodcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/snehp2307/prodcraft/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Planted bugs caught](https://img.shields.io/badge/demo%20eval-16%2F16%20planted%20bugs-brightgreen)](evals/)
[![Claude Skill](https://img.shields.io/badge/Claude-Skill-d97757)](skills/prodcraft/SKILL.md)
[![Release](https://img.shields.io/github/v/release/snehp2307/prodcraft?include_prereleases)](https://github.com/snehp2307/prodcraft/releases)

**A Claude skill that reviews code the way a staff engineer does: clean code, security, deployment readiness, and system design — tied together.**

Most AI code reviews stop at *"this line is bad."* prodcraft keeps going:

> *Which property of the system does this weaken? What's the trade-off? What decision should we record — and what automated check stops it from coming back?*

It applies ideas from three books every backend engineer should know — *Designing Data-Intensive Applications*, *Fundamentals of Software Architecture*, and *Software Architecture: The Hard Parts* — **to your actual code**, with `file:line` evidence for every finding.

---

## What you get

Point it at a repo and ask *"is this production ready?"*. You get a `PRODCRAFT_REPORT.md` with:

- **A verdict** — Ready / Ready with conditions / Not ready — and the findings that block it.
- **Findings ranked by severity**, each with evidence, a concrete failure scenario, the **architecture characteristic** it threatens (availability, data integrity, security…), the trade-off, and the smallest fix.
- **Architecture notes** — the style you *actually* have (not the one in your README), the deployable quanta, data ownership, and how distributed workflows are coordinated.
- **ADR drafts** for decisions the team needs to make, with options and trade-off tables.
- **Fitness functions** — runnable checks (tests, semgrep/lint rules, import-layer rules, CI jobs) so each fixed issue can't silently return.

## Five lenses in one pass

| Lens | Catches things like |
|---|---|
| **Code quality** | swallowed errors, partial failures, resource leaks, god modules, untested critical paths |
| **Security** | injection (incl. LLM output), IDOR, secrets in code/images, disabled TLS, unsigned webhooks, SSRF — mapped to OWASP |
| **Deployment readiness** | missing timeouts, fake health checks, no graceful shutdown, unsafe migrations, root containers, unpinned deps |
| **Data-intensive systems** *(DDIA ideas)* | non-idempotent retries, dual writes, read-modify-write races, write skew, replication lag, unbounded queues, unsafe schema evolution |
| **Architecture** *(Fundamentals + Hard Parts ideas)* | distributed monoliths, shared-database coupling, connascence across boundaries, granularity forces, sagas without compensations, leaky contracts |

## See it work

[`examples/order-service`](examples/order-service) is a small FastAPI service with **16 planted production bugs** — from a hard-coded password to a stock-reservation race to a billing worker writing another service's table. Here is the review prodcraft's workflow produces: **[examples/order-service/PRODCRAFT_REPORT.md](examples/order-service/PRODCRAFT_REPORT.md)**.

A taste:

> **PC-005 [High] Non-idempotent payment retries can double-charge — Data integrity**
> **Evidence:** `app/payments.py:14-25` retries `requests.post` up to 3 times with no idempotency key.
> **What happens:** the provider charges the card, the response is lost, the loop retries and charges again.
> **Trade-off:** retries buy resilience to transient errors; without idempotency they convert transient errors into duplicate side effects.
> **Fitness function:** test that two captures with the same key produce one charge.

> **PC-008 [High] Billing worker writes the order service's private table**
> Two deployables share one table with no single data owner… they are one architecture quantum pretending to be two (distributed monolith). *(followed by a 3-option trade-off table and an ADR)*

## It's evaluated, not vibes

`evals/` holds ground truth for every planted bug and a grader that scores any report:

```bash
python3 evals/grade_report.py examples/order-service/PRODCRAFT_REPORT.md --min-recall 0.9
# {"recall": 1.0, "missed": [], "sections_missing": [], "verdict_ok": true}
```

Run the skill yourself on the demo, grade your report, and open an issue with your score and model. A shallow "looks good to me" review scores 0.

## Install

**Claude Code** (personal, all projects):
```bash
git clone https://github.com/snehp2307/prodcraft.git
mkdir -p ~/.claude/skills
cp -r prodcraft/skills/prodcraft ~/.claude/skills/prodcraft
```
Or per project: copy `skills/prodcraft` into `<your-repo>/.claude/skills/prodcraft`.

**Claude apps (claude.ai / desktop):** zip the `skills/prodcraft` folder and upload it under Settings → Capabilities → Skills.

## Use

Just ask in plain language:

- *"Is this repo production ready?"* → all lenses
- *"Security audit this service"* → inventory + security + report
- *"Can we deploy this? Give me a deployment checklist"* → deployment lens
- *"Review the system design of these services — will it scale?"* → data + architecture lenses
- *"How would DDIA's ideas apply to our payment flow?"*

The bundled inventory script also works on its own (stdlib only, read-only, no network):

```bash
python3 ~/.claude/skills/prodcraft/scripts/inventory.py path/to/repo          # human-readable
python3 ~/.claude/skills/prodcraft/scripts/inventory.py path/to/repo --json   # for tooling
```

It reports languages, entry points, manifests and lockfiles, Docker/CI/IaC files, env files, migrations, test folders, and masked secret candidates.

## Repo layout

```
skills/prodcraft/
  SKILL.md                         workflow, ground rules, severity scale
  scripts/inventory.py             read-only repo inventory + secret candidates
  references/
    01-code-quality.md
    02-security-audit.md
    03-deployment-readiness.md
    04-architecture-characteristics.md   characteristics, quanta, connascence, modularity
    05-data-intensive.md                 12 distributed-data bug patterns and fixes
    06-hard-parts.md                     granularity forces, data ownership, sagas, contracts
    07-adrs-and-fitness-functions.md     ADR template + ready-to-use guard snippets
    report-template.md
examples/order-service/            demo with 16 planted bugs + sample report
evals/                             ground truth + grader
```

## Design principles

1. **Evidence or it didn't happen** — every finding cites `file:line` or command output; unchecked things are marked *not verified*.
2. **Characteristics, not opinions** — every finding names the property it threatens.
3. **Trade-offs, not best practices** — no "use microservices" without the forces that justify it.
4. **Leave guards behind** — ADRs and fitness functions, not just a list.
5. **Read-only and local** — no deploys, migrations, or uploading your code to scanners.

## Contributing

Wanted: more planted-bug demos in other stacks (Node/TypeScript, Go, Java/Spring), new bug patterns for the references, and eval results across models. Each new pattern should come with a fitness-function snippet and a planted example.

## Credits

The architecture and data-systems lenses are inspired by:
- Martin Kleppmann, *Designing Data-Intensive Applications*
- Mark Richards & Neal Ford, *Fundamentals of Software Architecture*
- Neal Ford, Mark Richards, Pramod Sadalage & Zhamak Dehghani, *Software Architecture: The Hard Parts*

The references restate ideas in original words as review checklists; they don't reproduce the books. This project isn't affiliated with the authors or publishers — read the books, they're worth it.

## License

MIT © Sneh Patel
