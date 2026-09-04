# Auremont

Auremont is an independent Django luxury-watch store demonstration project.
It currently contains **Phase 1 — Foundation**, **Phase 2 — Catalog**, and
**Phase 3 — Storefront UI**: project configuration, PostgreSQL, a custom
email-based user model, a Tailwind-built site shell, catalog administration,
responsive browse/detail, brand, collection and search pages, filtering,
sorting, pagination, lazy-loaded catalog images, fixtures, tests, and basic
CI. **Phase 4 — Accounts** adds email registration and confirmation, login,
POST-only logout, password reset, profile editing, delivery-address management,
and optional Google Sign-In configuration. **Phase 5 — Cart** adds guest and
authenticated carts, server-calculated prices, stock-limited quantities,
POST-only cart mutations, and cart merging when a guest signs in.

Checkout, orders, wishlist, and reviews are deliberately not implemented yet.

## Stack

- Python 3.14.7
- Django 6.1.1
- django-allauth 65.19.2
- PostgreSQL 18.6
- Psycopg 3.3.5
- Tailwind CSS 4.3.3

## Local setup

1. Copy the environment template and replace the development-only values.

   ```powershell
   Copy-Item .env.example .env
   ```

2. Start the local PostgreSQL service.

   ```powershell
   docker compose up -d db
   ```

3. Create the Python environment and install dependencies.

   ```powershell
   py -3.14 -m venv .venv
   .\.venv\Scripts\python -m pip install --upgrade pip
   .\.venv\Scripts\python -m pip install -r requirements-dev.txt
   ```

4. Install and build frontend assets.

   ```powershell
   npm ci
   npm run build
   ```

5. Apply migrations, run tests, and start Django.

   ```powershell
   .\.venv\Scripts\python manage.py migrate
   .\.venv\Scripts\python manage.py test
   .\.venv\Scripts\python manage.py runserver
   ```

Open `http://127.0.0.1:8000/`.

## Catalog demo data

After migrations, load the deliberately image-free catalog fixture. It uses
real watch brand names only for portfolio demonstration; Auremont is not
affiliated with those brands.

```powershell
.\.venv\Scripts\python manage.py loaddata catalog_demo
```

## Run the development stack with Docker

After creating `.env`, run the Django app and PostgreSQL together:

```powershell
docker compose up --build
```

The `web` container waits for PostgreSQL, applies migrations, then starts the
Django development server at `http://127.0.0.1:8000/`.

Use `Ctrl+C` to stop the foreground process. To stop the stack later, run:

```powershell
docker compose down
```

`docker compose down -v` also deletes the local PostgreSQL volume and must only
be used when resetting development data is intentional.

## Accounts and Google Sign-In

Account routes use Django's conventional `/accounts/` prefix:

- `/accounts/signup/`
- `/accounts/login/`
- `/accounts/logout/`
- `/accounts/password/reset/`
- `/account/`

Development email is printed to the Django console. In production, configure a
real SMTP backend with `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_HOST`,
`DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`,
and `DJANGO_EMAIL_USE_TLS`, as well as `DEFAULT_FROM_EMAIL`.

Google Sign-In remains hidden until both `GOOGLE_OAUTH_CLIENT_ID` and
`GOOGLE_OAUTH_CLIENT_SECRET` are set in `.env`. Create a Web OAuth client in
Google Cloud Console, then register the local redirect URI below for this
project's current route layout:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

For a deployed environment, register its exact HTTPS callback URI too. Do not
commit OAuth client secrets.

## Cart

Visitors can add available watches to `/cart/` before signing in. The cart keeps
only watch identifiers and quantities; current prices and stock are read and
validated on the server for every add or quantity update. When a customer signs
in, the guest cart merges into that customer's cart and caps duplicate
quantities at the current stock level.

## Quality checks

```powershell
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\ruff check .
.\.venv\Scripts\python manage.py test
```

The default settings module is `config.settings.development`. Production
settings live in `config.settings.production` and must be selected explicitly
through `DJANGO_SETTINGS_MODULE`.
