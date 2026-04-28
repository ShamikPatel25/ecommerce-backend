from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        # Remove global unique constraint on Product.sku
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(max_length=100),
        ),
        # Add per-store unique constraint on Product.sku
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(
                fields=['store', 'sku'],
                name='unique_product_sku_per_store',
            ),
        ),
        # Remove global unique constraint on ProductVariant.sku
        migrations.AlterField(
            model_name='productvariant',
            name='sku',
            field=models.CharField(max_length=100),
        ),
        # Add per-product unique constraint on ProductVariant.sku
        migrations.AddConstraint(
            model_name='productvariant',
            constraint=models.UniqueConstraint(
                fields=['product', 'sku'],
                name='unique_variant_sku_per_product',
            ),
        ),
    ]
