import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .forms import CheckoutForm, CustomerRegistrationForm
from .models import Category, Order, OrderItem, OrderStatusHistory, Payment, Product, ProductVariant
from .service import adjust_inventory, lookup_indian_pincode, save_category, save_product, save_variant
from .ai_catalog import generate_product_draft, product_quality, suggest_category_plan


def _request_data(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid JSON request.") from exc
    return request.POST.dict()


def _validation_response(exc):
    if hasattr(exc, "message_dict"):
        errors = exc.message_dict
    else:
        errors = {"error": exc.messages}
    return JsonResponse({"ok": False, "errors": errors}, status=400)


def _category_json(category):
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "parent": category.parent.name if category.parent else None,
        "active": category.active,
        "product_count": getattr(category, "product_count", category.products.count()),
    }


def _product_json(product):
    return {
        "id": product.id,
        "category_id": product.category_id,
        "category": product.category.name,
        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "brand": product.brand,
        "description": product.description,
        "specifications": product.specifications,
        "price": str(product.price),
        "stock": product.stock,
        "available_stock": product.available_stock,
        "active": product.active,
        "featured": product.featured,
        "catalog_status": product.catalog_status,
        "ingestion_source": product.ingestion_source,
        "ai_confidence": product.ai_confidence,
        "ai_missing_fields": product.ai_missing_fields,
        "ai_warnings": product.ai_warnings,
        "image": product.image.url if product.image else None,
        "variants": [
            {
                "id": variant.id,
                "name": variant.name,
                "sku": variant.sku,
                "options": variant.options,
                "price": str(variant.effective_price),
                "own_price": str(variant.price) if variant.price is not None else None,
                "stock": variant.stock,
                "active": variant.active,
            }
            for variant in product.variants.all()
        ],
    }


def _normalise_cart(request):
    """Upgrade legacy carts while preserving current sessions."""
    raw = request.session.get("cart", {})
    cart = {}
    for key, value in raw.items():
        if isinstance(value, int):
            cart[f"p:{key}"] = {"product_id": int(key), "variant_id": None, "quantity": value}
        elif isinstance(value, dict):
            product_id, variant_id = value.get("product_id"), value.get("variant_id")
            quantity = value.get("quantity", 1)
            if product_id and isinstance(quantity, int) and quantity > 0:
                cart[key] = {
                    "product_id": int(product_id),
                    "variant_id": int(variant_id) if variant_id else None,
                    "quantity": quantity,
                }
    if cart != raw:
        request.session["cart"] = cart
    return cart


def _cart_items(cart, lock=False):
    product_ids = {entry["product_id"] for entry in cart.values()}
    variant_ids = {entry["variant_id"] for entry in cart.values() if entry["variant_id"]}
    product_query = Product.objects.filter(id__in=product_ids, active=True)
    variant_query = ProductVariant.objects.filter(
        id__in=variant_ids, active=True, product__active=True
    ).select_related("product")
    if lock:
        product_query = product_query.select_for_update()
        variant_query = variant_query.select_for_update()
    products = {item.id: item for item in product_query}
    variants = {item.id: item for item in variant_query}
    items, total, invalid = [], Decimal("0"), False
    for key, entry in cart.items():
        product = products.get(entry["product_id"])
        variant = variants.get(entry["variant_id"]) if entry["variant_id"] else None
        if not product or (entry["variant_id"] and not variant):
            invalid = True
            continue
        quantity = entry["quantity"]
        stock = variant.stock if variant else product.stock
        price = variant.effective_price if variant else product.price
        subtotal = price * quantity
        total += subtotal
        items.append({
            "key": key, "product": product, "variant": variant,
            "quantity": quantity, "stock": stock, "price": price, "subtotal": subtotal,
        })
    return items, total, invalid

def customer_register(request):
    if request.user.is_authenticated:
        return redirect(
            "admin_dashboard" if request.user.is_staff else "customer_dashboard"
        )

    form = CustomerRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()

        # Log the new customer in immediately after registration.
        login(request, user)

        messages.success(
            request,
            "Registration successful. Welcome to NovaCart!"
        )

        next_url = request.POST.get("next") or request.GET.get("next")
        return redirect(next_url or "customer_dashboard")

    return render(
        request,
        "registration/register.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
        },
    )


