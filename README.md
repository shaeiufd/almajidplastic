# Al Majid Plastic Store

A full-stack storefront for product browsing, stock-aware order requests, and protected store administration. The backend owns products, prices, inventory, and order records in SQLite. Checkout creates an order request; it does not collect payment or promise delivery.

## Requirements

- Python 3.11 or newer
- PowerShell on Windows, or a shell with equivalent environment-variable commands

## Run locally on Windows

From the project directory, create and install the local environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Create the first administrator. The command prompts for the username and password; use a unique password with at least 12 characters:

```powershell
.\.venv\Scripts\python.exe -m app.create_admin
```

Start the web server:

```powershell
$env:SESSION_SECRET = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the storefront at `http://127.0.0.1:8000/` and the admin panel at `http://127.0.0.1:8000/admin`. The app creates the SQLite database at `data/store.sqlite3` and seeds the sample catalog on first run. Stop the server with Ctrl+C.

For local demo convenience, the server generates a temporary session secret if `SESSION_SECRET` is omitted; administrator sessions will expire when it restarts. Set a persistent secret for normal use. Set `STORE_CURRENCY` and `STORE_LOCALE` before launch to choose the displayed currency and locale, for example `SAR` and `en-US`. Set `COOKIE_SECURE=1` only when serving behind HTTPS.

## Features

- Product search, categories, sorting, and a browser-persisted basket
- Product quick-view with editable descriptions and browser-saved favorites
- Server-calculated order totals and transactional stock reservation
- Customer order requests with order references; no payment integration
- Admin sign-in with PBKDF2 password hashes, signed sessions, and CSRF checks
- Admin dashboard with order status changes, product editing, inventory, and archiving
- Category management with storefront filters updated from the database
- Customer directory with order history, full order details, and print views
- Inline stock adjustment, configurable low-stock warnings, and persistent store contact/currency settings
- CSV exports for products, orders, and customers
- Admin product photo uploads for JPEG, PNG, and WebP (5 MB and 20-megapixel limits); content is validated independently of the filename/MIME label and stored in `data/uploads/`
- Admin-uploaded store logo/icon, displayed in the storefront and admin header with a default-mark fallback
- Cancelling an order restores reserved stock; products are archived rather than deleted
- CSS-built product art and no third-party asset requests

Run the API tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Production notes

This is a functional local application, not yet a production deployment. For production installs, install `requirements.txt` without the development test dependency. Before accepting real orders, deploy behind HTTPS, set a long random `SESSION_SECRET`, set `COOKIE_SECURE=1`, configure backups and monitoring for the SQLite database, and connect a payment provider and an agreed delivery workflow. Add rate limiting and operational email/notification handling before public exposure. Prices default to USD unless `STORE_CURRENCY` is set.
