from django.db import migrations
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.filter(slug=''):
        base_slug = slugify(product.name) or 'product'
        slug = base_slug
        counter = 1
        while Product.objects.filter(store=product.store, slug=slug).exclude(pk=product.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        product.slug = slug
        product.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_productmedia_attribute_value'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
