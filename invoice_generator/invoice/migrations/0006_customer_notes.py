# Generated by Django 5.1.7 on 2025-03-29 06:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0005_remove_product_low_stock_threshold_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='notes',
            field=models.TextField(default=1),
            preserve_default=False,
        ),
    ]
