import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from knowledge.services import answer
from .models import Category, InventoryMovement, Order, Product


class CommerceFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("buyer", password="testpass123", email="test@example.com")
        self.client.force_login(self.user)
        self.category = Category.objects.create(name="Fruit", slug="fruit")
        self.product = Product.objects.create(
            category=self.category, name="Apple 500g", slug="apple-500g",
            description="Fresh apples", price="120.00", stock=5, active=True,
        )

    def test_cart_checkout_uses_server_price_and_reduces_stock(self):
        self.client.post(reverse("add_cart", args=[self.product.id]), {"quantity": 2})
        response = self.client.post(reverse("checkout"), {
            "full_name": "Test User", "email": "test@example.com",
            "phone": "9876543210", "address": "Test address",
            "shipping_method": "standard", "total": "1.00",
        })
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(str(order.total), "240.00")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_live_chat_uses_current_catalog_price(self):
        result, sources = answer("apple 500g price")
        self.assertIn("120.00", result)
        self.assertEqual(sources, ["/product/apple-500g/"])

    def test_order_chat_requires_owner(self):
        order = Order.objects.create(
            full_name="Guest", email="g@example.com", phone="9876543210",
            address="Address", total="120", subtotal="120",
        )
        result, _ = answer(f"track order #{order.id}")
        self.assertIn("sign in", result.lower())


class KnowledgeAccessTests(TestCase):
    def test_ingestion_requires_staff(self):
        user = get_user_model().objects.create_user("customer", password="testpass123")
        self.client.force_login(user)
        response = self.client.get(reverse("ingest"))
        self.assertEqual(response.status_code, 302)


class SeparateAdminDashboardTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            "adminuser", password="testpass123", is_staff=True
        )
        self.customer = get_user_model().objects.create_user(
            "customer2", password="testpass123"
        )

    def test_customer_cannot_access_dashboard(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_staff_receives_separate_dashboard_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NovaCart Admin")
        self.assertContains(response, "Categories")
        self.assertContains(response, "Inventory")

    def test_staff_can_create_jewels_category_and_product(self):
        self.client.force_login(self.staff)
        category_response = self.client.post(
            reverse("admin_categories"),
            data='{"name":"Jewels","active":true}',
            content_type="application/json",
        )
        self.assertEqual(category_response.status_code, 201)
        category_id = category_response.json()["category"]["id"]
        product_response = self.client.post(
            reverse("admin_products"),
            data=json.dumps({
                "category_id": category_id,
                "name": "Gold Necklace",
                "sku": "JWL-GN-001",
                "description": "22K gold necklace",
                "price": "85000.00",
                "stock": 3,
                "active": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(product_response.status_code, 201)
        product = Product.objects.get(name="Gold Necklace")
        self.assertEqual(product.category.name, "Jewels")

    def test_inventory_adjustment_is_recorded(self):
        self.client.force_login(self.staff)
        category = Category.objects.create(name="Jewels", slug="jewels")
        product = Product.objects.create(
            category=category, name="Ring", slug="ring", description="Gold ring",
            price="25000.00", stock=2,
        )
        response = self.client.post(
            reverse("admin_inventory"),
            data=json.dumps({"product_id": product.id, "quantity_change": 5, "reason": "purchase"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.stock, 7)
        self.assertTrue(InventoryMovement.objects.filter(product=product, stock_after=7).exists())


class CustomerAuthenticationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books", slug="books")
        self.product = Product.objects.create(
            category=self.category, name="Django Book", slug="django-book",
            description="Learn Django", price="499.00", stock=10, active=True,
        )
        self.customer = get_user_model().objects.create_user("shopper", password="testpass123")
        self.staff = get_user_model().objects.create_user("stafflogin", password="testpass123", is_staff=True)

    def test_anonymous_add_to_cart_requires_login(self):
        response = self.client.post(reverse("add_cart", args=[self.product.id]), {"quantity": 1})
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('add_cart', args=[self.product.id])}", fetch_redirect_response=False)

    def test_customer_login_redirects_to_customer_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "shopper", "password": "testpass123"})
        self.assertRedirects(response, reverse("customer_dashboard"), fetch_redirect_response=False)

    def test_staff_login_redirects_to_admin_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "stafflogin", "password": "testpass123"})
        self.assertRedirects(response, reverse("admin_dashboard"), fetch_redirect_response=False)

    def test_customer_dashboard_requires_login(self):
        response = self.client.get(reverse("customer_dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('customer_dashboard')}", fetch_redirect_response=False)
