# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2017-11-08 15:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0018_auto_20170303_0839'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='action',
            field=models.CharField(choices=[('confirm', 'Confirm'), ('cancel', 'Cancel')], max_length=7, verbose_name='Action'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='protocol',
            field=models.CharField(choices=[('paypal', 'Paypal'), ('redsys', 'Redsys'), ('redsysxml', 'Redsys XML')], max_length=10, verbose_name='Protocol'),
        ),
    ]