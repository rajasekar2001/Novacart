# NovaCart - Django E-commerce + Grounded RAG Assistant

NovaCart contains a responsive storefront, product variants, session cart, validated checkout, inventory-safe order creation, customer order tracking, Django administration, and a grounded shopping assistant.

The assistant uses two data paths:

- Current price, stock, product variants and private order status come from live commerce tables.
- FAQs, policies, uploaded documents and approved website content use bounded RAG retrieval.

This separation prevents stale FAQ content from overriding transactional data.

## Windows setup

```powershell
cd ecommerce_chatbot
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

Generate a secret key:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated value into `SECRET_KEY` in `.env`. Never commit the real `.env` file.

## URLs

- Store: `http://127.0.0.1:8000/`
- Customer orders: `http://127.0.0.1:8000/orders/`
- Staff knowledge ingestion: `http://127.0.0.1:8000/knowledge/`
- Django admin: `http://127.0.0.1:8000/admin/`

## Knowledge ingestion

Staff users can paste text, upload PDF/DOCX/TXT/MD/CSV files, or crawl a public website. The complete structured array is saved in `KnowledgeSource.faq_json`, and each record is saved as an `FAQ` row for retrieval.

```json
[
  {
    "question": "What is the return period?",
    "answer": "Items may be returned within 7 days if unused.",
    "keywords": ["return", "7 days", "unused"],
    "faq_type": "policy",
    "metadata": {},
    "source_url": "https://example.com/returns"
  }
]
```

The crawler blocks local/private network addresses by default. Only crawl websites you are permitted to process.

## Implemented documentation phases

- Foundation: catalog, categories, authentication integration and responsive UI
- Shopping: search, sorting, variants and quantity-aware cart
- Commerce: validated checkout, server-side totals, inventory locking and orders
- Operations: expanded order lifecycle, payments, shipments, coupons and admin tools
- Intelligence: live commerce tools plus bounded FAQ/document/website RAG
- Quality: access control, upload limits, SSRF protection and automated core-flow tests

Payment gateway collection is intentionally not enabled. `Payment` records and statuses are prepared for provider integration, but production online payments require signed webhooks and provider-side verification.

## Verification

```powershell
python manage.py check
python manage.py test
```

## PostgreSQL

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` in `.env`, then run `python manage.py migrate`. SQLite remains available for local development.

For production, set `DEBUG=False`, configure exact `ALLOWED_HOSTS`, serve static/media files through a web server or object storage, and move long website crawls to a background worker.
