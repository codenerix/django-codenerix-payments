# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0016_auto_20161021_1154'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='locator',
            field=models.CharField(unique=True, max_length=40, verbose_name='Locator'),
        ),
    ]
