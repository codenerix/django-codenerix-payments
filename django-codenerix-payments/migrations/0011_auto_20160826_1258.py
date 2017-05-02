# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0010_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Platform'),
        ),
    ]
