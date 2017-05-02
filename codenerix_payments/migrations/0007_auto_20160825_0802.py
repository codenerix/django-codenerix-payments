# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0006_auto_20160824_1524'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentconfirmation',
            name='error',
            field=models.BooleanField(default=False, verbose_name='Error'),
        ),
        migrations.AddField(
            model_name='paymentconfirmation',
            name='error_txt',
            field=models.TextField(null=True, verbose_name='Error Text', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Platform', choices=[(b'paypalonline', b'Paypalonline')]),
        ),
    ]