def account_login(request):
    if request.user.is_authenticated:
        return redirect("admin_dashboard" if request.user.is_staff else "customer_dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        if user.is_staff:
            return redirect("admin_dashboard")
        next_url = request.POST.get("next") or request.GET.get("next")
        return redirect(next_url or "customer_dashboard")
    return render(request, "registration/login.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def customer_dashboard(request):
    if request.user.is_staff:
        return redirect("admin_dashboard")
    cart_data = _normalise_cart(request)
    items, total, _ = _cart_items(cart_data)
    orders = request.user.orders.prefetch_related("items").all()
    return render(request, "store/customer_dashboard.html", {
        "cart_count": sum(item["quantity"] for item in items),
        "cart_total": total,
        "orders": orders[:5],
        "order_count": orders.count(),
    })

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def home(request):

    q = request.GET.get("q", "").strip()

    # ONLY root categories appear on homepage
    categories = (
        Category.objects
        .filter(
            active=True,
            parent__isnull=True,
        )
        .annotate(
            active_product_count=Count(
                "products",
                filter=Q(products__active=True),
                distinct=True,
            )
        )
        .order_by("name")
    )

    products = Product.objects.none()

    if q:

        products = (
            Product.objects
            .filter(active=True)
            .filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(brand__icontains=q)
                | Q(category__name__icontains=q)
            )
            .select_related("category")
            .prefetch_related("variants")
            .distinct()
            .order_by("name")
        )

    return render(
        request,
        "store/home.html",
        {
            "categories": categories,
            "products": products,
            "q": q,
        },
    )


def category_products(request, slug):

    category = get_object_or_404(
        Category.objects.select_related("parent"),
        slug=slug,
        active=True,
    )

    # Direct child categories
    subcategories = (
        Category.objects
        .filter(
            parent=category,
            active=True,
        )
        .annotate(
            active_product_count=Count(
                "products",
                filter=Q(products__active=True),
                distinct=True,
            )
        )
        .order_by("name")
    )

    # Products assigned directly to current category
    products = (
        Product.objects
        .filter(
            category=category,
            active=True,
        )
        .select_related("category")
        .prefetch_related("variants")
        .order_by("name")
    )

    # Build:
    # Home > Fashion > Men's Fashion > Dresses > T-Shirt

    breadcrumbs = []

    current = category

    while current is not None:

        breadcrumbs.insert(
            0,
            current,
        )

        current = current.parent

    return render(
        request,
        "store/category_products.html",
        {
            "category": category,
            "subcategories": subcategories,
            "products": products,
            "breadcrumbs": breadcrumbs,
        },
    )

# def home(request):
#     query = request.GET.get("q", "").strip()
#     sort = request.GET.get("sort", "featured")
#     categories = Category.objects.filter(active=True).annotate(
#         active_product_count=Count("products", filter=Q(products__active=True))
#     ).order_by("name")
#     products = Product.objects.none()
#     if query:
#         products = Product.objects.filter(active=True).select_related("category").filter(
#             Q(name__icontains=query) | Q(description__icontains=query)
#             | Q(brand__icontains=query) | Q(sku__icontains=query)
#             | Q(category__name__icontains=query)
#         ).distinct()
#     ordering = {
#         "price_low": "price", "price_high": "-price",
#         "newest": "-created_at", "featured": "-featured",
#     }.get(sort, "-featured")
#     return render(request, "store/home.html", {
#         "products": products.order_by(ordering, "name"),
#         "categories": categories, "q": query, "sort": sort,
#     })


# def category_products(request, slug):
#     category = get_object_or_404(Category, slug=slug, active=True)
#     query = request.GET.get("q", "").strip()
#     sort = request.GET.get("sort", "featured")
#     products = category.products.filter(active=True).select_related("category")
#     if query:
#         products = products.filter(
#             Q(name__icontains=query) | Q(description__icontains=query)
#             | Q(brand__icontains=query) | Q(sku__icontains=query)
#         )
#     ordering = {
#         "price_low": "price", "price_high": "-price",
#         "newest": "-created_at", "featured": "-featured",
#     }.get(sort, "-featured")
#     return render(request, "store/category_products.html", {
#         "category": category,
#         "products": products.order_by(ordering, "name"),
#         "q": query,
#         "sort": sort,
#     })


def detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("variants", "reviews"), slug=slug, active=True
    )
    return render(request, "store/detail.html", {"product": product})


