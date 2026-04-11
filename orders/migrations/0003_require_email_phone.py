from django.db import migrations, models


def backfill_nulls(apps, schema_editor):
    order_model = apps.get_model('orders', 'Order')
    order_model.objects.filter(customer_email__isnull=True).update(customer_email='unknown@example.com')
    order_model.objects.filter(customer_email='').update(customer_email='unknown@example.com')
    order_model.objects.filter(customer_phone__isnull=True).update(customer_phone='N/A')
    order_model.objects.filter(customer_phone='').update(customer_phone='N/A')


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_add_return_statuses'),
    ]

    # Separate into atomic operations so backfill commits before ALTER
    operations = [
        migrations.RunPython(backfill_nulls, migrations.RunPython.noop, atomic=False),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE orders_order ALTER COLUMN customer_email SET NOT NULL;",
                    "ALTER TABLE orders_order ALTER COLUMN customer_email DROP NOT NULL;",
                ),
                migrations.RunSQL(
                    "ALTER TABLE orders_order ALTER COLUMN customer_phone SET NOT NULL;",
                    "ALTER TABLE orders_order ALTER COLUMN customer_phone DROP NOT NULL;",
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='order',
                    name='customer_email',
                    field=models.EmailField(max_length=254),
                ),
                migrations.AlterField(
                    model_name='order',
                    name='customer_phone',
                    field=models.CharField(max_length=30),
                ),
            ],
        ),
    ]
