# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0002_auto_20160824_0950'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='action',
            field=models.CharField(max_length=7, verbose_name='Acci\xf3n', choices=[(b'confirm', 'Confirmada'), (b'cancel', 'Cancelar')]),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Plataforma', choices=[(b'url', b'Url'), (b'real', b'Real'), (b'paypalonline', b'Paypalonline'), (b'name', b'Name'), (b'taxes', b'Taxes')]),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='protocol',
            field=models.CharField(max_length=10, verbose_name='Protocolo', choices=[(b'paypal', 'Paypal'), (b'redsys', 'Redsys'), (b'redsysxml', 'Redsys XML')]),
        ),
    ]
