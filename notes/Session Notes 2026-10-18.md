# Session Notes — 2026-10-18

Connected the existing gym domain to the VPS app. The default proxy landing page
was caused by a missing proxy route; the old private staging image also lacked
Google sign-in. The owner created a Google Web application OAuth client, and its
downloaded JSON was validated against the configured HTTPS origin and callback.
Credentials are stored only in ignored private settings and the private VPS env.

Before deployment, confirmed the local server was stopped from both WSL and
Windows. Created a consistent SQLite snapshot and verified that every completed
workout in the older VPS database was also completed in the local snapshot. All
32 Markdown workout notes matched between local and synced server folders. Backed
up the previous server source, SQLite database, proxy database/configuration, and
container image before replacing staging with the current app and local snapshot.

The app now runs with Google authentication enabled on the existing proxy Docker
network, without a published host port. Applied migrations, installed a managed
HTTPS certificate, and created the gym proxy route. Disabled access logging for
that route to avoid recording OAuth callback codes. Existing proxy routes were
checked and retained their configuration.

Verification: 93 Python tests passed; the two opt-in browser tests were skipped.
Scoped authentication/configuration Ruff checks passed. The hosted app is healthy;
SQLite integrity and migration head were verified. Public HTTPS health and login
return 200, workout/history/dashboard pages redirect anonymous visitors to login,
the state API returns 401, and anonymous session creation is blocked. Google login
redirects to the expected provider and callback with PKCE and a Secure cookie.
The origin certificate validates, and the proxy configuration passes nginx -t.

Owner sign-in and an authenticated recording with completed-note sync remain
manual verification steps. No synthetic workout was added to the real database.
The local server remains stopped. The Windows launcher remains in local mode
until authenticated recording and sync have been verified; avoid recording into
both local and hosted databases. Deployment state, rollback backups, verification
responses, and credential files remain ignored and were not added to Git.

## Account ownership foundation

The user requested assigning their current workouts to their approved email while
preparing for future users with separate workouts. They accepted adding ownership
now, keeping registration closed, and later using invitations and editable generic
starter routines with empty history. Obsidian sync remains exclusive to the owner.

Added users with a stable account ID, private normalized email, optional unique
Google subject, and one designated vault owner. Sessions and routine templates
have required ownership; login sessions reference the user. Existing sessions,
drafts, defaults, sets, source records, and pending publications were preserved.
The migration revokes old login sessions and binds the approved verified Google
identity on the next sign-in. A changed email configuration fails closed rather
than transferring ownership.

Scoped repositories, request services, history, dashboard/defaults, review actions,
and mutations to the current user. Accessing another user's workout ID returns
404. The client cannot select ownership through request parameters. Owner-only
note publication/recovery prevents other profiles from writing into the vault.
Owner snapshots exclude other users' exercises, sessions, templates, rows, and
pending publications. Account identifiers and authentication data stay outside
the existing warehouse contract.

Created fresh local and server rollback backups. Rehearsed the migration on a
private copy of the server database and compared every preexisting workout column
before and after. After stopping the server, repeated the consistent backup and
same comparisons for the live migration; all original data and foreign keys were
preserved. Deployed the new image, verified the configured owner and sole account,
and confirmed all live sessions/templates belong to it. The inactive local copy
was migrated independently using the same approved email in private settings.

Verification passed 103 Python/browser tests across the full suite and final
scoped additions, including two live-browser recording workflows. The synthetic
dbt build passed eight models and 35 data tests. Ruff, formatting, compilation,
SQLFluff, whitespace, and public-file checks passed. Public HTTPS health/login
return 200; workout/history/dashboard pages redirect anonymous requests to login,
the state API returns 401, and the Google redirect retains the expected callback
and PKCE. Live owner state/dashboard queries succeeded without modifying workouts.

Additional-user registration, invitations, generic starter-routine editing, and
website-only completion are deferred. Actual owner sign-in must be repeated after
the migration; authenticated recording and note sync remain manual verification.
The local server and Windows launcher remain in their prior state. No real test
workout was created, and private settings/backups remain ignored.

## Login design research and previews

Reviewed the current login and found that its single content element is squeezed
into the first column of the shared workout `.start-panel` grid. Researched Google
sign-in branding, WCAG text contrast/target sizes, and focused navigation guidance.
Saved linked findings and tradeoffs in `Login Design Research 2026-10-18.md`.

Created `Login Design Options 2026-10-18.html`, a standalone local design preview
with three selectable directions, desktop/mobile sizes, and proposed error-state
copy. Quiet focus is recommended for its clear action, restrained appearance, and
fit with the current app. Training journal adds a warm editorial introduction;
After hours offers a charcoal/mint fitness style. All avoid private workout data
and expose only the existing approved-account sign-in concept.

Chromium exercised all option/size controls, captured desktop/mobile screenshots,
and verified no horizontal overflow at a 375px viewport, 48px sign-in controls,
and no JavaScript errors. Inspected the comparison and desktop editorial preview.
Screenshots remain ignored under `data/reports/login-design-options/`. No production
login changes or deployment occurred; selection of a visual direction is next.

## Quiet focus login implementation

The user selected option 1. Implemented its centered ivory/sage card, barbell
emblem, concise greeting, account-privacy helper, and approved-account access note.
Replaced the shared workout-grid login container with dedicated login markup and
`login.css`. Added small base-template blocks to support login-specific styling,
skip text, navigation, and footer while retaining other pages' default rendering.

The Google action retains the existing OAuth URL. Vendored the current official
SVG from Google's downloadable sign-in asset bundle, cropping its canvas and
removing the outer button border while retaining the original gradient logo and
outlined text. The responsive link supplies its border, padding, hover/focus, and
48px target. This avoids a new font or external runtime asset dependency.
Provenance: https://developers.google.com/identity/branding-guidelines .

Verification passed 34 authentication/configuration tests and both existing
desktop browser recording workflows. Exercised ready, OAuth-error, and unavailable
states at 1440px, 375px, and 320px, including their HTTP status, error/status
announcements, Google link/asset, keyboard focus, touch target, and absence of
horizontal overflow or unexpected browser errors. Checked normal text contrast
pairs range from 5.53:1 to 7.40:1. Ruff, formatting, whitespace, and public-file
policy passed. Inspected desktop and mobile-error screenshots.

Backed up the deployed source and previous container image, then deployed only
the two templates and two new static assets. No database migration was needed.
Live desktop/mobile Chromium checks passed; public CSS/SVG hashes match local
assets, health is good, and anonymous API requests remain blocked. Screenshots
are ignored in `data/reports/login-quiet-focus/`; rollback details stay in the
private deployment checkpoint.
