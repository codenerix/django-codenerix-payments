# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-07-06 08:13
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models
from codenerix.helpers import CodenerixEncoder


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0008_auto_20200504_1145'),
    ]

    def run_migrate(apps, schema_editor):
        ce = CodenerixEncoder()
        model = apps.get_model('codenerix_payments', "PaymentRequest")
        for line in model.objects.all():
            line.order_ref = ce.numeric_encode(line.order, dic='hex36', length=8, cfill='A')
            line.save()

    operations = [
        migrations.AddField(
            model_name='paymentrequest',
            name='order_ref',
            field=models.CharField(blank=True, default=' ', max_length=8, null=True, verbose_name='Order Reference'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='order',
            field=models.PositiveIntegerField(validators=[django.core.validators.MaxValueValidator(2821109907455)], verbose_name='Order Number'),
        ),
        migrations.RunPython(run_migrate),
    ]
