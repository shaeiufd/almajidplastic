from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.environ.get("STORE_DB_PATH", PROJECT_ROOT / "data" / "store.sqlite3"))
IMAGE_DIRECTORY = DATABASE_PATH.parent / "uploads"

SAMPLE_PRODUCTS = [
    ("flex-basket", "Everyday Flex Basket", "Storage", 850, 100, "#df795f", "#f3e5d7", "basket", "Bestseller", "Terracotta"),
    ("pantry-jar", "Pantry Keeper Canister", "Kitchen", 625, 100, "#e4ca61", "#f0eed9", "canister", "Easy stack", "Sunflower"),
    ("step-stool", "Little Step Stool", "Home & garden", 1400, 100, "#648b75", "#e4eee6", "stool", "Customer pick", "Sage"),
    ("patio-planter", "Patio Planter Pot", "Home & garden", 975, 100, "#cf745d", "#f2e6dd", "planter", "New color", "Clay"),
    ("spray-bottle", "Refillable Spray Bottle", "Cleaning", 450, 100, "#85bfc0", "#e1f0ed", "bottle", "Everyday", "Sea glass"),
    ("tidy-box", "Clear-View Tidy Box", "Storage", 1250, 100, "#9bbdba", "#e9efea", "storage", "Room to spare", "Mist"),
    ("utility-pail", "Utility Carry Pail", "Cleaning", 725, 100, "#e2c75f", "#f3eed9", "bucket", "Made useful", "Marigold"),
    ("rinse-colander", "Rinse & Drain Colander", "Kitchen", 575, 100, "#d98168", "#f2e6dd", "colander", "Kitchen staple", "Coral"),
]
SAMPLE_DESCRIPTIONS = {
    "flex-basket": "A roomy, flexible basket for laundry, toys, and everyday carry.",
    "pantry-jar": "A stackable pantry container for dry goods and kitchen essentials.",
    "step-stool": "A sturdy step stool for reaching shelves and helping with household tasks.",
    "patio-planter": "A lightweight planter for herbs, flowers, and patio greenery.",
    "spray-bottle": "A refillable spray bottle for everyday cleaning and watering.",
    "tidy-box": "A clear-view box that keeps household storage easy to sort.",
    "utility-pail": "A practical carry pail for cleaning, gardening, and home projects.",
    "rinse-colander": "A kitchen colander for rinsing produce and draining ingredients.",
}
SAMPLE_ARABIC = {
    "flex-basket": ("سلة مرنة للاستخدام اليومي", "سلة واسعة ومرنة للغسيل والألعاب والاستخدامات اليومية."),
    "pantry-jar": ("وعاء تخزين للمطبخ", "وعاء قابل للتكديس لحفظ المواد الجافة ومستلزمات المطبخ."),
    "step-stool": ("مقعد درج صغير", "مقعد متين للوصول إلى الرفوف وإنجاز المهام المنزلية."),
    "patio-planter": ("أصيص للنباتات", "أصيص خفيف للأعشاب والزهور ونباتات الفناء."),
    "spray-bottle": ("زجاجة رش قابلة لإعادة التعبئة", "زجاجة رش قابلة لإعادة التعبئة للتنظيف أو ري النباتات."),
    "tidy-box": ("صندوق تخزين شفاف", "صندوق شفاف يساعدك على ترتيب الأغراض المنزلية."),
    "utility-pail": ("سطل حمل متعدد الاستخدامات", "سطل عملي للتنظيف والبستنة والمشاريع المنزلية."),
    "rinse-colander": ("مصفاة مطبخ", "مصفاة لشطف الخضروات وتصفيه المكونات."),
}
CATEGORY_ARABIC = {
    "Kitchen": "المطبخ",
    "Storage": "التخزين",
    "Cleaning": "التنظيف",
    "Home & garden": "المنزل والحديقة",
}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_ar TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                category_ar TEXT NOT NULL DEFAULT '',
                description_ar TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
                color TEXT NOT NULL,
                background_color TEXT NOT NULL,
                art TEXT NOT NULL,
                badge TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS customer_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name TEXT NOT NULL,
                password_hash TEXT,
                provider TEXT NOT NULL DEFAULT 'local',
                provider_subject TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_provider_subject
                ON customer_users(provider, provider_subject)
                WHERE provider_subject IS NOT NULL;
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name_ar TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS store_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                business_name TEXT NOT NULL DEFAULT 'Al Majid Plastic',
                business_name_ar TEXT NOT NULL DEFAULT 'الماجد للبلاستيك',
                currency TEXT NOT NULL DEFAULT 'USD',
                locale TEXT NOT NULL DEFAULT 'en-US',
                contact_email TEXT NOT NULL DEFAULT '',
                contact_phone TEXT NOT NULL DEFAULT '',
                business_address TEXT NOT NULL DEFAULT '',
                about_en TEXT NOT NULL DEFAULT '',
                about_ar TEXT NOT NULL DEFAULT '',
                about_eyebrow_en TEXT NOT NULL DEFAULT 'Our story',
                about_title_en TEXT NOT NULL DEFAULT 'Useful things, made for real life.',
                about_lead_en TEXT NOT NULL DEFAULT 'We make everyday living simpler with practical products chosen for busy homes, thoughtful routines, and lasting value.',
                about_story_eyebrow_en TEXT NOT NULL DEFAULT 'Why we exist',
                about_story_heading_en TEXT NOT NULL DEFAULT 'Everyday essentials should feel easy to choose.',
                about_story_en TEXT NOT NULL DEFAULT '',
                about_story_secondary_en TEXT NOT NULL DEFAULT 'We keep our selection focused so it is easier to find what you need, order with confidence, and enjoy products that fit naturally into your routine.',
                about_value_1_title TEXT NOT NULL DEFAULT 'Useful by design',
                about_value_1_text TEXT NOT NULL DEFAULT 'Simple products that solve everyday problems without adding clutter.',
                about_value_2_title TEXT NOT NULL DEFAULT 'Chosen with care',
                about_value_2_text TEXT NOT NULL DEFAULT 'A focused collection selected for quality, function, and lasting value.',
                about_value_3_title TEXT NOT NULL DEFAULT 'Here to help',
                about_value_3_text TEXT NOT NULL DEFAULT 'Friendly support from order request to delivery, whenever you need us.',
                owner_name TEXT NOT NULL DEFAULT '',
                owner_eyebrow_en TEXT NOT NULL DEFAULT 'The person behind the business',
                owner_role TEXT NOT NULL DEFAULT 'Founder and owner',
                owner_bio TEXT NOT NULL DEFAULT '',
                owner_image_path TEXT,
                about_primary_color TEXT NOT NULL DEFAULT '#193b3e',
                about_background_color TEXT NOT NULL DEFAULT '#dff0f1',
                about_surface_color TEXT NOT NULL DEFAULT '#f4f8f5',
                about_accent_color TEXT NOT NULL DEFAULT '#df765f',
                about_values_eyebrow_en TEXT NOT NULL DEFAULT 'What matters to us',
                about_contact_eyebrow_en TEXT NOT NULL DEFAULT 'Stay connected',
                about_contact_title_en TEXT NOT NULL DEFAULT 'Have a question?',
                about_contact_text_en TEXT NOT NULL DEFAULT 'Our team is ready to help with products, orders, and store information.',
                logo_path TEXT,
                cover_path TEXT,
                cover_fit TEXT NOT NULL DEFAULT 'cover' CHECK (cover_fit IN ('cover', 'contain')),
                low_stock_threshold INTEGER NOT NULL DEFAULT 5 CHECK (low_stock_threshold >= 0),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'confirmed', 'fulfilled', 'cancelled')),
                subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0),
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS outlets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_en TEXT NOT NULL,
                name_ar TEXT NOT NULL DEFAULT '',
                address_en TEXT NOT NULL,
                address_ar TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                hours_en TEXT NOT NULL DEFAULT '',
                hours_ar TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id TEXT NOT NULL REFERENCES products(id),
                product_name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            );
            CREATE INDEX IF NOT EXISTS idx_products_active_category ON products(active, category);
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
            """
        )
        product_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(products)")
        }
        if "image_path" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN image_path TEXT")
        if "description" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        if "name_ar" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN name_ar TEXT NOT NULL DEFAULT ''")
        if "description_ar" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN description_ar TEXT NOT NULL DEFAULT ''")
        if "category_ar" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN category_ar TEXT NOT NULL DEFAULT ''")
        category_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(categories)")
        }
        if "name_ar" not in category_columns:
            connection.execute("ALTER TABLE categories ADD COLUMN name_ar TEXT NOT NULL DEFAULT ''")
        settings_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(store_settings)")
        }
        if "business_name_ar" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN business_name_ar TEXT NOT NULL DEFAULT 'الماجد للبلاستيك'")
        if "logo_path" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN logo_path TEXT")
        if "cover_path" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN cover_path TEXT")
        if "cover_fit" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN cover_fit TEXT NOT NULL DEFAULT 'cover'")
        if "about_en" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN about_en TEXT NOT NULL DEFAULT ''")
        if "about_ar" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN about_ar TEXT NOT NULL DEFAULT ''")
        about_defaults = {
            "about_eyebrow_en": "Our story",
            "about_title_en": "Useful things, made for real life.",
            "about_lead_en": "We make everyday living simpler with practical products chosen for busy homes, thoughtful routines, and lasting value.",
            "about_story_eyebrow_en": "Why we exist",
            "about_story_heading_en": "Everyday essentials should feel easy to choose.",
            "about_story_en": "",
            "about_story_secondary_en": "We keep our selection focused so it is easier to find what you need, order with confidence, and enjoy products that fit naturally into your routine.",
            "about_value_1_title": "Useful by design",
            "about_value_1_text": "Simple products that solve everyday problems without adding clutter.",
            "about_value_2_title": "Chosen with care",
            "about_value_2_text": "A focused collection selected for quality, function, and lasting value.",
            "about_value_3_title": "Here to help",
            "about_value_3_text": "Friendly support from order request to delivery, whenever you need us.",
            "owner_name": "",
            "owner_eyebrow_en": "The person behind the business",
            "owner_role": "Founder and owner",
            "owner_bio": "",
            "about_primary_color": "#193b3e",
            "about_background_color": "#dff0f1",
            "about_surface_color": "#f4f8f5",
            "about_accent_color": "#df765f",
            "about_values_eyebrow_en": "What matters to us",
            "about_contact_eyebrow_en": "Stay connected",
            "about_contact_title_en": "Have a question?",
            "about_contact_text_en": "Our team is ready to help with products, orders, and store information.",
        }
        for column, default in about_defaults.items():
            if column not in settings_columns:
                escaped_default = default.replace("'", "''")
                connection.execute(
                    f"ALTER TABLE store_settings ADD COLUMN {column} TEXT NOT NULL DEFAULT '{escaped_default}'"
                )
        if "owner_image_path" not in settings_columns:
            connection.execute("ALTER TABLE store_settings ADD COLUMN owner_image_path TEXT")
        count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            connection.executemany(
                """INSERT INTO products
                   (id, name, category, price_cents, stock_quantity, color,
                    background_color, art, badge, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                SAMPLE_PRODUCTS,
            )
        for product_id, description in SAMPLE_DESCRIPTIONS.items():
            connection.execute(
                "UPDATE products SET description = ? WHERE id = ? AND description = ''",
                (description, product_id),
            )
        for product_id, (name_ar, description_ar) in SAMPLE_ARABIC.items():
            connection.execute(
                """UPDATE products SET name_ar = ?, description_ar = ?
                   WHERE id = ? AND name_ar = '' AND description_ar = ''""",
                (name_ar, description_ar, product_id),
            )
        connection.execute(
            """INSERT OR IGNORE INTO store_settings (id, currency, locale)
               VALUES (1, ?, ?)""",
            (os.environ.get("STORE_CURRENCY", "USD").upper(), os.environ.get("STORE_LOCALE", "en-US")),
        )
        for category_name, arabic_name in CATEGORY_ARABIC.items():
            connection.execute(
                "UPDATE categories SET name_ar = ? WHERE name = ? COLLATE NOCASE AND name_ar = ''",
                (arabic_name, category_name),
            )
        connection.execute(
            """UPDATE products SET category_ar = COALESCE(
                   (SELECT name_ar FROM categories WHERE categories.name = products.category COLLATE NOCASE), '')
               WHERE category_ar = ''"""
        )
        connection.execute(
            """INSERT OR IGNORE INTO categories (name)
               SELECT DISTINCT category FROM products WHERE TRIM(category) <> ''"""
        )


def get_product(connection: sqlite3.Connection, product_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
