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
POST-only cart mutations, and cart merging when a guest signs in. **Phase 6 —
Checkout & Orders** adds delivery-address selection or one-time entry, an order
review, transaction-safe stock revalidation, order snapshots, mock payment
outcomes, and customer order history. **Phase 7 — Wishlist & Coupons** adds
private saved watches and server-revalidated checkout discounts. **Phase 8 —
Reviews** adds moderated, verified-purchase product reviews. **Phase 9 —
Testing & Hardening** covers authentication boundaries, safe redirects, cart
merge adjustments, coupon failure rollback, payment errors, and concurrent
stock allocation.

The remaining planned work is visual polish and production deployment.

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

## Checkout and orders

Checkout requires authentication, validates the cart again before review and
again while creating an order, then uses a controlled mock payment page. A
successful simulation creates a paid order, snapshots product and delivery
data, decrements stock inside the same database transaction, and clears the
cart. A failed simulation changes none of those records.

Shipping is deliberately set to complimentary insured delivery for the current
portfolio version. No payment credentials are collected or transmitted.

## Wishlist and coupons

Authenticated customers can save or remove available watches from their
wishlist on cards and product pages, then revisit the dedicated `/wishlist/`
page. Wishlist data is private to each customer.

Staff can create active coupon codes in the Django admin. Checkout accepts one
coupon at a time and revalidates its active state, validity window, minimum
order and fixed or percentage discount against the server-calculated subtotal
both before payment and inside the order transaction. The redeemed code and
discount are retained on the order as historical snapshots.

## Reviews

Only customers with a paid, processing, shipped, or delivered order containing a
watch can submit one review for it. Those reviews are marked as verified
purchases and remain private until a staff member approves them in the Django
admin. Public product pages show only approved reviews and calculate ratings
from that moderated set.

## Quality checks

```powershell
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\ruff check .
.\.venv\Scripts\python manage.py test
```

The default settings module is `config.settings.development`. Production
settings live in `config.settings.production` and must be selected explicitly
through `DJANGO_SETTINGS_MODULE`.
