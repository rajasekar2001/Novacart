import json
import re
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from .models import Category, InventoryMovement, Product, ProductVariant

def _lookup_india_post(pincode):
    """
    Retrieve city, state and country using the India Post API.

    City selection priority:
    1. Cleaned postal division
    2. District
    3. Taluk
    4. Block
    """

    base_url = getattr(
        settings,
        "INDIA_PINCODE_API_BASE_URL",
        "https://api.postalpincode.in/pincode",
    )

    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; NovaCart/1.0)"
        ),
    }

    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/{pincode}",
            headers=headers,
            timeout=(5, 15),
        )

        if response.status_code != 200:
            return None

        payload = response.json()

        if not isinstance(payload, list) or not payload:
            return None

        result = payload[0]

        if (
            str(result.get("Status", ""))
            .strip()
            .casefold()
            != "success"
        ):
            return None

        post_offices = result.get("PostOffice") or []

        if not isinstance(post_offices, list) or not post_offices:
            return None

        post_office = post_offices[0]

        state = str(
            post_office.get("State", "")
        ).strip()

        country = str(
            post_office.get("Country", "India")
        ).strip() or "India"

        division = str(
            post_office.get("Division", "")
        ).strip()

        # Examples:
        # "Chennai GPO Division" -> "Chennai"
        # "Chennai G.P.O."       -> "Chennai"
        division = re.sub(
            r"\s+(?:g\.?\s*p\.?\s*o\.?\s+)?division$",
            "",
            division,
            flags=re.IGNORECASE,
        ).strip()

        division = re.sub(
            r"\s+g\.?\s*p\.?\s*o\.?$",
            "",
            division,
            flags=re.IGNORECASE,
        ).strip()

        invalid_values = {
            "",
            "na",
            "n/a",
            "none",
            "null",
            "undefined",
        }

        city_candidates = (
            division,
            post_office.get("District"),
            post_office.get("Taluk"),
            post_office.get("Block"),
        )

        city = next(
            (
                str(candidate).strip()
                for candidate in city_candidates
                if candidate
                and str(candidate).strip().casefold()
                not in invalid_values
            ),
            "",
        )

        if not state or not city:
            return None

        return {
            "pincode": str(pincode),
            "country": country,
            "country_code": "IN",
            "state": state,
            "city": city,
        }

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ):
        return None
    
def lookup_indian_pincode(pincode):
    """Resolve an Indian pincode using India Post data."""

    value = str(pincode or "").strip()

    if not re.fullmatch(r"[1-9][0-9]{5}", value):
        raise ValidationError({
            "pincode": (
                "Enter a valid six-digit Indian pincode."
            )
        })

    # New version prevents previous Flower Bazar results.
    cache_key = f"pincode:v6:IN:{value}"

    cached = cache.get(cache_key)

    if cached:
        return cached

    # Do not use Zippopotam because it can return the
    # post-office locality as the city.
    result = _lookup_india_post(value)

    if not result:
        raise ValidationError({
            "pincode": (
                "The India Post service could not find this "
                "pincode. Enter the location manually."
            )
        })

    if not result.get("state") or not result.get("city"):
        raise ValidationError({
            "pincode": (
                "Incomplete pincode information was returned."
            )
        })

    cache.set(
        cache_key,
        result,
        60 * 60 * 24 * 7,
    )

    return result

# def lookup_indian_pincode(pincode):
#     """Resolve a six-digit Indian pincode to country, state and city."""
#     value = str(pincode or "").strip()
#     if not re.fullmatch(r"[1-9][0-9]{5}", value):
#         raise ValidationError({"pincode": "Enter a valid six-digit Indian pincode."})
#     cache_key = f"pincode:IN:{value}"
#     cached = cache.get(cache_key)
#     if cached:
#         return cached
#     base_url = getattr(settings, "PINCODE_API_BASE_URL", "https://api.zippopotam.us")
#     try:
#         response = requests.get(f"{base_url.rstrip('/')}/IN/{value}", timeout=8)
#     except requests.RequestException as exc:
#         raise ValidationError({"pincode": "Pincode service is temporarily unavailable."}) from exc
#     if response.status_code == 404:
#         raise ValidationError({"pincode": "No location was found for this pincode."})
#     try:
#         response.raise_for_status()
#         payload = response.json()
#         place = payload["places"][0]
#         result = {
#             "pincode": payload.get("post code", value),
#             "country": payload.get("country", "India"),
#             "country_code": payload.get("country abbreviation", "IN"),
#             "state": place.get("state", ""),
#             "city": place.get("place name", ""),
#         }
#     except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
#         raise ValidationError({"pincode": "The pincode response could not be processed."}) from exc
#     if not result["state"] or not result["city"]:
#         raise ValidationError({"pincode": "Incomplete location data was returned."})
#     cache.set(cache_key, result, 60 * 60 * 24 * 7)
#     return result


