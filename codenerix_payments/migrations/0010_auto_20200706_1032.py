# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-07-06 08:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0009_auto_20200706_1013'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='order_ref',
            field=models.CharField(default=' ', max_length=8, verbose_name='Order Reference'),
            preserve_default=False,
        ),
    ]
