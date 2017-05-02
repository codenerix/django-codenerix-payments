# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0013_auto_20160829_1443'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='ref',
            field=models.CharField(default=None, max_length=50, null=True, verbose_name='Reference'),
        ),
    ]
