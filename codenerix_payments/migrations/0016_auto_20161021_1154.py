# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from codenerix_payments.models import PaymentRequest

import time
import datetime
import hashlib

from django.db import migrations, models

def remake_locators(apps, schema_editor):
    prs = PaymentRequest.objects.all()
    for pr in prs:
        pr.locator=hashlib.sha1(str(time.time())+str(datetime.datetime.now().microsecond)).hexdigest()
        pr.save()

class Migration(migrations.Migration):
    
    dependencies = [
        ('codenerix_payments', '0015_paymentrequest_locator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='locator',
            field=models.CharField(default=b'94d5eeeaab540b416bd27fdbba990931501d3853', max_length=40, verbose_name='Locator'),
        ),
        migrations.RunPython(remake_locators)
    ]


