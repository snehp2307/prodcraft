# Architecture characteristics, styles, and coupling

Concepts drawn from *Fundamentals of Software Architecture* (Richards & Ford), written here in our own words as working tools for code review. Read the book for the full treatment.

## 1. Architecture characteristics ("-ilities")
These are the properties the system must have beyond its features. Tag every finding with one.

| Characteristic | What to look for in code |
|---|---|
| Availability | Single points of failure, missing timeouts/retries, no health checks, synchronous chains of calls |
| Reliability / data integrity | Lost writes, partial failures, non-idempotent retries, missing transactions |
| Scalability | Per-request work that grows with total data, in-memory state that prevents horizontal scaling, hot partitions |
| Elasticity | Slow startup, sticky sessions, state pinned to an instance |
| Performance | N+1 queries, chatty service calls, missing indexes, serialisation in hot loops |
| Security | See lens 2 |
| Maintainability / evolvability | God modules, high coupling, unclear boundaries, no tests on core rules |
| Testability | Logic tangled with I/O, global state, hidden time/randomness |
| Deployability | Lockstep releases between units, manual steps, migrations coupled to app start |
| Observability | No correlation IDs, unstructured logs, no metrics on critical paths |
| Fault tolerance | One bad dependency or message takes down the whole process |

**Rule:** a system can't max out all of them. Pick the top 3–5 that matter for this business (state them as an assumption if the user didn't) and judge findings against those. A performance nit in an internal batch job is not the same as one in a checkout API.

Implicit characteristics (security, maintainability) always count even if nobody listed them.

## 2. Architecture quantum
An **architecture quantum** is an independently deployable unit with high functional cohesion and its own data and characteristics. Find them by asking: *what can be deployed alone, and what must be deployed together?*
- Two "microservices" that share one database schema are usually **one quantum** — they cannot evolve independently.
- A synchronous call from A to B means A's availability is capped by B's; they are dynamically coupled even if deployed separately.

Report the quanta you find and whether their real coupling matches what the team thinks it has.

## 3. Identify the actual style
Name the style the code actually implements, with evidence: layered monolith, modular monolith, microkernel/plugin, service-based, event-driven (broker or mediator), space-based, microservices, or a hybrid. Common mismatch to flag: "microservices" that are really a **distributed monolith** (shared DB, synchronous call chains, lockstep releases) — paying distribution costs without independence benefits.

## 4. Coupling and connascence
Use connascence to describe coupling precisely, from weaker to stronger:
- **Static (visible in code):** name → type → meaning/convention (magic values both sides must agree on) → position (argument order) → algorithm (both sides must hash/encode the same way).
- **Dynamic (only at runtime):** execution order → timing → values that must change together → identity (both must reference the same instance).

Guidance: stronger forms should stay **local** (inside one module); across module or service boundaries, push coupling down to the weakest form (name/type, explicit contracts). A finding like "order-service and billing-service both hard-code the status string `'PAID_V2'`" is connascence of meaning across a quantum boundary — fix with a shared, versioned contract.

## 5. Modularity metrics (use when a module graph is available)
- **Cohesion:** do the things in this module change together for the same reason?
- **Afferent / efferent coupling:** how many depend on it / how many it depends on. High-afferent modules must be stable; high-efferent modules are fragile.
- **Abstractness vs instability:** concrete modules that everyone depends on are painful to change ("zone of pain"); abstract modules nobody uses are waste ("zone of uselessness").
- **Cycles:** any dependency cycle between modules is a finding.

## 6. Fitness functions
Any objective, automatable check that protects an architecture characteristic. See `07-adrs-and-fitness-functions.md`.
