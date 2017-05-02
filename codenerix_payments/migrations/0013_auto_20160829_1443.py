# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0012_auto_20160829_1439'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='ref',
            field=models.CharField(default=None, max_length=50, null=True, verbose_name='Reference'),
        ),
    ]
