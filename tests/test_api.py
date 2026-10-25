from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image


_TEST_DIRECTORY = tempfile.TemporaryDirectory()
os.environ["STORE_DB_PATH"] = str(Path(_TEST_DIRECTORY.name) / "tests.sqlite3")
os.environ["SESSION_SECRET"] = "unit-test-session-secret-not-for-production"

from fastapi.testclient import TestClient

from app.database import SAMPLE_PRODUCTS, connect
from app.main import app
from app.security import hash_password


class StoreApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.client.__enter__()
        with connect() as connection:
            connection.execute("DELETE FROM order_items")
            connection.execute("DELETE FROM orders")
            connection.execute("DELETE FROM admin_users")
            connection.execute("DELETE FROM categories")
            seed_ids = tuple(product[0] for product in SAMPLE_PRODUCTS)
            placeholders = ", ".join("?" for _ in seed_ids)
            connection.execute(
                f"DELETE FROM products WHERE id NOT IN ({placeholders})", seed_ids
            )
            connection.execute(
                "UPDATE products SET stock_quantity = 100, active = 1 WHERE id NOT LIKE 'test-%'"
            )
            for product in SAMPLE_PRODUCTS:
                connection.execute("UPDATE products SET category = ? WHERE id = ?", (product[2], product[0]))
            connection.execute(
                "INSERT INTO categories (name) SELECT DISTINCT category FROM products"
            )
            connection.execute(
                """UPDATE store_settings SET business_name = 'Al Majid Plastic', currency = 'USD',
                   locale = 'en-US', contact_email = '', contact_phone = '', business_address = '',
                   low_stock_threshold = 5 WHERE id = 1"""
            )
            connection.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                ("owner", hash_password("test-password-12")),
            )

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def sign_in(self) -> dict[str, str]:
        response = self.client.post(
            "/api/admin/login",
            json={"username": "owner", "password": "test-password-12"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def create_order(
        self,
        items: list[dict[str, Any]],
        customer_name: str = "Sample Customer",
        email: str = "sample@example.com",
    ) -> Any:
        return self.client.post(
            "/api/orders",
            json={
                "customer_name": customer_name,
                "email": email,
                "phone": "555-0199",
                "delivery_address": "123 Sample Street, Sample City",
                "items": items,
            },
        )

    def test_catalog_and_order_use_server_prices(self) -> None:
        products = self.client.get("/api/products").json()
        self.assertEqual(len(products), 8)
        basket = next(product for product in products if product["id"] == "flex-basket")
        self.assertIn("flexible basket", basket["description"].lower())
        order = self.create_order([{"product_id": "flex-basket", "quantity": 2}])
        self.assertEqual(order.status_code, 201, order.text)
        self.assertEqual(order.json()["subtotal_cents"], 1700)
        with connect() as connection:
            stock = connection.execute(
                "SELECT stock_quantity FROM products WHERE id = 'flex-basket'"
            ).fetchone()[0]
        self.assertEqual(stock, 98)

    def test_stock_conflict_does_not_partially_create_order(self) -> None:
        with connect() as connection:
            connection.execute(
                "UPDATE products SET stock_quantity = 0 WHERE id = 'pantry-jar'"
            )
        response = self.create_order(
            [
                {"product_id": "flex-basket", "quantity": 1},
                {"product_id": "pantry-jar", "quantity": 1},
            ]
        )
        self.assertEqual(response.status_code, 409)
        with connect() as connection:
            order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            basket_stock = connection.execute(
                "SELECT stock_quantity FROM products WHERE id = 'flex-basket'"
            ).fetchone()[0]
        self.assertEqual(order_count, 0)
        self.assertEqual(basket_stock, 100)

    def test_admin_auth_csrf_and_product_management(self) -> None:
        self.assertEqual(self.client.get("/api/admin/products").status_code, 401)
        session = self.client.get("/api/admin/session")
        self.assertEqual(session.status_code, 200)
        self.assertFalse(session.json()["authenticated"])
        headers = self.sign_in()
        payload = {
            "name": "Test Storage Box",
            "name_ar": "صندوق تخزين تجريبي",
            "category": "Storage",
            "category_ar": "التخزين",
            "description": "A useful test box for shelves.",
            "description_ar": "صندوق مفيد للأرفف.",
            "price_cents": 1250,
            "stock_quantity": 12,
            "color": "#557799",
            "background_color": "#e0eeee",
            "art": "storage",
            "badge": "New",
            "note": "Blue",
            "active": True,
        }
        self.assertEqual(self.client.post("/api/admin/products", json=payload).status_code, 403)
        created = self.client.post("/api/admin/products", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["description"], "A useful test box for shelves.")
        self.assertEqual(created.json()["name_ar"], "صندوق تخزين تجريبي")
        product_id = created.json()["id"]
        payload["price_cents"] = 1350
        updated = self.client.put(
            f"/api/admin/products/{product_id}", json=payload, headers=headers
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["price_cents"], 1350)
        stock_update = self.client.patch(
            f"/api/admin/products/{product_id}/stock",
            json={"stock_quantity": 7},
            headers=headers,
        )
        self.assertEqual(stock_update.status_code, 200, stock_update.text)
        self.assertEqual(stock_update.json()["stock_quantity"], 7)
        archived = self.client.delete(f"/api/admin/products/{product_id}", headers=headers)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertFalse(
            next(item for item in self.client.get("/api/admin/products", headers=headers).json()
                 if item["id"] == product_id)["active"]
        )

    def test_cancelling_order_restores_stock(self) -> None:
        order = self.create_order([{"product_id": "flex-basket", "quantity": 3}])
        self.assertEqual(order.status_code, 201, order.text)
        response = self.client.patch(
            f"/api/admin/orders/{order.json()['id']}",
            json={"status": "cancelled"},
            headers=self.sign_in(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        with connect() as connection:
            stock = connection.execute(
                "SELECT stock_quantity FROM products WHERE id = 'flex-basket'"
            ).fetchone()[0]
        self.assertEqual(stock, 100)

    def test_admin_upload_saves_and_serves_product_image(self) -> None:
        headers = self.sign_in()
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), "red").save(image_buffer, format="PNG")
        valid_png = image_buffer.getvalue()
        denied = self.client.post(
            "/api/admin/uploads",
            files={"file": ("photo.png", valid_png, "image/png")},
        )
        self.assertEqual(denied.status_code, 403)
        invalid = self.client.post(
            "/api/admin/uploads",
            files={"file": ("photo.png", b"not an image", "image/png")},
            headers=headers,
        )
        self.assertEqual(invalid.status_code, 415)

        uploaded = self.client.post(
            "/api/admin/uploads",
            files={"file": ("photo.jpg", valid_png, "image/jpeg")},
            headers=headers,
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        image_path = uploaded.json()["image_path"]
        self.assertTrue(image_path.endswith(".png"))
        self.assertEqual(uploaded.json()["media_type"], "image/png")
        product = self.client.post(
            "/api/admin/products",
            json={
                "name": "Photo Product",
                "category": "Storage",
                "price_cents": 750,
                "stock_quantity": 3,
                "color": "#557799",
                "background_color": "#e0eeee",
                "art": "storage",
                "image_path": image_path,
            },
            headers=headers,
        )
        self.assertEqual(product.status_code, 201, product.text)
        self.assertEqual(product.json()["image_url"], f"/media/{image_path}")
        served = self.client.get(product.json()["image_url"])
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.headers["content-type"], "image/png")
        self.assertEqual(served.headers["x-content-type-options"], "nosniff")
        settings_payload = {
            "business_name": "Al Majid Plastic",
            "currency": "USD",
            "locale": "en-US",
            "contact_email": "",
            "contact_phone": "",
            "business_address": "",
            "logo_path": image_path,
            "low_stock_threshold": 5,
        }
        saved_settings = self.client.put(
            "/api/admin/settings", json=settings_payload, headers=headers
        )
        self.assertEqual(saved_settings.status_code, 200, saved_settings.text)
        self.assertEqual(saved_settings.json()["logo_url"], f"/media/{image_path}")
        settings_payload["logo_path"] = "../../outside.png"
        invalid_logo = self.client.put(
            "/api/admin/settings", json=settings_payload, headers=headers
        )
        self.assertEqual(invalid_logo.status_code, 422)

    def test_categories_can_be_managed_and_products_follow_renames(self) -> None:
        headers = self.sign_in()
        created = self.client.post(
            "/api/admin/categories", json={"name": "Outdoor Living"}, headers=headers
        )
        self.assertEqual(created.status_code, 201, created.text)
        category_id = created.json()["id"]
        product = next(
            item for item in self.client.get("/api/admin/products", headers=headers).json()
            if item["id"] == "step-stool"
        )
        product_payload = {
            "name": product["name"],
            "category": "Outdoor Living",
            "price_cents": product["price_cents"],
            "stock_quantity": product["stock_quantity"],
            "color": product["color"],
            "background_color": product["bg"],
            "art": product["art"],
            "badge": product["badge"],
            "note": product["note"],
            "image_path": product["image_path"],
            "active": product["active"],
        }
        moved = self.client.put(
            "/api/admin/products/step-stool", json=product_payload, headers=headers
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        renamed = self.client.put(
            f"/api/admin/categories/{category_id}",
            json={"name": "Outdoor"},
            headers=headers,
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertIn("Outdoor", [item["name"] for item in self.client.get("/api/categories").json()])
        updated_product = next(
            item for item in self.client.get("/api/admin/products", headers=headers).json()
            if item["id"] == "step-stool"
        )
        self.assertEqual(updated_product["category"], "Outdoor")
        blocked = self.client.delete(f"/api/admin/categories/{category_id}", headers=headers)
        self.assertEqual(blocked.status_code, 409)
        product_payload["category"] = "Storage"
        self.assertEqual(
            self.client.put("/api/admin/products/step-stool", json=product_payload, headers=headers).status_code,
            200,
        )
        removed = self.client.delete(f"/api/admin/categories/{category_id}", headers=headers)
        self.assertEqual(removed.status_code, 200, removed.text)

    def test_store_settings_drive_public_config_and_low_stock(self) -> None:
        headers = self.sign_in()
        payload = {
            "business_name": "Al Majid Home Goods",
            "currency": "SAR",
            "locale": "en-SA",
            "contact_email": "shop@example.com",
            "contact_phone": "+966500000000",
            "business_address": "Riyadh",
            "low_stock_threshold": 10,
        }
        saved = self.client.put("/api/admin/settings", json=payload, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        public_config = self.client.get("/api/config").json()
        self.assertEqual(public_config["currency"], "SAR")
        self.assertEqual(public_config["contact_email"], "shop@example.com")
        with connect() as connection:
            connection.execute(
                "UPDATE products SET stock_quantity = 8 WHERE id = 'flex-basket'"
            )
        summary = self.client.get("/api/admin/summary", headers=headers).json()
        self.assertEqual(summary["low_stock"], 1)

    def test_bilingual_profile_categories_and_outlets(self) -> None:
        headers = self.sign_in()
        settings = {
            "business_name": "Al Majid Plastic",
            "business_name_ar": "الماجد للبلاستيك",
            "about_en": "Everyday essentials for homes and businesses.",
            "about_ar": "مستلزمات يومية للمنازل والأعمال.",
            "currency": "SAR",
            "locale": "ar-SA",
            "contact_email": "",
            "contact_phone": "",
            "business_address": "",
            "low_stock_threshold": 5,
        }
        saved = self.client.put("/api/admin/settings", json=settings, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        config = self.client.get("/api/config").json()
        self.assertEqual(config["business_name_ar"], "الماجد للبلاستيك")
        self.assertIn("مستلزمات يومية", config["about_ar"])

        category = self.client.post(
            "/api/admin/categories",
            json={"name": "Garden", "name_ar": "الحديقة"},
            headers=headers,
        )
        self.assertEqual(category.status_code, 201, category.text)
        self.assertIn(
            "الحديقة",
            [item["name_ar"] for item in self.client.get("/api/categories").json()],
        )

        outlet = self.client.post(
            "/api/admin/outlets",
            json={
                "name_en": "Riyadh Outlet",
                "name_ar": "فرع الرياض",
                "address_en": "Riyadh, Main Road",
                "address_ar": "الرياض، الطريق الرئيسي",
                "phone": "+966500000000",
                "hours_en": "Sat-Thu 9-5",
                "hours_ar": "السبت-الخميس ٩-٥",
                "active": True,
            },
            headers=headers,
        )
        self.assertEqual(outlet.status_code, 201, outlet.text)
        public_outlets = self.client.get("/api/outlets").json()
        self.assertEqual(public_outlets[0]["name_ar"], "فرع الرياض")
        archived = self.client.delete(
            f"/api/admin/outlets/{outlet.json()['id']}", headers=headers
        )
        self.assertEqual(archived.status_code, 200)

    def test_customer_history_order_detail_and_csv_exports(self) -> None:
        order = self.create_order(
            [{"product_id": "flex-basket", "quantity": 1}],
            customer_name="=1+2",
            email="history@example.com",
        )
        self.assertEqual(order.status_code, 201, order.text)
        headers = self.sign_in()
        detail = self.client.get(f"/api/admin/orders/{order.json()['id']}", headers=headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["delivery_address"], "123 Sample Street, Sample City")
        customers = self.client.get("/api/admin/customers", headers=headers)
        self.assertEqual(customers.status_code, 200, customers.text)
        customer = customers.json()[0]
        self.assertEqual(customer["order_count"], 1)
        self.assertEqual(len(customer["orders"]), 1)
        orders_csv = self.client.get("/api/admin/exports/orders.csv", headers=headers)
        self.assertEqual(orders_csv.status_code, 200)
        self.assertIn("'=1+2", orders_csv.text)
        for export in ("products", "customers"):
            response = self.client.get(f"/api/admin/exports/{export}.csv", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/csv", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
