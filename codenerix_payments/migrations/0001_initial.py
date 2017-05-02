# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('name', models.CharField(unique=True, max_length=15, verbose_name='Nombre')),
                ('symbol', models.CharField(unique=True, max_length=2, verbose_name='Simbolo')),
                ('iso4217', models.CharField(unique=True, max_length=3, verbose_name='ISO 4217 Code')),
                ('price', models.FloatField(verbose_name='Precio')),
            ],
            options={
                'permissions': [('list_currency', 'Can list currency'), ('detail_currency', 'Can view currency')],
            },
        ),
        migrations.CreateModel(
            name='PaymentAnswer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('ref', models.CharField(default=None, max_length=50, null=True, verbose_name='Referencia')),
                ('error', models.BooleanField(default=False, verbose_name='Error')),
                ('error_txt', models.TextField(null=True, verbose_name='Error del text', blank=True)),
                ('request', models.TextField(null=True, verbose_name='Solicitud', blank=True)),
                ('answer', models.TextField(null=True, verbose_name='Respuesta', blank=True)),
                ('request_date', models.DateTimeField(verbose_name='Fecha de solicitud', null=True, editable=False, blank=True)),
                ('answer_date', models.DateTimeField(verbose_name='Fecha de respuesta', null=True, editable=False, blank=True)),
            ],
            options={
                'permissions': [('list_paymentanswer', 'Can list paymentanswer'), ('detail_paymentanswer', 'Can view paymentanswer')],
            },
        ),
        migrations.CreateModel(
            name='PaymentConfirmation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('ref', models.CharField(max_length=50, verbose_name='Referencia')),
                ('action', models.CharField(max_length=7, verbose_name='Acci\xf3n', choices=[(b'confirm', 'Confirmar'), (b'cancel', 'Cancelar')])),
                ('data', models.TextField(null=True, verbose_name='Dato', blank=True)),
            ],
            options={
                'permissions': [('list_paymentconfirmation', 'Can list paymentconfirmation'), ('detail_paymentconfirmation', 'Can view paymentconfirmation')],
            },
        ),
        migrations.CreateModel(
            name='PaymentRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('ref', models.CharField(max_length=50, verbose_name='Referencia')),
                ('platform', models.CharField(max_length=20, verbose_name='Plataforma', choices=[(b'sabadell', b'Sabadell')])),
                ('protocol', models.CharField(max_length=10, verbose_name='Protocol', choices=[(b'paypal', 'Paypal'), (b'redsys', 'Redsys'), (b'redsysxml', 'Redsys XML')])),
                ('real', models.BooleanField(default=False, verbose_name='Real')),
                ('error', models.BooleanField(default=False, verbose_name='Error')),
                ('error_txt', models.TextField(null=True, verbose_name='Error del text', blank=True)),
                ('cancelled', models.BooleanField(default=False, verbose_name='Cancelado')),
                ('total', models.FloatField(verbose_name='Total')),
                ('notes', models.CharField(max_length=30, null=True, verbose_name='Notas', blank=True)),
                ('request', models.TextField(null=True, verbose_name='Solicitud', blank=True)),
                ('answer', models.TextField(null=True, verbose_name='Respuesta', blank=True)),
                ('request_date', models.DateTimeField(verbose_name='Fecha de solicitud', null=True, editable=False, blank=True)),
                ('answer_date', models.DateTimeField(verbose_name='Fecha de respuesta', null=True, editable=False, blank=True)),
                ('currency', models.ForeignKey(related_name='payments', to='codenerix_payments.Currency')),
            ],
            options={
                'permissions': [('list_paymentrequest', 'Can list paymentrequest'), ('detail_paymentrequest', 'Can view paymentrequest')],
            },
        ),
        migrations.AddField(
            model_name='paymentconfirmation',
            name='payment',
            field=models.ForeignKey(related_name='paymentconfirmations', to='codenerix_payments.PaymentRequest'),
        ),
        migrations.AddField(
            model_name='paymentanswer',
            name='payment',
            field=models.ForeignKey(related_name='paymentanswers', to='codenerix_payments.PaymentRequest'),
        ),
    ]
