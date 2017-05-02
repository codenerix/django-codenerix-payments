# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrequest',
            name='reverse',
            field=models.CharField(default='reverse', max_length=64, verbose_name='Reverse'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Plataforma', choices=[(b'redsys', b'Redsys')]),
        ),
    ]