def as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def as_money(value, field_name="price"):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Enter a valid amount."}) from exc
    if amount < 0:
        raise ValidationError({field_name: "Amount cannot be negative."})
    return amount.quantize(Decimal("0.01"))


def as_non_negative_int(value, field_name="stock"):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Enter a whole number."}) from exc
    if number < 0:
        raise ValidationError({field_name: "Value cannot be negative."})
    return number


def json_object(value, field_name="specifications"):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError({field_name: "Enter a valid JSON object."}) from exc
    if not isinstance(parsed, dict):
        raise ValidationError({field_name: "The value must be a JSON object."})
    return parsed


def unique_slug(model, value, instance=None):
    base = slugify(value) or "item"
    candidate = base
    counter = 2
    queryset = model.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(slug=candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


@transaction.atomic
def save_category(data, category=None):
    category = category or Category()
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValidationError({"name": "Category name is required."})
    parent_id = data.get("parent_id") or None
    parent = None
    if parent_id:
        parent = Category.objects.filter(pk=parent_id).first()
        if not parent:
            raise ValidationError({"parent_id": "Parent category was not found."})
        if category.pk and (parent.pk == category.pk or parent.parent_id == category.pk):
            raise ValidationError({"parent_id": "A category cannot be its own parent."})
    category.name = name
    category.slug = unique_slug(Category, data.get("slug") or name, category)
    category.parent = parent
    category.active = as_bool(data.get("active"), default=True)
    category.full_clean()
    category.save()
    return category


@transaction.atomic
def save_product(data, product=None):
    product = product or Product()
    category_id = data.get("category_id")
    category = Category.objects.filter(pk=category_id, active=True).first()
    if not category:
        raise ValidationError({"category_id": "Select an active category."})
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValidationError({"name": "Product name is required."})
    product.category = category
    product.name = name
    product.slug = unique_slug(Product, data.get("slug") or name, product)
    product.sku = str(data.get("sku", "")).strip()
    product.brand = str(data.get("brand", "")).strip()
    product.description = str(data.get("description", "")).strip()
    product.specifications = json_object(data.get("specifications"))
    product.price = as_money(data.get("price"))
    product.stock = as_non_negative_int(data.get("stock", 0))
    product.active = as_bool(data.get("active"), default=True)
    product.featured = as_bool(data.get("featured"), default=False)
    if data.get("ingestion_source") in {"manual", "ai", "import"}:
        product.ingestion_source = data["ingestion_source"]
    if data.get("catalog_status") in {"draft", "published"}:
        product.catalog_status = data["catalog_status"]
    if data.get("ai_confidence") not in (None, ""):
        try:
            product.ai_confidence = max(0.0, min(1.0, float(data["ai_confidence"])))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"ai_confidence": "Enter a confidence between 0 and 1."}) from exc
    if "ai_missing_fields" in data:
        value = data["ai_missing_fields"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        product.ai_missing_fields = value if isinstance(value, list) else []
    if "ai_warnings" in data:
        value = data["ai_warnings"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        product.ai_warnings = value if isinstance(value, list) else []
    product.full_clean()
    product.save()
    return product


@transaction.atomic
def save_variant(product, data, variant=None):
    variant = variant or ProductVariant(product=product)
    name = str(data.get("name", "")).strip()
    sku = str(data.get("sku", "")).strip()
    if not name or not sku:
        raise ValidationError({"variant": "Variant name and SKU are required."})
    variant.product = product
    variant.name = name
    variant.sku = sku
    variant.options = json_object(data.get("options"), "options")
    price = data.get("price")
    variant.price = None if price in (None, "") else as_money(price)
    variant.stock = as_non_negative_int(data.get("stock", 0))
    variant.active = as_bool(data.get("active"), default=True)
    variant.full_clean()
    variant.save()
    return variant


@transaction.atomic
def adjust_inventory(*, product_id, quantity_change, user, variant_id=None, reason="manual_adjustment", note=""):
    product = Product.objects.select_for_update().get(pk=product_id)
    variant = None
    target = product
    if variant_id:
        variant = ProductVariant.objects.select_for_update().get(
            pk=variant_id, product=product
        )
        target = variant
    change = int(quantity_change)
    new_stock = target.stock + change
    if new_stock < 0:
        raise ValidationError({"quantity_change": "Adjustment would make stock negative."})
    target.stock = new_stock
    target.save(update_fields=["stock", "updated_at"])
    return InventoryMovement.objects.create(
        product=product,
        variant=variant,
        changed_by=user,
        quantity_change=change,
        stock_after=new_stock,
        reason=str(reason or "manual_adjustment")[:160],
        note=str(note or "")[:255],
    )
