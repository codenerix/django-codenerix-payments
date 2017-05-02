# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0008_auto_20160825_0809'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrequest',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='Order Reference', validators=[django.core.validators.MaxValueValidator(2821109907455)]),
            preserve_default=False,
        ),
    ]
