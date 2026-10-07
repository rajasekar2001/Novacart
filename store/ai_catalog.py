import base64
import json
import mimetypes
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Category, Product


def _category_catalog():
    return [
        {"id": c.id, "name": c.name, "parent": c.parent.name if c.parent else None}
        for c in Category.objects.select_related("parent").filter(active=True).order_by("name")
    ]


def _extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise ValidationError({"ai": "AI returned invalid JSON. Try again."})



def _normalise_price(value):
    if value is None:
        return ""
    raw = str(value).strip().replace(",", "").replace("₹", "")
    raw = re.sub(r"(?i)\\b(?:inr|rs\\.?)\\b", "", raw).strip()
    match = re.search(r"\\d+(?:\\.\\d{1,2})?", raw)
    if not match:
        return ""
    try:
        return format(Decimal(match.group(0)).quantize(Decimal("0.01")), "f")
    except (InvalidOperation, ValueError):
        return ""

def _price_from_notes(notes):
    text = str(notes or "")
    patterns = [
        r"(?i)\\bprice\\s*[:\\-]?\\s*(?:₹|inr|rs\\.?)?\\s*([\\d,]+(?:\\.\\d{1,2})?)",
        r"(?:₹|(?i:inr)|(?i:rs\\.?))\\s*([\\d,]+(?:\\.\\d{1,2})?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return _normalise_price(m.group(1))
    return ""

def _groq_json(prompt):
    if not getattr(settings, "GROQ_API_KEY", ""):
        raise ValidationError({"ai": "GROQ_API_KEY is not configured."})
    from groq import Groq
    try:
        response = Groq(api_key=settings.GROQ_API_KEY).chat.completions.create(
            model=getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, response_format={"type": "json_object"},
        )
        return _extract_json(response.choices[0].message.content)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError({"ai": f"AI analysis failed: {exc}"}) from exc

def suggest_category_plan(description):
    existing = _category_catalog()
    prompt = (
        "You help an ecommerce admin design categories. Return JSON only.\
"
        f"Existing categories: {json.dumps(existing, ensure_ascii=False)}\
"
        f"Admin request: {description}\
"
        'Return {"suggestions":[{"name":"","parent":"","reason":"","spec_template":[]}],"warnings":[]}. '
        "Reuse existing category names where appropriate. Do not create synonyms or duplicates. "
        "Suggest useful specification fields for each category."
    )
    data = _groq_json(prompt)
    data["suggestions"] = (data.get("suggestions") or [])[:12]
    return data

def product_quality(product):
    issues = []
    if not product.image: issues.append("Missing product image")
    if not product.brand: issues.append("Missing brand")
    if not product.sku: issues.append("Missing SKU")
    if not (product.description or "").strip(): issues.append("Missing description")
    elif len(product.description.strip()) < 60: issues.append("Description is very short")
    if not product.specifications: issues.append("Missing specifications")
    if product.stock <= 5: issues.append("Low stock")
    if product.price <= 0: issues.append("Invalid price")
    return {"id": product.id, "name": product.name, "score": max(0, 100 - len(issues) * 12), "issues": issues}

def _match_category(suggested, categories):
    value = str(suggested or "").strip().casefold()
    if not value:
        return None, 0.0
    best, score = None, 0.0
    for category in categories:
        name = category["name"].casefold()
        current = 1.0 if name == value else SequenceMatcher(None, name, value).ratio()
        if current > score:
            best, score = category, current
    return (best, score) if score >= 0.72 else (None, score)


def _duplicate_candidates(draft):
    name = str(draft.get("name") or "").strip()
    sku = str(draft.get("sku") or "").strip()
    qs = Product.objects.select_related("category")
    if sku:
        exact = qs.filter(sku__iexact=sku).first()
        if exact:
            return [{"id": exact.id, "name": exact.name, "sku": exact.sku, "reason": "same SKU"}]
    if not name:
        return []
    candidates = []
    for product in qs.filter(name__icontains=name[:40])[:8]:
        score = SequenceMatcher(None, product.name.casefold(), name.casefold()).ratio()
        if score >= 0.78:
            candidates.append({"id": product.id, "name": product.name, "sku": product.sku, "reason": "similar name"})
    return candidates[:5]


def generate_product_draft(*, notes="", image=None):
    """Generate a reviewable product draft. Never writes/publishes a Product."""
    if not getattr(settings, "GROQ_API_KEY", ""):
        raise ValidationError({"ai": "GROQ_API_KEY is not configured."})

    categories = _category_catalog()
    category_text = json.dumps(categories, ensure_ascii=False)
    prompt = f"""
You are a catalog-ingestion assistant for an ecommerce admin. Return ONLY one JSON object.
Never invent facts that are not supported by the admin notes or clearly visible in the image.
Unknown values must be empty strings or omitted from specifications.
Use an existing category when appropriate. Do not create category synonyms.

Existing categories: {category_text}
Admin notes: {notes.strip() or '(none)'}

Return this schema:
{{
  "name": "",
  "brand": "",
  "sku": "",
  "description": "",
  "suggested_category": "",
  "price": "",
  "stock": 0,
  "specifications": {{}},
  "confidence": 0.0,
  "missing_fields": [],
  "warnings": []
}}
confidence must be between 0 and 1. If price is explicitly supplied, return digits only without currency symbols or commas (example: 54999.00). Do not infer price, stock, SKU, technical specifications, material, purity, size, or model unless supplied or visible with certainty.
""".strip()

    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
    content = prompt
    if image:
        vision_model = getattr(settings, "GROQ_VISION_MODEL", "").strip()
        if not vision_model:
            raise ValidationError({"image": "Set GROQ_VISION_MODEL to analyze product images, or analyze using text notes only."})
        raw = image.read()
        if len(raw) > 8 * 1024 * 1024:
            raise ValidationError({"image": "AI analysis image must be 8 MB or smaller."})
        mime = image.content_type or mimetypes.guess_type(image.name)[0] or "image/jpeg"
        encoded = base64.b64encode(raw).decode("ascii")
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]
        model = vision_model

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        draft = _extract_json(response.choices[0].message.content)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError({"ai": f"AI analysis failed: {exc}"}) from exc

    matched, match_score = _match_category(draft.get("suggested_category"), categories)
    draft["category_match"] = matched
    draft["category_match_score"] = round(match_score, 3)
    draft["price"] = _normalise_price(draft.get("price")) or _price_from_notes(notes)
    draft["duplicate_candidates"] = _duplicate_candidates(draft)
    draft["confidence"] = max(0.0, min(1.0, float(draft.get("confidence") or 0)))
    draft["missing_fields"] = list(dict.fromkeys(draft.get("missing_fields") or []))
    draft["warnings"] = list(dict.fromkeys(draft.get("warnings") or []))
    if draft.get("suggested_category") and not matched:
        draft["warnings"].append("No safe existing category match was found; admin must choose a category.")
    return draft
