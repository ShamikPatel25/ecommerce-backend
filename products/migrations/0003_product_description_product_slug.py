from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_category_is_active_alter_product_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='product',
            name='slug',
            field=models.SlugField(blank=True, max_length=200),
        ),
    ]
