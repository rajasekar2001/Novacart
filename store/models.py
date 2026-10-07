import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True,
    )
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="children",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"], name="unique_category_per_parent"
            )
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    CATALOG_STATUS = [("draft", "Draft"), ("published", "Published")]
    INGESTION_SOURCES = [("manual", "Manual"), ("ai", "AI assisted"), ("import", "Import")]
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=80, blank=True, db_index=True)
    brand = models.CharField(max_length=120, blank=True, db_index=True)
    description = models.TextField()
    specifications = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True)
    active = models.BooleanField(default=True, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)
    catalog_status = models.CharField(max_length=12, choices=CATALOG_STATUS, default="published", db_index=True)
    ingestion_source = models.CharField(max_length=12, choices=INGESTION_SOURCES, default="manual")
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_missing_fields = models.JSONField(default=list, blank=True)
    ai_warnings = models.JSONField(default=list, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_catalog_products",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def available_stock(self):
        variants = list(self.variants.filter(active=True))
        return sum(variant.stock for variant in variants) if variants else self.stock


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, unique=True)
    options = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.price


class InventoryMovement(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_movements"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True,
        related_name="inventory_movements",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity_change = models.IntegerField()
    stock_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=160, default="manual_adjustment")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = self.variant.name if self.variant else self.product.name
        return f"{target}: {self.quantity_change:+d}"


class Coupon(models.Model):
    DISCOUNT_TYPES = [("percent", "Percentage"), ("fixed", "Fixed amount")]
    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=12, choices=DISCOUNT_TYPES)
    value = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    minimum_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code


class Order(models.Model):
    STATUS = [
        ("placed", "Placed"), ("confirmed", "Confirmed"),
        ("processing", "Processing"), ("packed", "Packed"),
        ("shipped", "Shipped"), ("out_for_delivery", "Out for delivery"),
        ("delivered", "Delivered"), ("cancelled", "Cancelled"),
        ("return_requested", "Return requested"), ("returned", "Returned"),
        ("refunded", "Refunded"),
    ]
    PAYMENT_STATUS = [
        ("pending", "Pending"), ("paid", "Paid"),
        ("failed", "Failed"), ("refunded", "Refunded"),
    ]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders",
    )
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.TextField()
    pincode = models.CharField(max_length=12, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    shipping_method = models.CharField(max_length=80, default="standard")
    status = models.CharField(max_length=24, choices=STATUS, default="placed", db_index=True)
    payment_status = models.CharField(
        max_length=12, choices=PAYMENT_STATUS, default="pending", db_index=True
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True
    )
    product_name = models.CharField(max_length=180, blank=True)
    variant_name = models.CharField(max_length=160, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=24, choices=Order.STATUS)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=80, default="cash_on_delivery")
    provider_reference = models.CharField(max_length=160, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Order.PAYMENT_STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    carrier = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=160, blank=True, db_index=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="one_review_per_product")
        ]