@login_required
@require_POST
def add_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, active=True)
    variant_id = request.POST.get("variant_id") or None
    variant = get_object_or_404(
        ProductVariant, id=variant_id, product=product, active=True
    ) if variant_id else None
    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        quantity = 1
    stock = variant.stock if variant else product.stock
    if stock < 1:
        messages.error(request, "This item is out of stock.")
        return redirect(request.POST.get("next") or "cart")
    cart_data = _normalise_cart(request)
    key = f"v:{variant.id}" if variant else f"p:{product.id}"
    current = cart_data.get(key, {}).get("quantity", 0)
    cart_data[key] = {
        "product_id": product.id, "variant_id": variant.id if variant else None,
        "quantity": min(current + quantity, stock),
    }
    request.session["cart"] = cart_data
    messages.success(request, f"{product.name} added to cart.")
    return redirect(request.POST.get("next") or "cart")


@login_required
def cart(request):
    cart_data = _normalise_cart(request)
    items, total, invalid = _cart_items(cart_data)
    if invalid:
        valid_keys = {item["key"] for item in items}
        request.session["cart"] = {key: value for key, value in cart_data.items() if key in valid_keys}
        messages.warning(request, "Unavailable items were removed from your cart.")
    return render(request, "store/cart.html", {"items": items, "total": total})


@login_required
@require_POST
def update_cart(request, item_key):
    cart_data = _normalise_cart(request)
    entry = cart_data.get(item_key)
    if not entry:
        return redirect("cart")
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if quantity <= 0:
        cart_data.pop(item_key, None)
    else:
        product = get_object_or_404(Product, id=entry["product_id"], active=True)
        variant = get_object_or_404(
            ProductVariant, id=entry["variant_id"], active=True, product=product
        ) if entry["variant_id"] else None
        entry["quantity"] = min(quantity, variant.stock if variant else product.stock)
    request.session["cart"] = cart_data
    return redirect("cart")


@login_required
@require_POST
def remove_cart(request, item_key):
    cart_data = _normalise_cart(request)
    cart_data.pop(item_key, None)
    request.session["cart"] = cart_data
    return redirect("cart")


@login_required
@transaction.atomic
def checkout(request):
    cart_data = _normalise_cart(request)
    if not cart_data:
        return redirect("cart")
    items, total, invalid = _cart_items(cart_data, lock=request.method == "POST")
    if invalid or not items or any(item["quantity"] > item["stock"] for item in items):
        messages.error(request, "Some stock changed. Please review your cart.")
        return redirect("cart")
    initial = {"full_name": request.user.get_full_name(), "email": request.user.email}
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        checkout_data = form.cleaned_data.copy()
        try:
            location = lookup_indian_pincode(checkout_data["pincode"])
            checkout_data.update({
                "country": location["country"],
                "state": location["state"],
                "city": location["city"],
            })
        except ValidationError:
            # Keep manually entered values when the external service is unavailable.
            pass
        order = Order.objects.create(
            user=request.user,
            subtotal=total, total=total, **checkout_data,
        )
        for item in items:
            product, variant = item["product"], item["variant"]
            OrderItem.objects.create(
                order=order, product=product, variant=variant,
                product_name=product.name, variant_name=variant.name if variant else "",
                quantity=item["quantity"], price=item["price"],
            )
            stock_object = variant or product
            stock_object.stock -= item["quantity"]
            stock_object.save(update_fields=["stock", "updated_at"])
        OrderStatusHistory.objects.create(order=order, status="placed")
        Payment.objects.create(order=order, amount=total, status="pending")
        request.session["cart"] = {}
        return render(request, "store/success.html", {"order": order})
    return render(request, "store/checkout.html", {"form": form, "items": items, "total": total})


@require_GET
def pincode_lookup(request, pincode):
    try:
        location = lookup_indian_pincode(pincode)
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "location": location})


@login_required
def my_orders(request):
    return render(request, "store/orders.html", {
        "orders": request.user.orders.prefetch_related("items").all()
    })


