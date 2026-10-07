# NovaCart correction summary

## Commerce

- Added categories with hierarchy, product brands/SKUs/specifications, product variants and inventory.
- Added quantity-aware cart updates and POST-only cart mutations.
- Added validated checkout with server-side totals and database row locking.
- Added complete order statuses, payment status, status history, shipment, coupon and review models.
- Added authenticated My Orders and ownership-protected order detail pages.

## AI and knowledge

- Current price, stock, variants and authenticated order status now come from live commerce tables.
- FAQ, policy, text, document and website questions continue through bounded grounded retrieval.
- Added source links and a safer frontend chat request lifecycle.
- Limited message size and retained bounded evidence to prevent oversized Groq requests.
- Added knowledge-source ownership, processing status and error fields.

## Security and reliability

- Restricted knowledge ingestion to staff users.
- Added SSRF protection for website crawling by blocking private/local targets.
- Added production cookie, HTTPS and HSTS settings when `DEBUG=False`.
- Removed the real-looking secret from `.env.example`.
- Added upload/chat/crawler configuration values.
- Added Selenium dependencies required by the dynamic crawler.

## Run after replacing the project

```powershell
cd D:\ecommerce_chatbot
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

The ZIP intentionally excludes `venv`. Keep or recreate your local virtual environment and never copy a virtual environment between machines.
