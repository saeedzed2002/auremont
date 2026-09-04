# Production operations

## Deployment boundary

This repository prepares the application containers. It does not provision a
domain, a certificate authority account, a cloud host, DNS records, or a
managed backup destination.

`nginx/default.conf` expects a trusted TLS terminator in front of the exposed
HTTP port. That terminator must redirect HTTP to HTTPS and send
`X-Forwarded-Proto: https`. Restrict the Compose HTTP port so direct clients
cannot spoof that header. Do not set the HSTS subdomain or preload flags until
every applicable subdomain has HTTPS configured.

## First deployment

1. Copy `.env.production.example` to `.env.production` on the target host and
   replace every placeholder. Keep this file outside version control.
2. Point the production domain at the TLS terminator and configure it to route
   traffic to the host's Compose HTTP port.
3. Register the exact HTTPS Google OAuth callback, if Google Sign-In is
   enabled: `https://your-domain.example/accounts/google/login/callback/`.
4. Start PostgreSQL, then run the one-shot release task before starting web
   traffic.

```sh
docker compose --env-file .env.production -f compose.production.yaml up -d db
docker compose --env-file .env.production -f compose.production.yaml run --rm release
docker compose --env-file .env.production -f compose.production.yaml up -d --build
docker compose --env-file .env.production -f compose.production.yaml ps
```

The release task applies migrations and creates a manifest-backed static asset
set in the shared `auremont_static_data` volume. Product uploads persist in
`auremont_media_data`; PostgreSQL data persists in `auremont_postgres_data`.

## Post-deploy checks

```sh
curl -fsS https://your-domain.example/healthz/
docker compose --env-file .env.production -f compose.production.yaml logs --tail 100 web nginx
```

The health endpoint verifies that Django can make a database query. It is safe
to expose and returns only `{"status": "ok"}` or `{"status": "unavailable"}`.

## Backups

Back up both the PostgreSQL dump and the media volume to durable off-host
storage. Test restoration against a non-production project before relying on a
backup.

```sh
docker compose --env-file .env.production -f compose.production.yaml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > auremont-postgres.sql
```

Archive or snapshot the named `auremont_media_data` volume with the approved
backup mechanism on the target host. The exact command is host-specific; it
must produce an off-host copy and should be rehearsed alongside database
restoration.

Retain backups according to the host's recovery policy and protect them with
the same access controls as production data.
