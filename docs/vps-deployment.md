# Private VPS hosting with Google sign-in

The app can run continuously in Docker on a Linux VPS. Its HTTP server stays on
`127.0.0.1`; Cloudflare Tunnel connects it to an HTTPS hostname. Cloudflare Access
authenticates users through Google and allows only the explicitly approved email
address. The tunnel verifies the Access token before forwarding requests.

## App and storage

Use `deploy/Dockerfile` and `deploy/compose.yml`. The Docker build context permits
only application source, migration files, and dependency metadata. Runtime
databases, environment settings, backups, and workout notes are excluded.

Create a private `.env` on the VPS using `deploy/.env.example`. Set the hostname,
state directory, timezone, and synced workout directory. Set `GYM_UID`/`GYM_GID`
to the owner of that folder. Pre-create the state directory and give that account
ownership. The container persists SQLite separately from the source checkout.

```bash
docker compose --env-file .env -f deploy/compose.yml build
```

For a fresh installation, import the templates and existing notes:

```bash
docker compose --env-file .env -f deploy/compose.yml run --rm app /app/.venv/bin/gym-init
```

To migrate an existing installation, use Python's SQLite backup API to create a
consistent copy of the local application database. Transfer that copy privately
to the server's state directory as `app/gym.sqlite3`. Do not copy a running
database file without its WAL. Apply migrations to that copy without reimporting:

```bash
docker compose --env-file .env -f deploy/compose.yml run --rm app /app/.venv/bin/python -c 'from gym_workouts.cli import migrate; from gym_workouts.config import Settings; migrate(Settings.from_env())'
docker compose --env-file .env -f deploy/compose.yml up -d app
```

This starts a private staging instance. Check health through the VPS itself:

```bash
curl http://127.0.0.1:8010/health
```

## Cloudflare and Google

Use a domain managed by your Cloudflare account. The account owner must configure
the identity provider; the app needs no Gmail-reading permission.

1. In Cloudflare Zero Trust, find or create the team's Access domain.
2. Create a **Web application** OAuth client in Google Cloud. Use the team's
   `https://TEAM.cloudflareaccess.com` as its authorized JavaScript origin and
   `https://TEAM.cloudflareaccess.com/cdn-cgi/access/callback` as its redirect URI.
   Choose an external audience for a personal Gmail account. Keep the client
   secret private. An existing Desktop OAuth client cannot replace this client.
3. In Cloudflare Zero Trust, add **Google** as an identity provider using that
   OAuth client's ID and secret. Test the provider.
4. Create a **Self-hosted** Access application covering the entire app hostname.
   Select Google as its login method. Add an **Allow** policy for the specific
   approved email address. Avoid broad rules that admit every Google account.
   Record the application's audience (AUD) tag.
5. Create a dedicated locally managed Cloudflare Tunnel. Store its credential
   JSON and configuration outside the public checkout, in `GYM_TUNNEL_DIR`.
   Populate `deploy/cloudflared.example.yml` with the tunnel ID, hostname, team,
   and AUD tag. Keep `access.required: true`. Route the hostname's DNS to this
   tunnel only after the Access application exists.
6. Set `GYM_CLOUDFLARED_IMAGE` to a verified version or image digest, then start
   the connector:

```bash
docker compose --env-file .env -f deploy/compose.yml -f deploy/compose.tunnel.yml up -d
```

Official references: [Google identity provider](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/google/),
[protecting a self-hosted app](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/),
and [tunnel token validation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/#access).

## Cutover and verification

Before switching to the hosted app, stop the local recording server, take a final
SQLite backup, and update the server copy while its container is stopped. Keep
the local backup for recovery. Use one application database for active recording;
sync the Markdown folder through Obsidian's existing file-sync process. Syncthing
can carry new notes back to the PC when it reconnects. Do not sync live SQLite.

Verify that anonymous requests to both `/` and `/api/v1/sessions` reach the login
gate, an unapproved Google account is refused, and the approved account can record
and finish a workout. Confirm the resulting Markdown note reaches the PC. Check
that the VPS's app port is unreachable from outside and that restarting the app
retains its data. Change the Desktop launcher to open the hosted URL after these
checks pass.

The reverse proxy must preserve the public Host and HTTPS scheme. Uvicorn trusts
forwarded scheme headers from loopback by default, where this connector runs.
`GYM_ALLOWED_HOSTS` permits the configured hostname; mutation-origin checks remain
active. Back up SQLite and the workout folder together using consistent snapshots.
