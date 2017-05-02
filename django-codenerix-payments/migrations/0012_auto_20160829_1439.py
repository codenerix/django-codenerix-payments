# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0011_auto_20160826_1258'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='ref',
            field=models.CharField(default=None, max_length=50, verbose_name='Reference'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='ref',
            field=models.CharField(default=None, max_length=50, verbose_name='Reference'),
        ),
    ]
