from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_address_line_1_order_address_line_2_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['store', 'status'], name='orders_order_store_s_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['store', 'customer_email'], name='orders_order_store_c_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['store', 'created_at'], name='orders_order_store_d_idx'),
        ),
    ]
