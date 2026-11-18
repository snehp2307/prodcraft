# Data-intensive systems lens

Concepts drawn from *Designing Data-Intensive Applications* (Kleppmann), restated in our own words as a bug-hunting checklist for real code. Read the book for depth.

## Foundations: reliability, scalability, maintainability
- **Faults vs failures:** a fault is one component misbehaving; a failure is the whole system stopping service. Good design tolerates faults so they don't become failures. Ask: which single fault (one node, one dependency, one bad message) turns into a user-visible failure here?
- **Load parameters:** describe load in the terms that matter to *this* system (writes/s, fan-out, read/write ratio, payload size). Scalability claims without load parameters are not findings.
- **Tail latency:** look at p99, not averages. One slow backend call in a request that fans out to many makes most requests slow.

## Bug patterns to hunt

### 1. Non-idempotent retries (very common, High)
A client, queue, or job retries an operation that is not safe to repeat (charge card, send email, increment balance, insert row). Look for: retry decorators/loops around writes; at-least-once consumers (Kafka, SQS, RabbitMQ) without dedup; HTTP POST endpoints with no idempotency key.
Fix: idempotency key stored with the result in the same transaction; unique constraints; upserts; dedup table keyed by message ID.

### 2. Dual writes (High)
Code writes to the database *and* publishes an event / updates a cache / calls another service, as two separate steps. If the process dies between them, the systems disagree forever.
Fix: **transactional outbox** (write the event to an outbox table in the same DB transaction, relay it asynchronously) or change data capture; make consumers idempotent.

### 3. Read-modify-write races (High)
`x = read(); x.balance -= amount; save(x)` with concurrent requests → lost updates. Also check-then-insert (`if not exists: insert`) → duplicates.
Fix: atomic update in the DB (`UPDATE ... SET balance = balance - ? WHERE balance >= ?`), `SELECT ... FOR UPDATE`, optimistic concurrency with a version column, or unique constraints.

### 4. Wrong isolation assumptions (Medium–High)
Code assumes serializable behaviour but the database default is weaker (read committed in PostgreSQL, repeatable read in MySQL InnoDB). Watch for **write skew**: two transactions each read a condition, both decide it's fine, both write, and the invariant breaks (e.g. two doctors both go off-call; double-booking a slot).
Fix: materialise the conflict with a row to lock, use a unique/exclusion constraint, or run that transaction at serializable isolation and handle retry errors.

### 5. Replication lag surprises (Medium)
Writes go to the leader, reads go to a replica → user doesn't see their own change (**read-your-writes**), or sees time go backwards across requests (**monotonic reads**).
Fix: route a user's reads to the leader for a short window after they write, or pin a session to one replica, or read with a version/timestamp requirement.

### 6. Ordering by wall clock (Medium)
Using timestamps from different machines to decide "which write wins" or to order events. Clocks drift; last-write-wins silently drops data.
Fix: logical ordering (sequence numbers from a single leader, version vectors), or a single partition per key in a log.

### 7. Partitioning and hot keys (Medium)
Sharding/partitioning by a key with skew (celebrity user, one tenant with 80% of traffic, time-based keys that send all writes to the newest partition). Queries that must hit every partition on a hot path (scatter-gather).
Fix: choose keys that spread load; add a random suffix for known hot keys; keep hot-path queries single-partition.

### 8. Unbounded queues and missing backpressure (Medium–High)
In-memory queues, thread pools, or consumers with no bound; producers that never slow down. Under load the process runs out of memory and loses everything in the buffer.
Fix: bounded queues, explicit rejection/429, consumer lag alerts, durable broker instead of in-memory buffers for anything that must not be lost.

### 9. Schema evolution (Medium)
Changing a message or API schema without considering old readers and new writers running at the same time during a rolling deploy. Removing/renaming fields, changing types, required fields added without defaults.
Fix: backward- and forward-compatible changes only (add optional fields with defaults, never reuse field tags/names), version contracts, expand → migrate → contract for databases.

### 10. Derived data drift (Medium)
Caches, search indexes, read models, or denormalised columns updated by application code in addition to the source of truth. They drift after any partial failure.
Fix: treat the source of truth's change log as the single input for derived views (CDC/outbox), make rebuilds possible, and add a reconciliation job.

### 11. Exactly-once claims (flag wording)
"Exactly-once delivery" across systems is not achievable in general; what is achievable is **effectively-once processing** = at-least-once delivery + idempotent processing. Flag designs that rely on the broker alone.

### 12. Batch vs stream choice
Recomputing everything on a schedule when incremental processing is needed (or vice versa). Check that stream consumers handle reprocessing (replay from offset) without double effects.

## Questions to ask the user if the code doesn't answer them
- Which database and what isolation level is configured?
- Is the message broker at-least-once? Are consumers idempotent?
- Are reads ever served from replicas or caches right after a write?
