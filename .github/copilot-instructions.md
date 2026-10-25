# Al Majid Plastic Store

- Run the app through FastAPI; do not open `index.html` as a `file://` page because the storefront depends on same-origin API routes.
- Keep product and order persistence in SQLite through `app/database.py` and API behavior in `app/main.py`.
- Keep customer catalog/cart interactions in `store.js`, admin interactions in `admin.js`, and their styles in the matching CSS files.
- Persist product descriptions and store branding in SQLite; store the optional logo through the same validated upload/media flow as product photos.
- Never hard-code administrator passwords or secrets. Provision accounts with `python -m app.create_admin` and use a persistent `SESSION_SECRET` outside local demos.
- Order totals and stock checks must be computed by the server. Do not claim payment processing or delivery is implemented.
- Escape database-controlled text before placing it into HTML templates.
- Keep CSS product illustrations local; store uploaded product photos in `data/uploads/` and allow only validated JPEG, PNG, and WebP files.
- Never serve arbitrary upload paths; image references must use generated filenames and the media route.
- Update `README.md` when setup, currency, data storage, or order capabilities change.
