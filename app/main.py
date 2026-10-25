from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
import uuid
import warnings
import csv
import json
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Annotated, AsyncIterator, Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.database import IMAGE_DIRECTORY, connect, get_product, initialize_database
from app.security import hash_password, verify_password


PROJECT_ROOT = Path(__file__).resolve().parent.parent
def load_local_env() -> None:
    env_path = PROJECT_ROOT / "app" / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

LOGGER = logging.getLogger("al_majid")
SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(48)
    LOGGER.warning("SESSION_SECRET is not set; sessions will expire when the server restarts.")

ART_STYLES = {"basket", "canister", "stool", "planter", "bottle", "storage", "bucket", "colander"}
ORDER_STATUSES = {"new", "confirmed", "fulfilled", "cancelled"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(title="Al Majid Plastic Store", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="al_majid_session",
    same_site="lax",
    https_only=os.environ.get("COOKIE_SECURE") == "1",
    max_age=60 * 60 * 12,
)


class AdminLogin(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=256)


class CustomerSignup(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class CustomerLogin(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ProductInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    name_ar: str = Field(default="", max_length=100)
    category: str = Field(min_length=2, max_length=50)
    category_ar: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=2000)
    description_ar: str = Field(default="", max_length=2000)
    price_cents: int = Field(ge=0, le=100_000_000)
    stock_quantity: int = Field(ge=0, le=1_000_000)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    art: str
    badge: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=50)
    image_path: str | None = None
    active: bool = True

    def validate_art(self) -> None:
        if self.art not in ART_STYLES:
            raise HTTPException(status_code=422, detail="Unknown product illustration style.")


class StockInput(BaseModel):
    stock_quantity: int = Field(ge=0, le=1_000_000)


class CategoryInput(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    name_ar: str = Field(default="", max_length=50)


class OutletInput(BaseModel):
    name_en: str = Field(min_length=2, max_length=100)
    name_ar: str = Field(min_length=2, max_length=100)
    address_en: str = Field(min_length=4, max_length=300)
    address_ar: str = Field(min_length=4, max_length=300)
    phone: str = Field(default="", max_length=40)
    hours_en: str = Field(default="", max_length=160)
    hours_ar: str = Field(default="", max_length=160)
    active: bool = True
    name_ar: str = Field(default="", max_length=50)


class OutletInput(BaseModel):
    name_en: str = Field(min_length=2, max_length=100)
    name_ar: str = Field(min_length=2, max_length=100)
    address_en: str = Field(min_length=4, max_length=300)
    address_ar: str = Field(min_length=4, max_length=300)
    phone: str = Field(default="", max_length=40)
    hours_en: str = Field(default="", max_length=160)
    hours_ar: str = Field(default="", max_length=160)
    active: bool = True


class StoreSettingsInput(BaseModel):
    business_name: str = Field(min_length=2, max_length=100)
    business_name_ar: str = Field(default="", max_length=100)
    about_en: str = Field(default="", max_length=2000)
    about_ar: str = Field(default="", max_length=2000)
    business_name_ar: str = Field(default="", max_length=100)
    about_en: str = Field(default="", max_length=2000)
    about_ar: str = Field(default="", max_length=2000)
    about_eyebrow_en: str = Field(default="Our story", max_length=100)
    about_title_en: str = Field(default="Useful things, made for real life.", max_length=200)
    about_lead_en: str = Field(default="", max_length=2000)
    about_story_eyebrow_en: str = Field(default="Why we exist", max_length=100)
    about_story_heading_en: str = Field(default="", max_length=200)
    about_story_en: str = Field(default="", max_length=4000)
    about_story_secondary_en: str = Field(default="", max_length=2000)
    about_value_1_title: str = Field(default="", max_length=100)
    about_value_1_text: str = Field(default="", max_length=500)
    about_value_2_title: str = Field(default="", max_length=100)
    about_value_2_text: str = Field(default="", max_length=500)
    about_value_3_title: str = Field(default="", max_length=100)
    about_value_3_text: str = Field(default="", max_length=500)
    owner_name: str = Field(default="", max_length=100)
    owner_eyebrow_en: str = Field(default="The person behind the business", max_length=150)
    owner_role: str = Field(default="Founder and owner", max_length=120)
    owner_bio: str = Field(default="", max_length=2000)
    owner_image_path: str | None = None
    about_primary_color: str = Field(default="#193b3e", pattern=r"^#[0-9a-fA-F]{6}$")
    about_background_color: str = Field(default="#dff0f1", pattern=r"^#[0-9a-fA-F]{6}$")
    about_surface_color: str = Field(default="#f4f8f5", pattern=r"^#[0-9a-fA-F]{6}$")
    about_accent_color: str = Field(default="#df765f", pattern=r"^#[0-9a-fA-F]{6}$")
    about_values_eyebrow_en: str = Field(default="What matters to us", max_length=100)
    about_contact_eyebrow_en: str = Field(default="Stay connected", max_length=100)
    about_contact_title_en: str = Field(default="Have a question?", max_length=150)
    about_contact_text_en: str = Field(default="", max_length=500)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    locale: str = Field(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    contact_email: str = Field(default="", max_length=254)
    contact_phone: str = Field(default="", max_length=40)
    business_address: str = Field(default="", max_length=500)
    logo_path: str | None = None
    cover_path: str | None = None
    cover_fit: Literal["cover", "contain"] = "cover"
    low_stock_threshold: int = Field(ge=0, le=100_000)


class OrderItemInput(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=100)


class OrderInput(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=5, max_length=40)
    delivery_address: str = Field(min_length=8, max_length=500)
    items: list[OrderItemInput] = Field(min_length=1, max_length=30)


class OrderStatusInput(BaseModel):
    status: Literal["new", "confirmed", "fulfilled", "cancelled"]


def product_response(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "name": row["name"],
        "name_ar": row["name_ar"],
        "category": row["category"],
        "category_ar": row["category_ar"],
        "description": row["description"],
        "description_ar": row["description_ar"],
        "price": row["price_cents"] / 100,
        "price_cents": row["price_cents"],
        "stock_quantity": row["stock_quantity"],
        "color": row["color"],
        "bg": row["background_color"],
        "art": row["art"],
        "badge": row["badge"],
        "note": row["note"],
        "image_path": row["image_path"],
        "image_url": f"/media/{row['image_path']}" if row["image_path"] else None,
        "active": bool(row["active"]),
    }


def require_admin(
    request: Request,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> str:
    username = request.session.get("admin")
    if not username:
        raise HTTPException(status_code=401, detail="Admin sign-in required.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        expected = request.session.get("csrf")
        if not expected or not csrf_token or not secrets.compare_digest(expected, csrf_token):
            raise HTTPException(status_code=403, detail="Request verification failed.")
    return str(username)


def customer_payload(request: Request) -> dict[str, object]:
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": str(customer_id),
        "email": str(request.session.get("customer_email", "")),
        "full_name": str(request.session.get("customer_name", "")),
        "provider": str(request.session.get("customer_provider", "local")),
    }


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def sign_in_customer(request: Request, customer: sqlite3.Row) -> dict[str, object]:
    request.session["customer_id"] = customer["id"]
    request.session["customer_email"] = customer["email"]
    request.session["customer_name"] = customer["full_name"]
    request.session["customer_provider"] = customer["provider"]
    return customer_payload(request)


def oauth_config(provider: str) -> tuple[str, str, str, str] | None:
    if provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        return (client_id, client_secret, "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token") if client_id and client_secret else None
    if provider == "facebook":
        client_id = os.environ.get("FACEBOOK_APP_ID", "")
        client_secret = os.environ.get("FACEBOOK_APP_SECRET", "")
        return (client_id, client_secret, "https://www.facebook.com/v20.0/dialog/oauth", "https://graph.facebook.com/v20.0/oauth/access_token") if client_id and client_secret else None
    return None


def oauth_redirect_uri(request: Request, provider: str) -> str:
    return str(request.base_url).rstrip("/") + f"/api/auth/{provider}/callback"


def oauth_request(url: str, data: dict[str, str]) -> dict[str, object]:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="The identity provider could not be reached.") from exc
    if not isinstance(payload, dict) or "error" in payload:
        raise HTTPException(status_code=502, detail="The identity provider rejected the sign-in.")
    return payload


def order_response(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    items = connection.execute(
        """SELECT product_id, product_name, unit_price_cents, quantity
           FROM order_items WHERE order_id = ? ORDER BY id""",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "order_number": row["order_number"],
        "customer_name": row["customer_name"],
        "email": row["email"],
        "phone": row["phone"],
        "delivery_address": row["delivery_address"],
        "status": row["status"],
        "subtotal_cents": row["subtotal_cents"],
        "currency": row["currency"],
        "created_at": row["created_at"],
        "items": [dict(item) for item in items],
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    with connect() as connection:
        connection.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/config")
def public_config() -> dict[str, str | None]:
    with connect() as connection:
        settings = connection.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()
    return {
        "business_name": settings["business_name"],
        "business_name_ar": settings["business_name_ar"],
        "about_en": settings["about_en"],
        "about_ar": settings["about_ar"],
        "about_eyebrow_en": settings["about_eyebrow_en"],
        "about_title_en": settings["about_title_en"],
        "about_lead_en": settings["about_lead_en"],
        "about_story_eyebrow_en": settings["about_story_eyebrow_en"],
        "about_story_heading_en": settings["about_story_heading_en"],
        "about_story_en": settings["about_story_en"],
        "about_story_secondary_en": settings["about_story_secondary_en"],
        "about_value_1_title": settings["about_value_1_title"],
        "about_value_1_text": settings["about_value_1_text"],
        "about_value_2_title": settings["about_value_2_title"],
        "about_value_2_text": settings["about_value_2_text"],
        "about_value_3_title": settings["about_value_3_title"],
        "about_value_3_text": settings["about_value_3_text"],
        "owner_name": settings["owner_name"],
        "owner_eyebrow_en": settings["owner_eyebrow_en"],
        "owner_role": settings["owner_role"],
        "owner_bio": settings["owner_bio"],
        "owner_image_url": f"/media/{settings['owner_image_path']}" if settings["owner_image_path"] else None,
        "about_primary_color": settings["about_primary_color"],
        "about_background_color": settings["about_background_color"],
        "about_surface_color": settings["about_surface_color"],
        "about_accent_color": settings["about_accent_color"],
        "about_values_eyebrow_en": settings["about_values_eyebrow_en"],
        "about_contact_eyebrow_en": settings["about_contact_eyebrow_en"],
        "about_contact_title_en": settings["about_contact_title_en"],
        "about_contact_text_en": settings["about_contact_text_en"],
        "currency": settings["currency"] if re.fullmatch(r"[A-Z]{3}", settings["currency"]) else "USD",
        "locale": settings["locale"] if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", settings["locale"]) else "en-US",
        "contact_email": settings["contact_email"],
        "contact_phone": settings["contact_phone"],
        "business_address": settings["business_address"],
        "logo_url": f"/media/{settings['logo_path']}" if settings["logo_path"] else None,
        "cover_url": f"/media/{settings['cover_path']}" if settings["cover_path"] else None,
        "cover_fit": settings["cover_fit"],
    }


@app.get("/api/products")
def list_products() -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM products WHERE active = 1 ORDER BY rowid"
        ).fetchall()
    return [product_response(row) for row in rows]


@app.get("/api/outlets")
def public_outlets() -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name_en, name_ar, address_en, address_ar, phone, hours_en, hours_ar FROM outlets WHERE active = 1 ORDER BY name_en"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderInput) -> dict[str, object]:
    if "@" not in payload.email or payload.email.startswith("@") or payload.email.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")

    requested: dict[str, int] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(item.product_id, 0) + item.quantity
    if any(quantity > 100 for quantity in requested.values()):
        raise HTTPException(status_code=422, detail="Maximum quantity per product is 100.")

    order_id = uuid.uuid4().hex
    order_number = f"AM-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(3).upper()}"
    subtotal_cents = 0
    snapshots: list[tuple[str, str, int, int]] = []

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        currency = connection.execute(
            "SELECT currency FROM store_settings WHERE id = 1"
        ).fetchone()[0]
        for product_id, quantity in requested.items():
            product = connection.execute(
                "SELECT * FROM products WHERE id = ? AND active = 1", (product_id,)
            ).fetchone()
            if product is None:
                raise HTTPException(status_code=404, detail="A selected product is no longer available.")
            if product["stock_quantity"] < quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Not enough stock for {product['name']}. Available: {product['stock_quantity']}.",
                )
            price_cents = int(product["price_cents"])
            subtotal_cents += price_cents * quantity
            snapshots.append((product_id, product["name"], price_cents, quantity))

        connection.execute(
            """INSERT INTO orders
               (id, order_number, customer_name, email, phone, delivery_address,
                status, subtotal_cents, currency)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
            (
                order_id,
                order_number,
                payload.customer_name.strip(),
                payload.email.strip().lower(),
                payload.phone.strip(),
                payload.delivery_address.strip(),
                subtotal_cents,
                currency,
            ),
        )
        for product_id, product_name, price_cents, quantity in snapshots:
            connection.execute(
                """UPDATE products SET stock_quantity = stock_quantity - ?,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ? AND stock_quantity >= ?""",
                (quantity, product_id, quantity),
            )
            connection.execute(
                """INSERT INTO order_items
                   (order_id, product_id, product_name, unit_price_cents, quantity)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, product_id, product_name, price_cents, quantity),
            )

    return {
        "id": order_id,
        "order_number": order_number,
        "status": "new",
        "subtotal_cents": subtotal_cents,
        "currency": currency,
    }


@app.get("/api/auth/me")
def customer_session(request: Request) -> dict[str, object]:
    return customer_payload(request)


@app.post("/api/auth/signup", status_code=status.HTTP_201_CREATED)
def customer_signup(payload: CustomerSignup, request: Request) -> dict[str, object]:
    email = payload.email.strip().lower()
    name = payload.full_name.strip()
    if not valid_email(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Enter your full name.")
    customer_id = uuid.uuid4().hex
    try:
        with connect() as connection:
            connection.execute(
                "INSERT INTO customer_users (id, email, full_name, password_hash) VALUES (?, ?, ?, ?)",
                (customer_id, email, name, hash_password(payload.password)),
            )
            customer = connection.execute("SELECT * FROM customer_users WHERE id = ?", (customer_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from None
    request.session.clear()
    return sign_in_customer(request, customer)


@app.post("/api/auth/login")
def customer_login(payload: CustomerLogin, request: Request) -> dict[str, object]:
    email = payload.email.strip().lower()
    with connect() as connection:
        customer = connection.execute("SELECT * FROM customer_users WHERE email = ?", (email,)).fetchone()
    if customer is None or not customer["password_hash"] or not verify_password(payload.password, customer["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    request.session.clear()
    return sign_in_customer(request, customer)


@app.post("/api/auth/logout")
def customer_logout(request: Request) -> dict[str, str]:
    request.session.pop("customer_id", None)
    request.session.pop("customer_email", None)
    request.session.pop("customer_name", None)
    request.session.pop("customer_provider", None)
    return {"status": "signed out"}


@app.get("/api/auth/{provider}/start")
def oauth_start(provider: Literal["google", "facebook"], request: Request) -> RedirectResponse:
    config = oauth_config(provider)
    if config is None:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured.")
    client_id, _, auth_url, _ = config
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    query = {
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(request, provider),
        "response_type": "code",
        "state": state,
    }
    if provider == "google":
        query.update({"scope": "openid email profile", "access_type": "online", "prompt": "select_account"})
    else:
        query["scope"] = "email,public_profile"
    return RedirectResponse(auth_url + "?" + urllib.parse.urlencode(query), status_code=307)


@app.get("/api/auth/{provider}/callback")
def oauth_callback(provider: Literal["google", "facebook"], request: Request) -> RedirectResponse:
    config = oauth_config(provider)
    if config is None:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured.")
    state = request.query_params.get("state", "")
    expected_state = request.session.pop("oauth_state", "")
    if not expected_state or not state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Sign-in session expired. Please try again.")
    code = request.query_params.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="The identity provider did not return a sign-in code.")
    client_id, client_secret, _, token_url = config
    token = oauth_request(token_url, {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": oauth_redirect_uri(request, provider),
        "grant_type": "authorization_code",
    })
    access_token = str(token.get("access_token", ""))
    if not access_token:
        raise HTTPException(status_code=502, detail="The identity provider did not return an access token.")
    if provider == "google":
        profile_request = urllib.request.Request("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
    else:
        profile_request = urllib.request.Request("https://graph.facebook.com/me?fields=id,name,email", headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(profile_request, timeout=10) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not read your identity provider profile.") from exc
    email = str(profile.get("email", "")).strip().lower()
    subject = str(profile.get("sub") or profile.get("id") or "").strip()
    name = str(profile.get("name") or profile.get("given_name") or "Customer").strip()
    if not valid_email(email) or not subject:
        raise HTTPException(status_code=422, detail="The provider did not share a usable email address.")
    with connect() as connection:
        customer = connection.execute("SELECT * FROM customer_users WHERE provider = ? AND provider_subject = ?", (provider, subject)).fetchone()
        if customer is None:
            customer = connection.execute("SELECT * FROM customer_users WHERE email = ?", (email,)).fetchone()
            if customer is None:
                customer_id = uuid.uuid4().hex
                connection.execute("INSERT INTO customer_users (id, email, full_name, provider, provider_subject) VALUES (?, ?, ?, ?, ?)", (customer_id, email, name[:100], provider, subject))
            else:
                connection.execute("UPDATE customer_users SET provider = ?, provider_subject = ?, full_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (provider, subject, name[:100], customer["id"]))
            customer = connection.execute("SELECT * FROM customer_users WHERE email = ?", (email,)).fetchone()
    request.session.clear()
    sign_in_customer(request, customer)
    return RedirectResponse("/?signed_in=1", status_code=303)


@app.post("/api/admin/login")
def admin_login(payload: AdminLogin, request: Request) -> dict[str, str]:
    with connect() as connection:
        user = connection.execute(
            "SELECT username, password_hash FROM admin_users WHERE username = ?",
            (payload.username.strip(),),
        ).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")

    request.session.clear()
    request.session["admin"] = user["username"]
    request.session["csrf"] = secrets.token_urlsafe(32)
    return {"username": user["username"], "csrf_token": request.session["csrf"]}


@app.get("/api/admin/session")
def admin_session(request: Request) -> dict[str, object]:
    username = request.session.get("admin")
    if not username:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": str(username),
        "csrf_token": str(request.session["csrf"]),
    }


@app.post("/api/admin/logout")
def admin_logout(
    _: Annotated[str, Depends(require_admin)], request: Request
) -> dict[str, str]:
    request.session.clear()
    return {"status": "signed out"}


@app.get("/api/admin/summary")
def admin_summary(_: Annotated[str, Depends(require_admin)]) -> dict[str, int]:
    with connect() as connection:
        total_products = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        low_stock = connection.execute(
            """SELECT COUNT(*) FROM products, store_settings
               WHERE products.active = 1 AND products.stock_quantity <= store_settings.low_stock_threshold
               AND store_settings.id = 1"""
        ).fetchone()[0]
        new_orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'new'"
        ).fetchone()[0]
        total_orders = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return {
        "total_products": total_products,
        "low_stock": low_stock,
        "new_orders": new_orders,
        "total_orders": total_orders,
    }


@app.get("/api/categories")
def public_categories() -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, name_ar FROM categories WHERE active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/admin/categories")
def admin_categories(_: Annotated[str, Depends(require_admin)]) -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, name_ar, active FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [{**dict(row), "active": bool(row["active"])} for row in rows]


@app.post("/api/admin/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryInput, _: Annotated[str, Depends(require_admin)]
) -> dict[str, object]:
    name = payload.name.strip()
    name_ar = payload.name_ar.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Category name must contain at least 2 characters.")
    try:
        with connect() as connection:
            result = connection.execute("INSERT INTO categories (name, name_ar) VALUES (?, ?)", (name, name_ar))
            category_id = result.lastrowid
            category = connection.execute(
                "SELECT id, name, name_ar, active FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="That category already exists.") from None
    return {**dict(category), "active": bool(category["active"])}


@app.put("/api/admin/categories/{category_id}")
def rename_category(
    category_id: int,
    payload: CategoryInput,
    _: Annotated[str, Depends(require_admin)],
) -> dict[str, object]:
    name = payload.name.strip()
    name_ar = payload.name_ar.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Category name must contain at least 2 characters.")
    try:
        with connect() as connection:
            category = connection.execute(
                "SELECT name, name_ar FROM categories WHERE id = ? AND active = 1", (category_id,)
            ).fetchone()
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found.")
            connection.execute(
                "UPDATE products SET category = ?, category_ar = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ? COLLATE NOCASE",
                (name, name_ar or category["name_ar"], category["name"]),
            )
            connection.execute("UPDATE categories SET name = ?, name_ar = ? WHERE id = ?", (name, name_ar, category_id))
            updated = connection.execute(
                "SELECT id, name, name_ar, active FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="That category already exists.") from None
    return {**dict(updated), "active": bool(updated["active"])}


@app.delete("/api/admin/categories/{category_id}")
def archive_category(
    category_id: int, _: Annotated[str, Depends(require_admin)]
) -> dict[str, str]:
    with connect() as connection:
        category = connection.execute(
            "SELECT name FROM categories WHERE id = ? AND active = 1", (category_id,)
        ).fetchone()
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found.")
        product_count = connection.execute(
            "SELECT COUNT(*) FROM products WHERE category = ? COLLATE NOCASE",
            (category["name"],),
        ).fetchone()[0]
        if product_count:
            raise HTTPException(
                status_code=409,
                detail="Move or archive its products before removing this category.",
            )
        connection.execute("UPDATE categories SET active = 0 WHERE id = ?", (category_id,))
    return {"status": "archived"}


@app.get("/api/admin/settings")
def admin_settings(_: Annotated[str, Depends(require_admin)]) -> dict[str, object]:
    with connect() as connection:
        settings = connection.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()
    return settings_response(settings)


def settings_response(settings: sqlite3.Row) -> dict[str, object]:
    result = dict(settings)
    result["logo_url"] = f"/media/{settings['logo_path']}" if settings["logo_path"] else None
    result["cover_url"] = f"/media/{settings['cover_path']}" if settings["cover_path"] else None
    return result


@app.put("/api/admin/settings")
def update_settings(
    payload: StoreSettingsInput, _: Annotated[str, Depends(require_admin)]
) -> dict[str, object]:
    values = payload.model_dump()
    for key in ("business_name", "business_name_ar", "about_en", "about_ar", "about_eyebrow_en", "about_title_en", "about_lead_en", "about_story_eyebrow_en", "about_story_heading_en", "about_story_en", "about_story_secondary_en", "about_value_1_title", "about_value_1_text", "about_value_2_title", "about_value_2_text", "about_value_3_title", "about_value_3_text", "owner_name", "owner_eyebrow_en", "owner_role", "owner_bio", "about_values_eyebrow_en", "about_contact_eyebrow_en", "about_contact_title_en", "about_contact_text_en", "locale", "contact_email", "contact_phone", "business_address"):
        values[key] = values[key].strip()
    if values["contact_email"] and (
        "@" not in values["contact_email"]
        or values["contact_email"].startswith("@")
        or values["contact_email"].endswith("@")
    ):
        raise HTTPException(status_code=422, detail="Enter a valid contact email address.")
    if values["logo_path"] is not None and (
        not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", values["logo_path"])
        or not (IMAGE_DIRECTORY / values["logo_path"]).is_file()
    ):
        raise HTTPException(status_code=422, detail="Upload a valid logo image before saving.")
    if values["cover_path"] is not None and (
        not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", values["cover_path"])
        or not (IMAGE_DIRECTORY / values["cover_path"]).is_file()
    ):
        raise HTTPException(status_code=422, detail="Upload a valid cover image before saving.")
    if values["owner_image_path"] is not None and (
        not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", values["owner_image_path"])
        or not (IMAGE_DIRECTORY / values["owner_image_path"]).is_file()
    ):
        raise HTTPException(status_code=422, detail="Upload a valid owner image before saving.")
    with connect() as connection:
        connection.execute(
            """UPDATE store_settings SET business_name = ?, business_name_ar = ?, about_en = ?, about_ar = ?,
               about_eyebrow_en = ?, about_title_en = ?, about_lead_en = ?, about_story_eyebrow_en = ?, about_story_heading_en = ?, about_story_en = ?, about_story_secondary_en = ?,
               about_value_1_title = ?, about_value_1_text = ?, about_value_2_title = ?, about_value_2_text = ?, about_value_3_title = ?, about_value_3_text = ?,
               owner_name = ?, owner_eyebrow_en = ?, owner_role = ?, owner_bio = ?, owner_image_path = ?,
               about_primary_color = ?, about_background_color = ?, about_surface_color = ?, about_accent_color = ?,
               about_values_eyebrow_en = ?, about_contact_eyebrow_en = ?, about_contact_title_en = ?, about_contact_text_en = ?,
               currency = ?, locale = ?, contact_email = ?, contact_phone = ?, business_address = ?,
               logo_path = ?, cover_path = ?, cover_fit = ?, low_stock_threshold = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1""",
            tuple(values[key] for key in (
                "business_name", "business_name_ar", "about_en", "about_ar", "about_eyebrow_en", "about_title_en", "about_lead_en", "about_story_eyebrow_en", "about_story_heading_en", "about_story_en", "about_story_secondary_en",
                "about_value_1_title", "about_value_1_text", "about_value_2_title", "about_value_2_text", "about_value_3_title", "about_value_3_text", "owner_name", "owner_eyebrow_en", "owner_role", "owner_bio", "owner_image_path",
                "about_primary_color", "about_background_color", "about_surface_color", "about_accent_color", "about_values_eyebrow_en", "about_contact_eyebrow_en", "about_contact_title_en", "about_contact_text_en", "currency", "locale", "contact_email", "contact_phone", "business_address", "logo_path", "cover_path", "cover_fit", "low_stock_threshold"
            )),
        )
        settings = connection.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()
    return settings_response(settings)


@app.get("/api/admin/products")
def admin_products(_: Annotated[str, Depends(require_admin)]) -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM products ORDER BY name").fetchall()
    return [product_response(row) for row in rows]


@app.get("/api/admin/outlets")
def admin_outlets(_: Annotated[str, Depends(require_admin)]) -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM outlets ORDER BY name_en").fetchall()
    return [{**dict(row), "active": bool(row["active"])} for row in rows]


@app.post("/api/admin/outlets", status_code=status.HTTP_201_CREATED)
def create_outlet(
    payload: OutletInput, _: Annotated[str, Depends(require_admin)]
) -> dict[str, object]:
    values = payload.model_dump()
    for key, value in values.items():
        if isinstance(value, str):
            values[key] = value.strip()
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO outlets (name_en, name_ar, address_en, address_ar, phone, hours_en, hours_ar, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(values[key] for key in ("name_en", "name_ar", "address_en", "address_ar", "phone", "hours_en", "hours_ar")) + (int(values["active"]),),
        )
        row = connection.execute("SELECT * FROM outlets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return {**dict(row), "active": bool(row["active"])}


@app.put("/api/admin/outlets/{outlet_id}")
def update_outlet(
    outlet_id: int,
    payload: OutletInput,
    _: Annotated[str, Depends(require_admin)],
) -> dict[str, object]:
    values = payload.model_dump()
    for key, value in values.items():
        if isinstance(value, str):
            values[key] = value.strip()
    with connect() as connection:
        result = connection.execute(
            """UPDATE outlets SET name_en = ?, name_ar = ?, address_en = ?, address_ar = ?,
               phone = ?, hours_en = ?, hours_ar = ?, active = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            tuple(values[key] for key in ("name_en", "name_ar", "address_en", "address_ar", "phone", "hours_en", "hours_ar")) + (int(values["active"]), outlet_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Outlet not found.")
        row = connection.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,)).fetchone()
    return {**dict(row), "active": bool(row["active"])}


@app.delete("/api/admin/outlets/{outlet_id}")
def archive_outlet(
    outlet_id: int, _: Annotated[str, Depends(require_admin)]
) -> dict[str, str]:
    with connect() as connection:
        result = connection.execute(
            "UPDATE outlets SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (outlet_id,),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Outlet not found.")
    return {"status": "archived"}


def product_values(payload: ProductInput) -> tuple[object, ...]:
    payload.validate_art()
    with connect() as connection:
        category = connection.execute(
            "SELECT name_ar FROM categories WHERE name = ? COLLATE NOCASE AND active = 1",
            (payload.category.strip(),),
        ).fetchone()
    if category is None:
        raise HTTPException(status_code=422, detail="Choose an active product category.")
    if payload.image_path is not None:
        if not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", payload.image_path):
            raise HTTPException(status_code=422, detail="Invalid product image reference.")
        if not (IMAGE_DIRECTORY / payload.image_path).is_file():
            raise HTTPException(status_code=422, detail="Upload the product image before saving.")
    return (
        payload.name.strip(),
        payload.name_ar.strip(),
        payload.category.strip(),
        payload.category_ar.strip() or category["name_ar"],
        payload.description.strip(),
        payload.description_ar.strip(),
        payload.price_cents,
        payload.stock_quantity,
        payload.color,
        payload.background_color,
        payload.art,
        payload.badge.strip(),
        payload.note.strip(),
        payload.image_path,
        int(payload.active),
    )


@app.post("/api/admin/uploads", status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    _: Annotated[str, Depends(require_admin)],
    file: UploadFile = File(...),
) -> dict[str, str]:
    try:
        content = await file.read(MAX_IMAGE_SIZE + 1)
        if not content:
            raise HTTPException(status_code=400, detail="The selected image is empty.")
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail="Images must be 5 MB or smaller.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    detected_format = image.format
                    width, height = image.size
                    image.verify()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(status_code=413, detail="Images must be 20 megapixels or smaller.") from None
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=415,
                detail="This file is not a valid JPEG, PNG, or WebP image. Re-save it in one of those formats and try again.",
            ) from None
        image_format = IMAGE_FORMATS.get(detected_format or "")
        if image_format is None:
            raise HTTPException(
                status_code=415,
                detail="This image format is not supported. Use JPEG, PNG, or WebP.",
            )
        if width * height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=413, detail="Images must be 20 megapixels or smaller.")
        extension, media_type = image_format
        filename = f"{secrets.token_hex(16)}{extension}"
        IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        (IMAGE_DIRECTORY / filename).write_bytes(content)
        return {"image_path": filename, "image_url": f"/media/{filename}", "media_type": media_type}
    finally:
        await file.close()


@app.post("/api/admin/products", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductInput, _: Annotated[str, Depends(require_admin)]
) -> dict[str, object]:
    product_id = f"{re.sub(r'[^a-z0-9]+', '-', payload.name.lower()).strip('-')[:45]}-{uuid.uuid4().hex[:6]}"
    values = product_values(payload)
    with connect() as connection:
        connection.execute(
            """INSERT INTO products
               (id, name, name_ar, category, category_ar, description, description_ar, price_cents, stock_quantity, color,
                     background_color, art, badge, note, image_path, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (product_id, *values),
        )
        product = get_product(connection, product_id)
    return product_response(product)


@app.put("/api/admin/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductInput,
    _: Annotated[str, Depends(require_admin)],
) -> dict[str, object]:
    values = product_values(payload)
    with connect() as connection:
        result = connection.execute(
                """UPDATE products SET name = ?, name_ar = ?, category = ?, category_ar = ?,
                    description = ?, description_ar = ?, price_cents = ?, stock_quantity = ?,
                    color = ?, background_color = ?, art = ?,
               badge = ?, note = ?, image_path = ?, active = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (*values, product_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        product = get_product(connection, product_id)
    return product_response(product)


@app.patch("/api/admin/products/{product_id}/stock")
def adjust_product_stock(
    product_id: str,
    payload: StockInput,
    _: Annotated[str, Depends(require_admin)],
) -> dict[str, object]:
    with connect() as connection:
        result = connection.execute(
            """UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (payload.stock_quantity, product_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        product = get_product(connection, product_id)
    return product_response(product)


@app.delete("/api/admin/products/{product_id}")
def archive_product(
    product_id: str, _: Annotated[str, Depends(require_admin)]
) -> dict[str, str]:
    with connect() as connection:
        result = connection.execute(
            "UPDATE products SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (product_id,),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
    return {"status": "archived"}


@app.get("/api/admin/orders")
def admin_orders(
    _: Annotated[str, Depends(require_admin)],
    order_status: str | None = None,
) -> list[dict[str, object]]:
    if order_status is not None and order_status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail="Unknown order status.")
    with connect() as connection:
        if order_status:
            rows = connection.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                (order_status,),
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        return [order_response(connection, row) for row in rows]


@app.get("/api/admin/orders/{order_id}")
def admin_order_detail(
    order_id: str, _: Annotated[str, Depends(require_admin)]
) -> dict[str, object]:
    with connect() as connection:
        row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        return order_response(connection, row)


@app.get("/api/admin/customers")
def admin_customers(_: Annotated[str, Depends(require_admin)]) -> list[dict[str, object]]:
    with connect() as connection:
        customers = connection.execute(
            """SELECT LOWER(email) AS email, MAX(customer_name) AS customer_name,
                      MAX(phone) AS phone, COUNT(*) AS order_count,
                      SUM(subtotal_cents) AS total_order_value_cents,
                      MAX(created_at) AS last_order_at
               FROM orders GROUP BY LOWER(email) ORDER BY MAX(created_at) DESC"""
        ).fetchall()
        results: list[dict[str, object]] = []
        for customer in customers:
            order_rows = connection.execute(
                "SELECT * FROM orders WHERE LOWER(email) = ? ORDER BY created_at DESC",
                (customer["email"],),
            ).fetchall()
            results.append(
                {
                    "email": customer["email"],
                    "customer_name": customer["customer_name"],
                    "phone": customer["phone"],
                    "order_count": customer["order_count"],
                    "total_order_value_cents": customer["total_order_value_cents"],
                    "last_order_at": customer["last_order_at"],
                    "orders": [order_response(connection, row) for row in order_rows],
                }
            )
    return results


def safe_csv_value(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def csv_response(filename: str, columns: list[str], rows: list[list[object]]) -> Response:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows([[safe_csv_value(value) for value in row] for row in rows])
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/exports/products.csv")
def export_products_csv(_: Annotated[str, Depends(require_admin)]) -> Response:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM products ORDER BY name").fetchall()
    return csv_response(
        "products.csv",
        ["id", "name", "description", "category", "price_cents", "stock_quantity", "active", "image_url"],
        [
            [row["id"], row["name"], row["description"], row["category"], row["price_cents"], row["stock_quantity"],
             bool(row["active"]), f"/media/{row['image_path']}" if row["image_path"] else ""]
            for row in rows
        ],
    )


@app.get("/api/admin/exports/orders.csv")
def export_orders_csv(_: Annotated[str, Depends(require_admin)]) -> Response:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        orders = [order_response(connection, row) for row in rows]
    return csv_response(
        "orders.csv",
        ["order_number", "created_at", "status", "customer_name", "email", "phone",
         "delivery_address", "items", "subtotal_cents", "currency"],
        [
            [order["order_number"], order["created_at"], order["status"], order["customer_name"],
             order["email"], order["phone"], order["delivery_address"],
             "; ".join(f"{item['quantity']} x {item['product_name']}" for item in order["items"]),
             order["subtotal_cents"], order["currency"]]
            for order in orders
        ],
    )


@app.get("/api/admin/exports/customers.csv")
def export_customers_csv(_: Annotated[str, Depends(require_admin)]) -> Response:
    customers = admin_customers(_)
    return csv_response(
        "customers.csv",
        ["customer_name", "email", "phone", "order_count", "total_order_value_cents", "last_order_at"],
        [[customer[key] for key in ("customer_name", "email", "phone", "order_count", "total_order_value_cents", "last_order_at")] for customer in customers],
    )


@app.patch("/api/admin/orders/{order_id}")
def update_order_status(
    order_id: str,
    payload: OrderStatusInput,
    _: Annotated[str, Depends(require_admin)],
) -> dict[str, object]:
    transitions = {
        "new": {"confirmed", "cancelled"},
        "confirmed": {"fulfilled", "cancelled"},
        "fulfilled": set(),
        "cancelled": set(),
    }
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if payload.status not in transitions[order["status"]]:
            raise HTTPException(status_code=409, detail="That order status change is not allowed.")
        if payload.status == "cancelled":
            items = connection.execute(
                "SELECT product_id, quantity FROM order_items WHERE order_id = ?",
                (order_id,),
            ).fetchall()
            for item in items:
                connection.execute(
                    """UPDATE products SET stock_quantity = stock_quantity + ?,
                       updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (item["quantity"], item["product_id"]),
                )
        connection.execute("UPDATE orders SET status = ? WHERE id = ?", (payload.status, order_id))
        updated = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return order_response(connection, updated)


@app.get("/", include_in_schema=False)
def storefront() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/about", include_in_schema=False)
def about_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "about.html", headers={"Cache-Control": "no-store"})


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "admin.html", headers={"Cache-Control": "no-store"})


@app.get("/styles.css", include_in_schema=False)
def storefront_styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "styles.css", media_type="text/css", headers={"Cache-Control": "no-store"})


@app.get("/store.js", include_in_schema=False)
def storefront_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "store.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/about.css", include_in_schema=False)
def about_styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "about.css", media_type="text/css", headers={"Cache-Control": "no-store"})


@app.get("/about.js", include_in_schema=False)
def about_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "about.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/admin.css", include_in_schema=False)
def admin_styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "admin.css", media_type="text/css", headers={"Cache-Control": "no-store"})


@app.get("/admin.js", include_in_schema=False)
def admin_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "admin.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/media/{filename}", include_in_schema=False)
def product_image(filename: str) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", filename):
        raise HTTPException(status_code=404, detail="Image not found.")
    path = IMAGE_DIRECTORY / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    media_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )
