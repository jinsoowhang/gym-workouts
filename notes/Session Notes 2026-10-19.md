# Session Notes — 2026-10-19

Opened the hosted gym page for the user's workout. Initial public health/login
checks passed, but the user reported that Start workout did nothing. Reproduced
the public POST returning 403 with "Cross-origin request denied". The same request
through the origin's HTTPS listener reached authentication correctly, isolating
the failure to how the public proxy chain presents the upstream request scheme.

Changed hosted mutation Origin validation to compare against the explicitly
configured HTTPS public origin. Local mode retains request-origin validation.
Host allowlisting, Google authentication, cross-site checks, and rejection of
incorrect Origin schemes, hosts, and ports remain in place. Added regression
coverage for authenticated HTMX workout creation over HTTP and HTTPS upstreams.

Verification: 56 authentication, workflow, and ownership tests passed; both browser
recording workflows passed with synthetic data. Ruff, formatting, and whitespace
checks passed. Preserved a consistent SQLite backup, prior source, and prior image
privately on the VPS before rebuilding and restarting only the gym container.
Local, remote-source, and running-container hashes match. Public health returns
200; same-origin Start requests now reach authentication (401 without a login),
while wrong-origin requests still return 403 and anonymous data access is blocked.
No synthetic workout was written to the real database. User retry and completion
with Obsidian note sync remain the final real-account verification.
