from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_slug_unique_per_store'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='product',
            unique_together={('store', 'slug')},
        ),
    ]
