# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2019-01-09 07:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='protocol',
            field=models.CharField(choices=[('paypal', 'Paypal'), ('redsys', 'Redsys'), ('redsysxml', 'Redsys XML'), ('yeepay', 'Yeepay')], max_length=10, verbose_name='Protocol'),
        ),
    ]
