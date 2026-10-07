# NovaCart separate admin dashboard

## Access

1. Sign in with a Django staff or superuser account.
2. Open `http://127.0.0.1:8000/dashboard/`.
3. Normal customer accounts are redirected to the admin login and cannot use the dashboard APIs.

## Included sections

- Overview statistics and recent orders
- Category create/edit
- Product create/edit with mandatory category
- Product variant management
- Inventory adjustment with audit records
- Links to AI Knowledge and the advanced Django Admin

## Example category workflow

Create `Jewels` in Categories. Then open Products and select `Jewels` from the required Category field when creating Gold Necklace, Ring, Bracelet or any other jewel product.

## Install after copying the files

```powershell
python manage.py makemigrations store
python manage.py migrate
python manage.py check
python manage.py test store
python manage.py runserver
```
