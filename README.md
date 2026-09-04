# Auremont

Auremont is a Django luxury-watch store. This repository currently contains
**Phase 1 — Foundation** only: project configuration, PostgreSQL, a custom
email-based user model, a Tailwind-built site shell, tests, and basic CI.

Catalog, authentication flows, cart, checkout, orders, wishlist, and reviews
are deliberately not implemented yet.

## Stack

- Python 3.14.7
- Django 6.1.1
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

## Quality checks

```powershell
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\ruff check .
.\.venv\Scripts\python manage.py test
```

The default settings module is `config.settings.development`. Production
settings live in `config.settings.production` and must be selected explicitly
through `DJANGO_SETTINGS_MODULE`.