@login_required
def order_detail(request, public_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_history"),
        public_id=public_id, user=request.user,
    )
    return render(request, "store/order_detail.html", {"order": order})


# Separate staff dashboard API. These endpoints are never used by customer pages.
@staff_member_required
@require_GET
def admin_dashboard(request):
    orders = Order.objects.all()
    stats = {
        "categories": Category.objects.count(),
        "active_products": Product.objects.filter(active=True).count(),
        "low_stock_products": Product.objects.filter(active=True, stock__lte=5).count(),
        "orders": orders.count(),
        "pending_orders": orders.exclude(
            status__in=["delivered", "cancelled", "returned", "refunded"]
        ).count(),
        "revenue": orders.filter(payment_status="paid").aggregate(total=Sum("total"))["total"]
        or Decimal("0.00"),
    }
    recent_orders = orders.select_related("user")[:8]
    low_stock = Product.objects.filter(active=True, stock__lte=5).select_related("category")[:8]
    return render(request, "store/admin/dashboard.html", {
        "stats": stats,
        "recent_orders": recent_orders,
        "low_stock": low_stock,
    })


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_categories(request):
    if request.method == "GET":
        categories = Category.objects.select_related("parent").order_by("name")
        return JsonResponse({"ok": True, "categories": [_category_json(item) for item in categories]})
    try:
        category = save_category(_request_data(request))
        if request.FILES.get("image"):
            category.image = request.FILES["image"]
            category.save(update_fields=["image"])
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "category": _category_json(category)}, status=201)


# @staff_member_required
# @require_http_methods(["GET", "POST"])
# def admin_category_detail(request, category_id):
#     category = get_object_or_404(Category.objects.select_related("parent"), pk=category_id)
#     if request.method == "GET":
#         products = category.products.prefetch_related("variants").order_by("name")
#         return JsonResponse({
#             "ok": True,
#             "category": _category_json(category),
#             "products": [_product_json(product) for product in products],
#         })
#     try:
#         category = save_category(_request_data(request), category=category)
#     except ValidationError as exc:
#         return _validation_response(exc)
#     return JsonResponse({"ok": True, "category": _category_json(category)})

@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_category_detail(request, category_id):
    category = get_object_or_404(
        Category.objects.select_related("parent"),
        pk=category_id
    )

    if request.method == "GET":
        products = (
            category.products
            .prefetch_related("variants")
            .order_by("name")
        )

        return JsonResponse({
            "ok": True,
            "category": _category_json(category),
            "products": [
                _product_json(product)
                for product in products
            ],
        })

    try:
        data = _request_data(request)

        category = save_category(
            data,
            category=category
        )

        # SAVE UPLOADED IMAGE
        uploaded_image = request.FILES.get("image")

        if uploaded_image:
            category.image = uploaded_image
            category.save(update_fields=["image"])

    except ValidationError as exc:
        return _validation_response(exc)

    return JsonResponse({
        "ok": True,
        "category": _category_json(category)
    })


@staff_member_required
@require_POST
def admin_ai_category_plan(request):
    try:
        data = _request_data(request)
        description = str(data.get("description") or "").strip()
        if not description:
            raise ValidationError({"description": "Describe what you want to sell."})
        plan = suggest_category_plan(description)
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "plan": plan})


@staff_member_required
@require_GET
def admin_quality_insights(request):
    checks = [product_quality(p) for p in Product.objects.select_related("category").all()]
    needing_review = sorted([x for x in checks if x["issues"]], key=lambda x: x["score"])
    return JsonResponse({"ok": True, "summary": {
        "total": len(checks), "needs_review": len(needing_review),
        "missing_images": sum("Missing product image" in x["issues"] for x in checks),
        "missing_specs": sum("Missing specifications" in x["issues"] for x in checks),
        "low_stock": sum("Low stock" in x["issues"] for x in checks),
    }, "products": needing_review[:20]})


