# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0002_auto_20160824_0950'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Plataforma', choices=[(b'sabadell', b'Sabadell')]),
        ),
    ]
