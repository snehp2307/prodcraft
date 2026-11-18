# Distributed architecture trade-offs lens

Concepts drawn from *Software Architecture: The Hard Parts* (Ford, Richards, Sadalage, Dehghani), restated in our own words. The core idea: in distributed architecture there are no best practices, only trade-offs — so every recommendation must name the forces on both sides.

## 1. Service granularity: name the forces
Never recommend "split this service" or "merge these services" without listing the forces.

**Forces that push toward splitting (disintegrators):**
- Different parts have different **volatility** (one changes weekly, the rest yearly).
- Different **scalability/throughput** needs.
- Different **fault tolerance** needs (a crash in the image resizer shouldn't kill checkout).
- Different **security** boundaries (PCI data, admin functions).
- Code that is genuinely unrelated in purpose (low cohesion).

**Forces that push toward keeping together (integrators):**
- They need a single **ACID transaction** across their data.
- They form one **workflow** with heavy synchronous back-and-forth (chatty calls, latency, failure coupling).
- They **share code or data** so heavily that splitting forces lockstep releases.
- The **data relationships** are tight (foreign keys, joins on every request).

A finding should read like: "Splitting `notifications` out of `orders` is justified by volatility and fault tolerance (evidence…). Keep `pricing` with `orders` because every order write needs a consistent price in the same transaction (evidence…)."

## 2. Data ownership
- Each table should have **one writing owner** (service/module). Multiple writers to the same table across service boundaries = shared-database coupling; flag it with the list of writers.
- Options when two services need the same data, with trade-offs:
  - **Synchronous call to the owner:** always fresh; couples availability and latency.
  - **Replicated read-only copy** (events/CDC into the reader's store): independent and fast; eventually consistent, needs reconciliation.
  - **Shared library/cache of reference data:** simple for slow-changing data; stale risk, version coordination.
  - **Merge the services:** simplest consistency; loses independent deployability.

## 3. Distributed transactions and workflow coordination
When a business operation spans services, identify how it is coordinated and whether that matches its needs. Describe it on three axes:
- **Communication:** synchronous (request/response) vs asynchronous (messages/events).
- **Consistency:** atomic (all-or-nothing via a distributed transaction) vs eventual (compensations).
- **Coordination:** orchestrated (a central workflow owner) vs choreographed (services react to each other's events).

Common findings:
- Choreography for a complex multi-step workflow with many failure branches → nobody owns the overall state; debugging and compensations are scattered. Consider an orchestrator for this workflow.
- Orchestration for a simple fan-out notification → unnecessary central coupling.
- A "saga" with no compensating actions defined for steps that can fail after earlier steps succeeded → silent inconsistency. List each step, its failure, and its compensation; mark gaps.
- Synchronous chains across 3+ services on a user request → availability is the product of each hop; consider async where the user doesn't need the result immediately.

## 4. Contracts
- **Strict contracts** (typed schemas, versioned APIs) catch breakage early but couple deployments.
- **Loose contracts** (consumers read only the fields they need, tolerant readers) evolve independently but hide breakage until runtime.
- Recommend **consumer-driven contract tests** when many consumers depend on one provider.
- Flag internal types or ORM entities leaked directly as public API/message payloads — every internal refactor becomes a breaking change.

## 5. Reuse across boundaries
Shared code options and trade-offs: copy (independent, drifts), shared library (consistent, version coupling), shared service (single deploy, runtime coupling), sidecar/service mesh (operational concerns only). Flag shared libraries that contain **business logic** used by multiple quanta — a change forces coordinated releases.

## 6. Analytical data
Flag operational services that run heavy analytics queries on their production database, or analytics pipelines that read other services' private tables. Prefer each domain publishing analytical data as a product (events or curated tables) rather than others reaching into its schema.

## 7. Output: a trade-off table
For each significant architecture finding, include:

| Option | Gains | Costs | Fits this system because… |
|---|---|---|---|

and put the decision in an ADR (see `07-adrs-and-fitness-functions.md`).