@staff_member_required
@require_POST
def admin_ai_copilot(request):
    try:
        query = str(_request_data(request).get("query") or "").strip().lower()
        if not query:
            raise ValidationError({"query": "Ask the admin copilot a question."})
        products = Product.objects.select_related("category")
        if "low stock" in query or "stock below" in query:
            rows = products.filter(stock__lte=5).order_by("stock")[:20]
            answer = "Low-stock products: " + (", ".join(f"{p.name} ({p.stock})" for p in rows) or "None")
        elif "missing image" in query or "without image" in query:
            rows = products.filter(Q(image="") | Q(image__isnull=True))[:20]
            answer = "Products missing images: " + (", ".join(p.name for p in rows) or "None")
        elif "missing specification" in query or "incomplete" in query:
            rows = [p.name for p in products if not p.specifications][:20]
            answer = "Products missing specifications: " + (", ".join(rows) or "None")
        elif "draft" in query:
            rows = products.filter(catalog_status="draft")[:20]
            answer = "Draft products: " + (", ".join(p.name for p in rows) or "None")
        else:
            answer = "Try: show low stock, products missing images, products missing specifications, or show draft products."
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "answer": answer})


@staff_member_required
@require_POST
def admin_ai_product_draft(request):
    try:
        draft = generate_product_draft(
            notes=request.POST.get("notes", ""),
            image=request.FILES.get("image"),
        )
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "draft": draft})

@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_products(request):
    if request.method == "GET":
        products = Product.objects.select_related("category").prefetch_related("variants")
        category_id = request.GET.get("category_id")
        if category_id:
            products = products.filter(category_id=category_id)
        query = request.GET.get("q", "").strip()
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(sku__icontains=query)
                | Q(brand__icontains=query) | Q(category__name__icontains=query)
            ).distinct()
        return JsonResponse({"ok": True, "products": [_product_json(item) for item in products]})
    try:
        data = _request_data(request)
        product = save_product(data)
        if product.ingestion_source == "ai" and product.catalog_status == "published":
            product.reviewed_by = request.user
            product.reviewed_at = timezone.now()
            product.save(update_fields=["reviewed_by", "reviewed_at", "updated_at"])
        if request.FILES.get("image"):
            product.image = request.FILES["image"]
            product.save(update_fields=["image", "updated_at"])
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "product": _product_json(product)}, status=201)


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("variants"), pk=product_id
    )
    if request.method == "GET":
        return JsonResponse({"ok": True, "product": _product_json(product)})
    try:
        product = save_product(_request_data(request), product=product)
        if product.ingestion_source == "ai" and product.catalog_status == "published":
            product.reviewed_by = request.user
            product.reviewed_at = timezone.now()
            product.save(update_fields=["reviewed_by", "reviewed_at", "updated_at"])
        if request.FILES.get("image"):
            product.image = request.FILES["image"]
            product.save(update_fields=["image", "updated_at"])
    except ValidationError as exc:
        return _validation_response(exc)
    return JsonResponse({"ok": True, "product": _product_json(product)})


@staff_member_required
@require_POST
def admin_product_variant(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        data = _request_data(request)
        variant = None
        if data.get("variant_id"):
            variant = get_object_or_404(ProductVariant, pk=data["variant_id"], product=product)
        save_variant(product, data, variant=variant)
    except ValidationError as exc:
        return _validation_response(exc)
    product = Product.objects.select_related("category").prefetch_related("variants").get(pk=product.pk)
    return JsonResponse({"ok": True, "product": _product_json(product)})


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_inventory(request):
    if request.method == "GET":
        products = Product.objects.select_related("category").prefetch_related("variants")
        return JsonResponse({
            "ok": True,
            "inventory": [_product_json(product) for product in products],
        })
    try:
        data = _request_data(request)
        movement = adjust_inventory(
            product_id=data.get("product_id"),
            variant_id=data.get("variant_id") or None,
            quantity_change=data.get("quantity_change"),
            reason=data.get("reason", "manual_adjustment"),
            note=data.get("note", ""),
            user=request.user,
        )
    except (ValidationError, ValueError, TypeError, Product.DoesNotExist, ProductVariant.DoesNotExist) as exc:
        if isinstance(exc, ValidationError):
            return _validation_response(exc)
        return JsonResponse({"ok": False, "errors": {"inventory": [str(exc)]}}, status=400)
    return JsonResponse({
        "ok": True,
        "movement": {
            "id": movement.id,
            "product_id": movement.product_id,
            "variant_id": movement.variant_id,
            "quantity_change": movement.quantity_change,
            "stock_after": movement.stock_after,
            "reason": movement.reason,
        },
    })
