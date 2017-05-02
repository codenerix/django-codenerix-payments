# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
import datetime
import hashlib

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0014_auto_20160829_1444'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrequest',
            name='locator',
            field=models.CharField(default=hashlib.sha1(
                (
                    str(time.time()) + str(datetime.datetime.now().microsecond)
                ).encode('utf-8')
            ).hexdigest(), max_length=40, null=False, verbose_name='Locator'),
        ),
    ]
