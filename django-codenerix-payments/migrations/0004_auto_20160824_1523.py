# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codenerix_payments', '0003_auto_20160824_1459'),
    ]

    operations = [
        migrations.AlterField(
            model_name='currency',
            name='name',
            field=models.CharField(unique=True, max_length=15, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='currency',
            name='price',
            field=models.FloatField(verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='currency',
            name='symbol',
            field=models.CharField(unique=True, max_length=2, verbose_name='Symbol'),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='answer',
            field=models.TextField(null=True, verbose_name='Answer', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='answer_date',
            field=models.DateTimeField(verbose_name='Answer date', null=True, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='error_txt',
            field=models.TextField(null=True, verbose_name='Error Text', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='ref',
            field=models.CharField(default=None, max_length=50, null=True, verbose_name='Reference'),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='request',
            field=models.TextField(null=True, verbose_name='Request', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentanswer',
            name='request_date',
            field=models.DateTimeField(verbose_name='Request date', null=True, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='action',
            field=models.CharField(max_length=7, verbose_name='Action', choices=[(b'confirm', 'Confirm'), (b'cancel', 'Cancel')]),
        ),
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='data',
            field=models.TextField(null=True, verbose_name='Data', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentconfirmation',
            name='ref',
            field=models.CharField(max_length=50, verbose_name='Reference'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='answer',
            field=models.TextField(null=True, verbose_name='Answer', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='answer_date',
            field=models.DateTimeField(verbose_name='Answer date', null=True, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='cancelled',
            field=models.BooleanField(default=False, verbose_name='Cancelled'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='error_txt',
            field=models.TextField(null=True, verbose_name='Error Text', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='notes',
            field=models.CharField(max_length=30, null=True, verbose_name='Notes', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='platform',
            field=models.CharField(max_length=20, verbose_name='Platform', choices=[(b'redsys', b'Redsys')]),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='protocol',
            field=models.CharField(max_length=10, verbose_name='Protocol', choices=[(b'paypal', 'Paypal'), (b'redsys', 'Redsys'), (b'redsysxml', 'Redsys XML')]),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='ref',
            field=models.CharField(max_length=50, verbose_name='Reference'),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='request',
            field=models.TextField(null=True, verbose_name='Request', blank=True),
        ),
        migrations.AlterField(
            model_name='paymentrequest',
            name='request_date',
            field=models.DateTimeField(verbose_name='Request date', null=True, editable=False, blank=True),
        ),
    ]
