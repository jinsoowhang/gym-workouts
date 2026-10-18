# Architecture and data ownership

```mermaid
flowchart LR
  O[Obsidian workout notes] --> I[Validated import]
  I --> S[(SQLite)]
  U[Jinja + HTMX UI] <--> F[FastAPI services]
  F <--> S
  S --> W[Durable vault write]
  W --> O
  S --> E[Consistent snapshot]
  E --> D[(DuckDB raw + manifest)]
  D --> T[dbt staging → intermediate → marts]
```

SQLite owns app drafts, statuses, actual results, imported provenance, and retryable
vault writes. SQLAlchemy repositories isolate persistence; services handle workout
rules and publication; FastAPI transports commands and renders Jinja/HTMX fragments.
Alembic owns operational schema changes.

Workout sessions and routine sets have a required `user_id` referencing a stable
user record. The existing dataset belongs to the configured vault owner. Hosted
requests take their user identity from a validated login session; repositories,
history, defaults, drafts, edits, and dashboard queries scope access to that user.
Another user's workout ID returns the same not-found response as a missing ID.
The owner is initially identified by the configured verified email and then bound
to Google's stable subject. Changing the allowed email cannot transfer ownership.

Registration remains closed to the configured owner. Future onboarding will use
invitations and editable generic starter routines with empty history, rather than
copying the owner's workouts, templates, loads, or therapy defaults. Invitations
and starter-routine editing are not implemented in this ownership foundation.
Obsidian import/publication and private warehouse snapshots belong exclusively
to the vault owner. Additional users must get website-only recording before their
access is enabled; they cannot publish into the owner's workout folder.

Only a finished session is published as a dated Obsidian note. Results are first
persisted with a pending write; file publication is then acknowledged in SQLite.
Interrupted acknowledgement is recovered by matching session identity/content.
Failed saves remain finalizing and cannot advance the next workout. Existing
differing notes are conflicts, never overwritten. A complete temporary file is
published with a same-directory, no-clobber hard link; Windows/NTFS and WSL support
this path. Unsupported filesystems surface an error and preserve the pending write.

Templates and existing notes are read-only import sources. An optional, explicitly configured
legacy cutoff confirms historical notes through a reviewed date. Without a cutoff,
unmarked notes require explicit completion review. Changed imported checksums are reported rather
than silently replacing results. App metadata and numeric result lines must agree.

Recorded exercises have stable identities and ordered per-routine set keys. Legacy
sets map only when an exercise's set count matches the template; missing middle
sets have unknown planned identity. Prefills still reuse those observed values in
recorded order and label that assumption; only additional sets use template values.
New notes retain
planned-set metadata, including skipped/removed positions. Removal is session-only.

The web process binds to loopback, checks trusted hosts and mutation origins, and
accepts file targets only from validated session dates/routines. No vault directory
is exposed as static assets. The local port is configurable.

Analytics is downstream, never invoked by recording requests. A read-only SQLite
transaction extracts contracted tables, preserving IDs, statuses, and row order.
Content hashes make unchanged snapshots idempotent. DuckDB loads all tables and
publishes the manifest in one transaction; dbt selects the newest complete snapshot.
Private source text and pending-note contents are excluded from warehouse extracts.

Synthetic fixtures use a separate DuckDB file. Real snapshots and generated docs
remain ignored. Model descriptions and tests define grain, relationships, completion
filters, and recorded external-load volume. The hosted BigQuery/dbt Platform path
is a documented future milestone; no cloud dependency is required to record.
