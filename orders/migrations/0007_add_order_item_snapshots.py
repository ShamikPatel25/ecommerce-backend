from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_orderitem_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='product_name_snapshot',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='product_sku_snapshot',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='product_slug_snapshot',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='product_thumbnail_snapshot',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='variant_attrs_snapshot',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
