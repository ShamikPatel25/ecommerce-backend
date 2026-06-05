# Generated migration to fix order numbers with UUID format

import random
import string
from django.db import migrations


def generate_order_number():
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=6))
    return f"ORD-{random_part}"


def fix_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    used_numbers = set()

    # Get all existing valid order numbers to avoid duplicates
    for order in Order.objects.all():
        if order.order_number and len(order.order_number) <= 12:
            used_numbers.add(order.order_number)

    # Fix orders with UUID-style order numbers (longer than 12 chars)
    for order in Order.objects.all():
        if not order.order_number or len(order.order_number) > 12:
            order_number = generate_order_number()
            while order_number in used_numbers:
                order_number = generate_order_number()
            used_numbers.add(order_number)
            order.order_number = order_number
            order.save(update_fields=['order_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_add_order_number'),
    ]

    operations = [
        migrations.RunPython(fix_order_numbers, migrations.RunPython.noop),
    ]
