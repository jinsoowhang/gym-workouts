# VPS hosting with direct Google sign-in

The app runs continuously in Docker behind your existing HTTPS reverse proxy.
Google sign-in is part of the app. A verified Google identity must match the
single approved email address before any workout page or API is available.
Cloudflare can continue providing DNS for the domain. Zero Trust is not required.

The ownership migration assigns existing sessions and personal routine templates
to this configured account, including current drafts. Google sign-in binds its
stable subject on the first successful login. Changing `GYM_ALLOWED_EMAIL` after
ownership is assigned fails startup rather than transferring private workouts.
Local mode uses the same persisted owner without requiring a Google login.
Public registrations remain closed; invitations and generic starter routines are
planned for later. Obsidian sync remains exclusive to the configured vault owner.

## Private settings and Google client

Create a private `.env` on the VPS from `deploy/.env.example`. Set the hostname,
state directory, synced workout directory, and timezone. Set `GYM_UID`/`GYM_GID`
to the owner of the workout folder and give that account ownership of the state
directory. `GYM_PROXY_NETWORK` must name the existing proxy's Docker network;
`GYM_PROXY_IPS` must contain the trusted proxy container's IP address.

Store the actual allowed email and secrets only in that private file. Generate
`GYM_SESSION_SECRET` with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.
Preserve this value across deployments. Never put it in source, examples, logs,
or issue reports. The hosted Compose configuration always enables authentication.
If Google credentials are not configured, the app shows a setup page and blocks
workout pages and APIs.

Create a dedicated **Web application** OAuth client in
[Google Cloud Console](https://console.cloud.google.com/auth/clients). Choose an
external audience for a personal Google account and configure only the basic
`openid` and `email` sign-in scopes. Use your app origin as the authorized
JavaScript origin, and its `/auth/callback` URL as the authorized redirect URI.
For example:

- Origin: `https://gym.example.com`
- Redirect URI: `https://gym.example.com/auth/callback`

If the client is in testing, add the approved account as a test user. Download
its credential JSON into an ignored private directory such as `.secrets/`; an
existing Desktop OAuth client is not suitable for this web callback. Set its
client ID and secret as `GYM_GOOGLE_CLIENT_ID` and `GYM_GOOGLE_CLIENT_SECRET` in
the private VPS `.env`, then recreate the app container. The app does not request
Gmail-reading permissions or store Google access/refresh tokens.

Reference: [Google's OpenID Connect server flow](https://developers.google.com/identity/openid-connect/openid-connect).

## Docker and database

The Docker context includes only source, migrations, and dependency metadata.
Runtime databases, environment files, backups, and private notes are excluded.
The container joins the proxy's Docker network and publishes no host port.
Configure the reverse proxy to reach `http://gym-workouts:8010` on that network.
Keep authentication enabled even when routing directly to the container.

```bash
docker compose --env-file .env -f deploy/compose.yml build
```

For a fresh database, import your templates and historical notes:

```bash
docker compose --env-file .env -f deploy/compose.yml run --rm gym /app/.venv/bin/gym-init
```

For an existing database, use SQLite's backup API to create a consistent copy.
Transfer it privately into the state directory as `app/gym.sqlite3`. Apply
migrations to that copy without reimporting the vault:

```bash
docker compose --env-file .env -f deploy/compose.yml run --rm gym /app/.venv/bin/python -c 'from gym_workouts.cli import migrate; from gym_workouts.config import Settings; migrate(Settings.from_env())'
docker compose --env-file .env -f deploy/compose.yml up -d --remove-orphans gym
```

The ownership migration rebuilds SQLite tables transactionally, verifies foreign
keys, and preserves workout records. Stop the app and take a consistent SQLite
backup before applying it. Existing login sessions are revoked; sign in again
after deployment. Health checks use `/health` inside the container.

## HTTPS proxy and cutover

Create a proxy host for the app subdomain in your existing Nginx Proxy Manager.
Forward to `gym-workouts` on port `8010`, with scheme `http`. Obtain a certificate
covering that subdomain and force HTTPS. Preserve the public Host and forward the
HTTPS scheme; Uvicorn trusts only the proxy address configured above. Disable
access logging for this host so OAuth callback codes are not recorded in URLs.

Before active recording moves to the VPS, stop the local recording server and
take a final consistent SQLite backup. Stop the hosted container, replace its
staging database with that final copy, apply migrations, and restart. Keep the
local backup. Use one active recording database and sync only the Markdown folder
through the existing Obsidian/Syncthing workflow; never sync live SQLite.

Verify anonymous HTML redirects to `/login`, APIs return 401 without exposing
workout data, and an unapproved Google account cannot log in. Verify the approved
account can finish a workout and that its note reaches the PC. Sessions have a
fixed 24-hour expiry, and signing out revokes the server-side session. Expired
sign-in leaves unsaved fields intact and offers a new-tab login and save retry.
Change the Desktop launcher to open the hosted URL only after authenticated
recording and vault sync pass.

Local recording keeps its no-login default and loopback listener. After updating
an existing local installation, apply migrations before restarting it. Keep
private login identities and OAuth credentials outside GitHub. The publication
checks reject personal email addresses and credential JSON files.
