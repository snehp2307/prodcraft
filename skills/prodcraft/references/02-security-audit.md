# Lens 2 — Security audit

Method: walk the **trust boundaries**. Anything that crosses into the process from outside (HTTP, queues, files, env, DB rows written by others, LLM output) is untrusted until validated. Severity = exploitability × impact.

## 1. Map the attack surface first
List: public endpoints (and which are unauthenticated), message consumers, file/upload handlers, webhooks, admin panels, background jobs triggered by user data, outbound calls driven by user input. The inventory script's entry points are your starting list.

## 2. Checklist by category (mapped to OWASP Top 10 where it applies)

### Access control (A01)
- Every handler that reads or writes a resource checks the caller **owns or may access that specific resource**, not just "is logged in". Look for IDOR: `GET /orders/{id}` loading by id with no owner check.
- Authorization is enforced server-side, not by hiding UI.
- Admin/internal routes are not reachable from the public router.
- Multi-tenant queries always scope by tenant.

### Cryptography and secrets (A02)
- No secrets in source, Dockerfiles, CI YAML, test fixtures, or committed `.env` files. (Inventory flags candidates; confirm each.)
- Passwords hashed with a slow adaptive function (argon2, bcrypt, scrypt), never plain SHA/MD5.
- TLS verification not disabled (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify`).
- Tokens/IDs that must be unguessable come from a CSPRNG (`secrets`, `crypto.randomBytes`), not `random`.

### Injection (A03)
- SQL built with string formatting/concatenation instead of parameters.
- Shell commands built from input (`os.system`, `subprocess(..., shell=True)`, `exec`, backticks).
- Template injection, unsafe deserialisation (`pickle.loads`, `yaml.load` without SafeLoader, Java native deserialisation).
- Path traversal: user input joined into file paths without normalising and checking the root.
- **LLM-specific:** model output treated as trusted (executed, used as SQL, used to pick a tool with side effects without confirmation); retrieved documents able to inject instructions; secrets placed in prompts.

### Insecure design (A04)
- No rate limiting or lockout on login, OTP, password reset, or expensive endpoints.
- Business-logic abuse: negative quantities, coupon reuse, race to double-spend (see also lens 4 on idempotency).

### Security misconfiguration (A05)
- Debug mode, stack traces, or verbose errors in production config.
- CORS `*` with credentials; permissive CSP; missing security headers on web apps.
- Default credentials, open admin consoles, public buckets in IaC.
- Containers running as root; writable root filesystem without need.

### Vulnerable components (A06)
- Unpinned dependencies or no lockfile. Known-vulnerable versions (use the ecosystem's local audit if present: `pip-audit`, `npm audit`, `govulncheck`, `cargo audit` — note these may contact a vulnerability database; ask first).
- Abandoned packages on a security-critical path.

### Identification and authentication (A07)
- Session/JWT handling: tokens validated (signature, `alg` pinned, expiry, audience); logout/rotation possible; refresh tokens stored safely.
- Sensitive cookies `HttpOnly`, `Secure`, `SameSite`.

### Integrity (A08)
- CI pulls actions/images by mutable tag instead of digest/SHA on privileged pipelines.
- Webhooks accepted without signature verification.

### Logging and monitoring (A09)
- Security events (login failures, permission denials, admin actions) are logged.
- Logs do not contain secrets, tokens, full card numbers, or unnecessary PII.

### SSRF (A10)
- Server fetches a URL supplied by a user without an allowlist, or follows redirects into internal address ranges / cloud metadata endpoints.

## 3. Severity guidance
- **Critical:** unauthenticated RCE, SQL injection on reachable endpoint, leaked production secret, auth bypass, IDOR on sensitive data.
- **High:** authenticated injection, missing authz on write paths, disabled TLS verification to a payment/identity provider, unsigned webhooks that move money.
- **Medium:** missing rate limits on auth, verbose errors, unpinned deps without known CVEs, overly broad CORS.
- **Low:** missing hardening headers on internal tools, minor info leaks.

## 4. Writing the finding
State the attacker, the path, and the impact in one sentence each. Example:
"An authenticated user (attacker) can call `GET /api/orders/{id}` with another user's order id (path) and read their address and phone number (impact). Evidence: `app/routes/orders.py:31` loads `Order.get(id)` with no `user_id` filter."

Never include a working exploit payload beyond what is needed to show the issue exists.
