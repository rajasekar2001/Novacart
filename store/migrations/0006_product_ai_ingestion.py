from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("store", "0005_category_image"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="product", name="catalog_status", field=models.CharField(choices=[("draft", "Draft"), ("published", "Published")], db_index=True, default="published", max_length=12)),
        migrations.AddField(model_name="product", name="ingestion_source", field=models.CharField(choices=[("manual", "Manual"), ("ai", "AI assisted"), ("import", "Import")], default="manual", max_length=12)),
        migrations.AddField(model_name="product", name="ai_confidence", field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name="product", name="ai_missing_fields", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="product", name="ai_warnings", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="product", name="reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="product", name="reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_catalog_products", to=settings.AUTH_USER_MODEL)),
    ]
