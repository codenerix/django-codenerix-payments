# -*- coding: utf-8 -*-
#
# django-codenerix-payments
#
# Copyright 2017 Centrologic Computational Logistic Center S.L.
#
# Project URL : http://www.codenerix.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import paypalrestsdk
import importlib
import hashlib
import base64
import time
import datetime
import requests
import math
from Crypto.Cipher import DES3
from Crypto.Hash import HMAC, SHA256
# from suds.client import Client as SOAPClient

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.urls import reverse, resolve
from django.utils import timezone
from django.utils.encoding import smart_text
from django.core.validators import MaxValueValidator

from codenerix.models import CodenerixModel
from codenerix.helpers import CodenerixEncoder

CURRENCY_MAX_DIGITS = getattr(settings, 'CDNX_INVOICING_CURRENCY_MAX_DIGITS', 10)
CURRENCY_DECIMAL_PLACES = getattr(settings, 'CDNX_INVOICING_CURRENCY_DECIMAL_PLACES', 2)

PAYMENT_PROTOCOL_CHOICES = (
    ('paypal', _('Paypal')),
    ('redsys', _('Redsys')),
    ('redsysxml', _('Redsys XML')),
)

PAYMENT_CONFIRMATION_CHOICES = (
    ('confirm', _('Confirm')),
    ('cancel', _('Cancel')),
)

REDSYS_LANG_MAP = {
    'es': '001',
    'en': '002',
    'ca': '003',
    'fr': '004',
    'de': '005',
    'nl': '006',
    'it': '007',
    'sv': '008',
    'pt': '009',
    'pl': '011',
    'gl': '012',
    'eu': '013',
    'da': '208',
}


def redsys_signature(authkey, order, paramsb64, recode=False):
    # Build the signature
    iv = b'\0\0\0\0\0\0\0\0'
    k = DES3.new(authkey, DES3.MODE_CBC, iv)
    ceros = b'\0' * (len(order) % 8)
    claveOp = k.encrypt(order + ceros.decode())

    # Realizo la codificacion SHA256
    dig = HMAC.new(claveOp, msg=paramsb64.encode(), digestmod=SHA256).digest()
    signature = base64.b64encode(dig).decode()
    if recode:
        signature = signature.replace("+", "-").replace("/", "_")
    return signature


def redsys_error(code):
    errors = {}
    errors['0101'] = u'Tarjeta Caducada.'
    errors['0102'] = u'Tarjeta en excepción transitoria o bajo sospecha de fraude.'
    errors['0104'] = u'Operación no permitida para esa tarjeta o terminal.'
    errors['0106'] = u'Intentos de PIN excedidos.'
    errors['0116'] = u'Disponible Insuficiente.'
    errors['0118'] = u'Tarjeta no Registrada.'
    errors['0125'] = u'Tarjeta no efectiva.'
    errors['0129'] = u'Código de seguridad (CVV2/CVC2) incorrecto.'
    errors['0180'] = u'Tarjeta ajena al servicio.'
    errors['0184'] = u'Error en la autenticación del titular.'
    errors['0190'] = u'Denegación sin especificar motivo.'
    errors['0191'] = u'Fecha de caducidad errónea.'
    errors['0202'] = u'Tarjeta en excepción transitoria o bajo sospecha de fraude con retirada de tarjeta.'
    errors['0904'] = u'Comercio no registrado en FUC.'
    errors['0909'] = u'Error de sistema.'
    errors['0912'] = u'Emisor no disponible.'
    errors['0913'] = u'Pedido repetido.'
    errors['0944'] = u'Sesión Incorrecta.'
    errors['0950'] = u'Operación de devolución no permitida.'
    errors['9064'] = u'Número de posiciones de la tarjeta incorrecto.'
    errors['9078'] = u'No existe método de pago válido para esa tarjeta.'
    errors['9093'] = u'Tarjeta no existente.'
    errors['9094'] = u'Rechazo servidores internacionales.'
    errors['9104'] = u'Comercio con “titular seguro” y titular sin clave de compra segura.'
    errors['9218'] = u'El comercio no permite op. seguras por entrada /operaciones.'
    errors['9253'] = u'Tarjeta no cumple el check-digit.'
    errors['9256'] = u'El comercio no puede realizar preautorizaciones.'
    errors['9257'] = u'Esta tarjeta no permite operativa de preautorizaciones.'
    errors['9261'] = u'Operación detenida por superar el control de restricciones en la entrada al SIS.'
    errors['9912'] = u'Emisor no disponible.'
    errors['9913'] = u'Error en la confirmación que el comercio envía al TPV Virtual (solo aplicable en la opción de sincronización SOAP).'
    errors['9914'] = u'Confirmación “KO” del comercio (solo aplicable en la opción de sincronización SOAP).'
    errors['9915'] = u'A petición del usuario se ha cancelado el pago.'
    errors['9928'] = u'Anulación de autorización en diferido realizada por el SIS (proceso batch).'
    errors['9929'] = u'Anulación de autorización en diferido realizada por el comercio.'
    errors['9997'] = u'Se está procesando otra transacción en SIS con la misma tarjeta.'
    errors['9998'] = u'Operación en proceso de solicitud de datos de tarjeta.'
    errors['9999'] = u'Operación que ha sido redirigida al emisor a autenticar.'
    errors['SIS0007'] = u'Error al desmontar el XML de entrada.'
    errors['SIS0008'] = u'Error falta Ds_Merchant_MerchantCode.'
    errors['SIS0009'] = u'Error de formato en Ds_Merchant_MerchantCode.'
    errors['SIS0010'] = u'Error falta Ds_Merchant_Terminal.'
    errors['SIS0011'] = u'Error de formato en Ds_Merchant_Terminal.'
    errors['SIS0014'] = u'Error de formato en Ds_Merchant_Order.'
    errors['SIS0015'] = u'Error falta Ds_Merchant_Currency.'
    errors['SIS0016'] = u'Error de formato en Ds_Merchant_Currency.'
    errors['SIS0017'] = u'Error no se admiten operaciones en pesetas.'
    errors['SIS0018'] = u'Error falta Ds_Merchant_Amount.'
    errors['SIS0019'] = u'Error de formato en Ds_Merchant_Amount.'
    errors['SIS0020'] = u'Error falta Ds_Merchant_MerchantSignature.'
    errors['SIS0021'] = u'Error la Ds_Merchant_MerchantSignature viene vacía.'
    errors['SIS0022'] = u'Error de formato en Ds_Merchant_TransactionType.'
    errors['SIS0023'] = u'Error Ds_Merchant_TransactionType desconocido.'
    errors['SIS0024'] = u'Error Ds_Merchant_ConsumerLanguage tiene mas de 3 posiciones.'
    errors['SIS0025'] = u'Error de formato en Ds_Merchant_ConsumerLanguage.'
    errors['SIS0026'] = u'Error No existe el comercio / terminal enviado.'
    errors['SIS0027'] = u'Error Moneda enviada por el comercio es diferente a la que tiene asignada para ese terminal.'
    errors['SIS0028'] = u'Error Comercio / terminal está dado de baja.'
    errors['SIS0030'] = u'Error en un pago con tarjeta ha llegado un tipo de operación no valido.'
    errors['SIS0031'] = u'Método de pago no definido.'
    errors['SIS0033'] = u'Error en un pago con móvil ha llegado un tipo de operación que no es ni pago ni preautorización.'
    errors['SIS0034'] = u'Error de acceso a la Base de Datos.'
    errors['SIS0037'] = u'El número de teléfono no es válido.'
    errors['SIS0038'] = u'Error en java.'
    errors['SIS0040'] = u'Error el comercio / terminal no tiene ningún método de pago asignado.'
    errors['SIS0041'] = u'Error en el cálculo de la firma de datos del comercio.'
    errors['SIS0042'] = u'La firma enviada no es correcta.'
    errors['SIS0043'] = u'Error al realizar la notificación on-line.'
    errors['SIS0046'] = u'El BIN de la tarjeta no está dado de alta.'
    errors['SIS0051'] = u'Error número de pedido repetido.'
    errors['SIS0054'] = u'Error no existe operación sobre la que realizar la devolución.'
    errors['SIS0055'] = u'Error no existe más de un pago con el mismo número de pedido.'
    errors['SIS0056'] = u'La operación sobre la que se desea devolver no está autorizada.'
    errors['SIS0057'] = u'El importe a devolver supera el permitido.'
    errors['SIS0058'] = u'Inconsistencia de datos, en la validación de una confirmación.'
    errors['SIS0059'] = u'Error no existe operación sobre la que realizar la devolución.'
    errors['SIS0060'] = u'Ya existe una confirmación asociada a la preautorización.'
    errors['SIS0061'] = u'La preautorización sobre la que se desea confirmar no está autorizada.'
    errors['SIS0062'] = u'El importe a confirmar supera el permitido.'
    errors['SIS0063'] = u'Error. Número de tarjeta no disponible.'
    errors['SIS0064'] = u'Error. El número de tarjeta no puede tener más de 19 posiciones.'
    errors['SIS0065'] = u'Error. El número de tarjeta no es numérico.'
    errors['SIS0066'] = u'Error. Mes de caducidad no disponible.'
    errors['SIS0067'] = u'Error. El mes de la caducidad no es numérico.'
    errors['SIS0068'] = u'Error. El mes de la caducidad no es válido.'
    errors['SIS0069'] = u'Error. Año de caducidad no disponible.'
    errors['SIS0070'] = u'Error. El Año de la caducidad no es numérico.'
    errors['SIS0071'] = u'Tarjeta caducada.'
    errors['SIS0072'] = u'Operación no anulable.'
    errors['SIS0074'] = u'Error falta Ds_Merchant_Order.'
    errors['SIS0075'] = u'Error el Ds_Merchant_Order tiene menos de 4 posiciones o más de 12.'
    errors['SIS0076'] = u'Error el Ds_Merchant_Order no tiene las cuatro primeras posiciones numéricas.'
    errors['SIS0078'] = u'Método de pago no disponible.'
    errors['SIS0079'] = u'Error al realizar el pago con tarjeta.'
    errors['SIS0081'] = u'La sesión es nueva, se han perdido los datos almacenados.'
    errors['SIS0084'] = u'El valor de Ds_Merchant_Conciliation es nulo.'
    errors['SIS0085'] = u'El valor de Ds_Merchant_Conciliation no es numérico.'
    errors['SIS0086'] = u'El valor de Ds_Merchant_Conciliation no ocupa 6 posiciones.'
    errors['SIS0089'] = u'El valor de Ds_Merchant_ExpiryDate no ocupa 4 posiciones.'
    errors['SIS0092'] = u'El valor de Ds_Merchant_ExpiryDate es nulo.'
    errors['SIS0093'] = u'Tarjeta no encontrada en la tabla de rangos.'
    errors['SIS0094'] = u'La tarjeta no fue autenticada como 3D Secure.'
    errors['SIS0097'] = u'Valor del campo Ds_Merchant_CComercio no válido.'
    errors['SIS0098'] = u'Valor del campo Ds_Merchant_CVentana no válido.'
    errors['SIS0112'] = u'Error. El tipo de transacción especificado en Ds_Merchant_Transaction_Type no esta permitido.'
    errors['SIS0113'] = u'Excepción producida en el servlet de operaciones.'
    errors['SIS0114'] = u'Error, se ha llamado con un GET en lugar de un POST.'
    errors['SIS0115'] = u'Error no existe operación sobre la que realizar el pago de la cuota.'
    errors['SIS0116'] = u'La operación sobre la que se desea pagar una cuota no es una operación válida.'
    errors['SIS0117'] = u'La operación sobre la que se desea pagar una cuota no está autorizada.'
    errors['SIS0118'] = u'Se ha excedido el importe total de las cuotas.'
    errors['SIS0119'] = u'Valor del campo Ds_Merchant_DateFrecuency no válido.'
    errors['SIS0120'] = u'Valor del campo Ds_Merchant_CargeExpiryDate no válido.'
    errors['SIS0121'] = u'Valor del campo Ds_Merchant_SumTotal no válido.'
    errors['SIS0122'] = u'Valor del campo Ds_merchant_DateFrecuency o Ds_Merchant_SumTotal tiene formato incorrecto.'
    errors['SIS0123'] = u'Se ha excedido la fecha tope para realizar transacciones.'
    errors['SIS0124'] = u'No ha transcurrido la frecuencia mínima en un pago recurrente sucesivo.'
    errors['SIS0132'] = u'La fecha de Confirmación de Autorización no puede superar en más de 7 días a la de Preautorización.'
    errors['SIS0133'] = u'La fecha de Confirmación de Autenticación no puede superar en mas de 45 días a la de Autenticación Previa.'
    errors['SIS0139'] = u'Error el pago recurrente inicial está duplicado.'
    errors['SIS0142'] = u'Tiempo excedido para el pago.'
    errors['SIS0197'] = u'Error al obtener los datos de cesta de la compra en operación tipo pasarela.'
    errors['SIS0198'] = u'Error el importe supera el límite permitido para el comercio.'
    errors['SIS0199'] = u'Error el número de operaciones supera el límite permitido para el comercio.'
    errors['SIS0200'] = u'Error el importe acumulado supera el límite permitido para el comercio.'
    errors['SIS0214'] = u'El comercio no admite devoluciones.'
    errors['SIS0216'] = u'Error Ds_Merchant_CVV2 tiene mas de 3/4 posiciones.'
    errors['SIS0217'] = u'Error de formato en Ds_Merchant_CVV2.'
    errors['SIS0218'] = u'El comercio no permite operaciones seguras por la entrada /operaciones.'
    errors['SIS0219'] = u'Error el número de operaciones de la tarjeta supera el límite permitido para el comercio.'
    errors['SIS0220'] = u'Error el importe acumulado de la tarjeta supera el límite permitido para el comercio.'
    errors['SIS0221'] = u'Error el CVV2 es obligatorio.'
    errors['SIS0222'] = u'Ya existe una anulación asociada a la preautorización.'
    errors['SIS0223'] = u'La preautorización que se desea anular no está autorizada.'
    errors['SIS0224'] = u'El comercio no permite anulaciones por no tener firma ampliada.'
    errors['SIS0225'] = u'Error no existe operación sobre la que realizar la anulación.'
    errors['SIS0226'] = u'Inconsistencia de datos, en la validación de una anulación.'
    errors['SIS0227'] = u'Valor del campo Ds_Merchan_TransactionDate no válido.'
    errors['SIS0229'] = u'No existe el código de pago aplazado solicitado.'
    errors['SIS0252'] = u'El comercio no permite el envío de tarjeta.'
    errors['SIS0253'] = u'La tarjeta no cumple el check-digit.'
    errors['SIS0254'] = u'El número de operaciones de la IP supera el límite permitido por el comercio.'
    errors['SIS0255'] = u'El importe acumulado por la IP supera el límite permitido por el comercio.'
    errors['SIS0256'] = u'El comercio no puede realizar preautorizaciones.'
    errors['SIS0257'] = u'Esta tarjeta no permite operativa de preautorizaciones.'
    errors['SIS0258'] = u'Inconsistencia de datos, en la validación de una confirmación.'
    errors['SIS0261'] = u'Operación detenida por superar el control de restricciones en la entrada al SIS.'
    errors['SIS0270'] = u'El comercio no puede realizar autorizaciones en diferido.'
    errors['SIS0274'] = u'Tipo de operación desconocida o no permitida por esta entrada al SIS.'
    errors['SIS0298'] = u'El comercio no permite realizar operaciones de Tarjeta en Archivo.'
    errors['SIS0319'] = u'El comercio no pertenece al grupo especificado en Ds_Merchant_Group.'
    errors['SIS0321'] = u'La referencia indicada en Ds_Merchant_Identifier no está asociada al comercio.'
    errors['SIS0322'] = u'Error de formato en Ds_Merchant_Group.'
    errors['SIS0325'] = u'Se ha pedido no mostrar pantallas pero no se ha enviado ninguna referencia de tarjeta.'
    errors['SIS0334'] = u'Superado los límites de compra con esta tarjeta o IP (ver parámetros en Redsys). [Velocity checks]'
    errors['SIS0429'] = u'Error en la versión enviada por el comercio en el parámetro Ds_SignatureVersion'
    errors['SIS0430'] = u'Error al decodificar el parámetro Ds_MerchantParameters'
    errors['SIS0431'] = u'Error del objeto JSON que se envía codificado en el parámetro Ds_MerchantParameters'
    errors['SIS0432'] = u'Error FUC del comercio erróneo'
    errors['SIS0433'] = u'Error Terminal del comercio erróneo'
    errors['SIS0434'] = u'Error ausencia de número de pedido en la operación enviada por el comercio'
    errors['SIS0435'] = u'Error en el cálculo de la firma'
    code2 = "SIS{}".format(code)
    code3 = code.replace("SIS", "")
    if code in errors:
        return errors[code]
    elif code2 in errors:
        return errors[code2]
    elif code3 in errors:
        return errors[code3]
    else:
        return _('UNKNOWN CODE {code}').format(code=code)


class Currency(CodenerixModel):
    '''
    Currencies
    '''
    name = models.CharField(_('Name'), max_length=15, blank=False, null=False, unique=True)
    symbol = models.CharField(_('Symbol'), max_length=2, blank=False, null=False, unique=True)
    iso4217 = models.CharField(_('ISO 4217 Code'), max_length=3, blank=False, null=False, unique=True)
    price = models.DecimalField(_('Price'), blank=False, null=False, max_digits=CURRENCY_MAX_DIGITS, decimal_places=CURRENCY_DECIMAL_PLACES)

    def __unicode__(self):
        return u"{0} ({1})".format(smart_text(self.name), smart_text(self.symbol))

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(('name', _('Name'), 100))
        fields.append(('symbol', _('Symbol'), 100))
        fields.append(('price', _('Price'), 100))
        return fields

    def rate(self, buy):
        # Prepare the call
        url = "http://api.fixer.io/latest"
        payload = {'base': self.iso4217, 'symbols': buy.iso4217}
        r = requests.get(url, params=payload)
        if not r.raise_for_status():
            # Read the answer
            data = r.json()
            rate = data['rates'][buy.iso4217]
        return rate


class PaymentRequest(CodenerixModel):
    '''
    ref: used to store the reference on the remote system (bank, paypal, google checkout, adyen,...), it is separated for quicker location
    reverse: used to store the reverse URL for this request when we get back an user from a remote system
    platform: selected platform for payment to happen (it is linked to request/answer)
    protocol: selected protocol for payment to happen (it is linked to request/answer)
    request/answer: usable structure for the selected payment system
    '''
    locator = models.CharField(_('Locator'), max_length=40, unique=True, blank=False, null=False)
    ref = models.CharField(_('Reference'), max_length=50, blank=False, null=True, default=None)
    order = models.PositiveIntegerField(_('Order Reference'), blank=False, null=False, validators=[MaxValueValidator(2821109907455)])  # 2821109907455 => codenerix::hex36 = 8 char
    reverse = models.CharField(_('Reverse'), max_length=64, blank=False, null=False)
    currency = models.ForeignKey(Currency, blank=False, null=False, related_name='payments', on_delete=models.CASCADE)
    platform = models.CharField(_('Platform'), max_length=20, blank=False, null=False)
    protocol = models.CharField(_('Protocol'), choices=PAYMENT_PROTOCOL_CHOICES, max_length=10, blank=False, null=False)
    real = models.BooleanField(_('Real'), blank=False, null=False, default=False)
    error = models.BooleanField(_('Error'), blank=False, null=False, default=False)
    error_txt = models.TextField(_('Error Text'), blank=True, null=True)
    cancelled = models.BooleanField(_('Cancelled'), blank=False, null=False, default=False)
    total = models.FloatField(_('Total'), blank=False, null=False)
    notes = models.CharField(_('Notes'), max_length=30, blank=True, null=True)    # Observaciones

    request = models.TextField(_('Request'), blank=True, null=True)
    answer = models.TextField(_('Answer'), blank=True, null=True)
    request_date = models.DateTimeField(_("Request date"), editable=False, blank=True, null=True)
    answer_date = models.DateTimeField(_("Answer date"), editable=False, blank=True, null=True)

    def __unicode__(self):
        return u"PayReq({0}):{1}_{2}:{3}|{4}:{5}[{6}]".format(self.pk, self.locator, self.platform, self.protocol, self.ref, self.total, self.order)

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(('is_paid', _('Is paid?'), 100))
        fields.append(('locator', _('Locator'), 100))
        fields.append(('order', _('Order Reference'), 100))
        fields.append(('request_date', _('Request date'), 100))
        fields.append(('answer_date', _('Answer date'), 100))
        fields.append(('platform', _('Platform'), 100))
        fields.append(('protocol', _('Protocol'), 100))
        fields.append(('total', _('Total'), 100))
        fields.append(('currency', _('Currency'), 100))
        fields.append(('cancelled', _('Cancelled'), 100))
        fields.append(('error', _('Error'), 100))
        if getattr(settings, 'CDNX_PAYMENTS_REQUEST_PAY', False):
            fields.append(('get_approval_list', _('Pay'), 100))
        return fields

    def is_paid(self):
        return bool(self.paymentanswers.filter(ref__isnull=False, error=False).first())

    def get_approval_list(self):
        try:
            apr = self.get_approval()
        except PaymentError as e:
            apr = {'error': str(e)}
        return apr

    def get_approval(self):
        # If the transaction wasn't cancelled
        if not self.cancelled and self.answer:
            # Get approval link
            config = settings.PAYMENTS.get(self.platform, {})
            meta = settings.PAYMENTS.get('meta', {})
            if config and meta:
                if self.protocol == 'paypal':
                    approval = self.__get_approval_paypal(meta, config)
                elif self.protocol == 'redsys' or self.protocol == 'redsysxml':
                    approval = self.__get_approval_redsys(meta, config)
                else:
                    raise PaymentError(1, _("Unknown protocol '{protocol}'").format(protocol=self.protocol))
            else:
                raise PaymentError(2, _("Unknown platform '{platform}'").format(platform=self.platform))
        else:
            # No approval information available
            approval = {}

        # Return the approval INFO
        return approval

    def __get_approval_paypal(self, meta, config):
        # Initialize
        approval = {}
        # Get dict
        answer = json.loads(self.answer)
        # Get links inside the answer
        links = answer['links']
        for link in links:
            # Look for approval URL
            if link['rel'] == 'approval_url':
                approval['url'] = link['href']
                break
        return approval

    def __get_approval_redsys(self, meta, config):
        # Initialize
        approval = {}
        # Get dict
        # answer = json.loads(self.answer) # It wasn't being used !!! <--- DEPRECATED???
        params = {}

        # AMOUNT: 12 Numeric - Last 2 positions are decimals except for YENS
        amount = int(math.ceil(float(self.total) * 100))
        params['DS_MERCHANT_AMOUNT'] = str(amount)

        # Sanity check for total amount to charge
        if float(amount) / 100 != self.total:
            raise PaymentError(11, _("Amount doesn't match to the payment request: stored={stored} - protocol={protocol}").format(stored=self.total, protocol=float(amount) / 100))

        # CURRENCY: 4 Numeric
        curcode = self.currency.iso4217
        if curcode == 'EUR':
            curcode = '978'
        elif curcode == 'USD':
            curcode = '840'
        elif curcode == 'GBP':
            curcode = '826'
        elif curcode == 'JPY':
            curcode = '392'
        elif curcode == 'CHF':
            curcode = '756'
        elif curcode == 'CAD':
            curcode = '124'
        else:
            raise PaymentError(1, _("Unknown currency for this protocol '{currency}' (available are: EUR, USD, GBP, JPY, CHF & CAD)").format(currency=curcode))
        params['DS_MERCHANT_CURRENCY'] = curcode

        # GET DETAILS
        # name = meta.get('name','')
        url = meta.get('url', '')  # URL when not using SSL
        urlssl = meta.get('urlssl', '')  # URL when using SSL
        ssl = meta.get('ssl', True)  # If the system can use SSL connections
        sslvalid = meta.get('sslvalid', True)  # If the certificate is valid officially

        # Confirm/Cancel
        if ssl:
            urllink = urlssl
        else:
            urllink = url

        # Success
        if sslvalid:
            urlsuccess = urllink
        else:
            urlsuccess = url

        # Prepare configuration
        code = config.get('merchant_code', '')
        authkey = base64.b64decode(config.get('auth_key', ''))
        success_url = urlsuccess + reverse('payment_url', kwargs={'action': 'success', 'locator': self.locator})
        return_url = urllink + reverse('payment_url', kwargs={'action': 'confirm', 'locator': self.locator})
        cancel_url = urllink + reverse('payment_url', kwargs={'action': 'cancel', 'locator': self.locator})

        # DETAILS 1
        ce = CodenerixEncoder()
        params['DS_MERCHANT_ORDER'] = '{}'.format(ce.numeric_encode(self.pk, dic='hex36', length=8, cfill='A'))  # ORDER NUMBER: Min 4 Alfa Numeric - Max 12 Alfa Numeric
        # #fields['Ds_Merchant_Titular'] = 'TIT'                   # TITULAR: Max 60 Alfa Numeric
        # #fields['Ds_Merchant_ProductDescription'] = 'DES'        # PRODUCT DESCRIPTION: Max 125 Alfa Numeric
        params['DS_MERCHANT_MERCHANTCODE'] = code               # SELF CODE: 9 Numeric
        params['DS_MERCHANT_MERCHANTURL'] = success_url         # SELF URL BACKEND: 250 Alfa Numeric
        params['DS_MERCHANT_URLOK'] = return_url                # SELF URL USER OK: 250 Alfa Numeric
        params['DS_MERCHANT_URLKO'] = cancel_url                # SELF URL USER KO: 250 Alfa Numeric
        # #fields['Ds_Merchant_MerchantName'] = name               # SELF NAME: 25 Alfa Numeric

        # LANGUAGE: 3 Numeric
        # lang_code = 0   # Client
        # #fields['Ds_Merchant_ConsumerLanguage'] = lang_code

        # DETAILS 2
        params['DS_MERCHANT_TERMINAL'] = '1'                      # TERMINAL: 3 Numeric (Fixed to 1)
        # #fields['Ds_Merchant_MerchantData'] = 'INFO'               # SELF INFO: 1024 Alfa Numeric
        params['DS_MERCHANT_TRANSACTIONTYPE'] = '0'               # TRANSACTION TYPE: 1 Numeric (Fixed to 1 - Standard Payment)
        # fields['Ds_Merchant_AuthorisationCode'] = ''            # AUTH CODE: 6 Numeric (OPTIONAL)
        # #fields['Ds_Merchant_Identifier'] = 'IDENT'                # IDENTIFIER: Max 40 Alfa Numeric
        # fields['Ds_Merchant_Group'] = ''                        # GROUP: Max 9 Numeric (OPTIONAL)
        # fields['Ds_Merchant_DirectPayment'] = ''                # DIRECT PAYMENT: 'True' / 'false' (OPTIONAL)
        # fields['Ds_Merchant_PayMethod'] = ''                    # METHOD: C:CARD / O:IUPAY (only for e-commerce with IUPAY support)

        # Build the request
        paramsjson = json.dumps(params).encode()
        paramsb64 = base64.b64encode(paramsjson).decode()
        # try:
        #    paramsb64 = ''.join(unicode(base64.encodestring(paramsjson), 'utf-8')).splitlines()
        # except NameError:
        #    paramsb64 = ''.join(base64.encodestring(paramsjson)).splitlines()

        # Build the signature
        signature = redsys_signature(authkey, params['DS_MERCHANT_ORDER'], paramsb64)

        # Prepare the form
        form = {}
        form['Ds_SignatureVersion'] = 'HMAC_SHA256_V1'
        form['Ds_MerchantParameters'] = paramsb64
        form['Ds_Signature'] = signature

        # xml =   '<DS_MERCHANT_AMOUNT>'+params['DS_MERCHANT_AMOUNT']+'</DS_MERCHANT_AMOUNT>'
        # xml+=   '<DS_MERCHANT_ORDER>'+params['DS_MERCHANT_ORDER']+'</DS_MERCHANT_ORDER>'
        # xml+=   '<DS_MERCHANT_MERCHANTCODE>'+params['DS_MERCHANT_MERCHANTCODE']+'</DS_MERCHANT_MERCHANTCODE>'
        # xml+=   '<DS_MERCHANT_CURRENCY>'+params['DS_MERCHANT_CURRENCY']+'</DS_MERCHANT_CURRENCY>'
        # xml+=   '<DS_MERCHANT_PAN>'+card['number']+'</DS_MERCHANT_PAN>'
        # xml+=   '<DS_MERCHANT_CVV2>'+card['ccv2']+'</DS_MERCHANT_CVV2>'
        # xml+=   '<DS_MERCHANT_TRANSACTIONTYPE>'+params['DS_MERCHANT_TRANSACTIONTYPE']+'</DS_MERCHANT_TRANSACTIONTYPE>'
        # xml+=   '<DS_MERCHANT_TERMINAL>'+params['DS_MERCHANT_TERMINAL']+'</DS_MERCHANT_TERMINAL>'
        # xml+=   '<DS_MERCHANT_EXPIRYDATE>'+card['expiry']['year']+card['expiry']['month']+'</DS_MERCHANT_EXPIRYDATE>'
        # Build the signature
        # iv = b'\0\0\0\0\0\0\0\0'
        # k = DES3.new(authkey, DES3.MODE_CBC, iv)
        # claveOp = k.encrypt(params['DS_MERCHANT_ORDER'])

        # Realizo la codificacion SHA256
        # dig = HMAC.new(claveOp, msg=xml, digestmod=SHA256).digest()
        # signature = base64.b64encode(dig)
        # signature=signature.replace("+","-").replace("/","_")

        # Add signature
        # finalxml ='<REQUEST>'
        # finalxml+=    '<DATOSENTRADA>'
        # finalxml+=        xml
        # finalxml+=    '</DATOSENTRADA>'
        # finalxml+=    '<DS_SIGNATUREVERSION>HMAC_SHA256_V1</DS_SIGNATUREVERSION>'
        # finalxml+=    '<DS_SIGNATURE>'
        # finalxml+=        signature
        # finalxml+=    '</DS_SIGNATURE>'
        # finalxml+='</REQUEST>'

        # path = "/home/br0th3r/mixentradas/payments"
        # print 1
        # cli = SOAPClient("file://{}/redsys_test.wsdl".format(path))
        # cli = SOAPClient("file://{}/redsys_real.wsdl".format(path))
        # print 2
        # m=cli.service.trataPeticion(finalxml)
        # print 3
        # print m

        # Decide endpoint
        if self.real:
            endpoint = "https://sis.redsys.es/sis/realizarPago"
        else:
            endpoint = "https://sis-t.redsys.es:25443/sis/realizarPago"

        # Set aproval information
        approval['url'] = endpoint
        approval['form'] = form
        return approval

    def save(self, *args, **kwargs):

        # Check if we are a new object
        if self.pk:
            new = False
        else:
            new = True
            # Autoset locator

            info_decode = str(time.time()) + str(datetime.datetime.now().microsecond)
            self.locator = hashlib.sha1(info_decode.encode()).hexdigest()

            # Autoset environment
            self.real = settings.PAYMENTS.get('meta', {}).get('real', False)
            # Autoset protocol
            self.protocol = None
            protocol = settings.PAYMENTS.get(self.platform, {}).get('protocol', None)
            for (key, name) in PAYMENT_PROTOCOL_CHOICES:
                if key == protocol:
                    self.protocol = key
            if self.protocol is None:
                raise PaymentError(8, _("Unknown platform '{platform}'").format(platorm=self.platform))

        # If no orther specified
        auto_set_order = not self.order
        if auto_set_order:
            self.order = 0

        # Save the model like always
        m = super(PaymentRequest, self).save(*args, **kwargs)

        # Autoset order
        if auto_set_order:
            self.order = self.pk

        # Execute specific actions for the payment system
        if new:
            if self.platform in settings.PAYMENTS:
                config = settings.PAYMENTS.get(self.platform, {})
                meta = settings.PAYMENTS.get('meta', {})
                if self.real == meta.get('real', False):
                    if self.protocol == 'paypal':
                        self.__save_paypal(meta, config)
                    elif self.protocol in ['redsys', 'redsysxml']:
                        # Save request as we go since we don't have to do anything else
                        now = timezone.now()
                        self.request = '{}'
                        self.answer = '{}'
                        self.request_date = now
                        self.answer_date = now
                        self.save()
                    else:
                        # Unknown protocol selected
                        raise PaymentError(1, _("Unknown protocol '{protocol}'").format(protocol=self.protocol))
                else:
                    # Request and configuration do not match
                    if meta.get('real', False):
                        envsys = 'REAL'
                    else:
                        envsys = 'TEST'
                    if self.real:
                        envself = 'REAL'
                    else:
                        envself = 'TEST'
                    raise PaymentError(2, _("Wrong environment: this transaction is for '{selfenviron}' environment and system is set to '{sysenviron}'").format(selfenviron=envself, sysenviron=envsys))
            else:
                raise PaymentError(8, _("Platform '{platform}' not configured in your system").format(platform=self.platform))

        # Return the model we have created
        return m

    def __save_paypal(self, meta, config):
        # Select environment
        if self.real:
            environment = "live"
        else:
            environment = "sandbox"

        # Get details
        client_id = config.get('id', None)
        client_secret = config.get('secret', None)
        # If the system can use SSL connections
        ssl = meta.get('ssl', True)
        if ssl:
            # URL when using SSL
            url = meta.get('urlssl', '')
        else:
            # URL when not using SSL
            url = meta.get('url', '')
        return_url = url + reverse('payment_url', kwargs={'action': 'confirm', 'locator': self.locator})
        cancel_url = url + reverse('payment_url', kwargs={'action': 'cancel', 'locator': self.locator})

        # Configure
        paypalrestsdk.configure({
            "mode": environment,
            "client_id": client_id,
            "client_secret": client_secret,
        })

        # Request
        ce = CodenerixEncoder()
        request = {
            "intent": "sale",
            "payer": {
                "payment_method": "paypal",
            },
            "redirect_urls": {
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
            "transactions": [
                {
                    "invoice_number": ce.numeric_encode(self.order, dic='hex36', length=8, cfill='A'),
                    "amount": {
                        "total": self.total,
                        "currency": self.currency.iso4217.upper(),
                    },
                    "description": self.notes,
                },
            ],
        }

        # Save request
        self.request = json.dumps(request)
        self.request_date = timezone.now()
        self.save()

        # Create payment in Paypal
        payment = paypalrestsdk.Payment(request)

        # Check result
        if payment.create():
            # Convert payment to dict
            answer = payment.to_dict()
            # Get Reference
            self.ref = answer['id']
            # Build request
            self.answer = json.dumps(answer)

        else:
            # Get error and save
            self.error = True
            self.error_txt = json.dumps(payment.error)

        # Save everything
        self.answer_date = timezone.now()
        self.save()

    def notify(self, request):
        # with open("/tmp/codenerix_transaction.txt", "a") as F:
        if True:
            import datetime
            now = datetime.datetime.now()
            # F.write("\n\n{} -     > NOTIFY FUNCTION\n".format(now))
            if self.reverse == 'autorender':
                func = resolve(reverse('CNDX_payments_confirmation', kwargs={'locator': 0, 'action': 'success', 'error': 0})).func
            else:
                func = resolve(reverse(self.reverse, kwargs={'locator': 0, 'action': 'success', 'error': 0})).func

            # Detect if it is class based view
            module = func.__module__
            name = func.__name__
            mod = importlib.import_module(module)
            cl = getattr(mod, name)

            # F.write("{} -     > DETAILS:\n".format(now))
            # F.write("{} -          module:{}\n".format(now, module))
            # F.write("{} -            name:{}\n".format(now, name))
            # F.write("{} -            func:{}\n".format(now, func))
            # F.write("{} -              cl:{}\n".format(now, cl))
            # F.flush()

            # Decide what to do
            try:
                # F.write("{} -     > NOTIFY DECISION\n".format(now))
                # F.flush()
                if getattr(cl, "payment_paid", None):
                    # F.write("{} -     > NOTIFY PAID -> CLASS payment_paid({},{},{},{})\n".format(now, 'request', self.pk, self.locator, 0))
                    # F.flush()
                    cl.payment_paid(request, self.locator)
                else:
                    # F.write("{} -     > NOTIFY PAID -> FUNCTION func({},{},{},{},{})\n".format(now, 'request', 'paid', self.pk, self.locator, 0))
                    # F.flush()
                    func(request, 'paid', self.locator, 0)
            except Exception as e:
                # try:
                #     F.write("{} -     > EXCEPTION -> {}\n".format(now, e))
                # except Exception:
                #     F.write("{} -     > EXCEPTION -> ???\n".format(now))
                try:
                    if getattr(cl, "payment_exception", None):
                        # F.write("{} -     > NOTIFY EXCEPTION -> CLASS payment_exception({},{},{},{})\n".format(now, 'request', self.pk, self.locator, e))
                        # F.flush()
                        cl.payment_exception(request, self.locator, e)
                    else:
                        # F.write("{} -     > NOTIFY EXCEPTION -> FUNCTION func({},{},{},{},{})\n".format(now, 'request', 'exception', self.pk, self.locator, e))
                        # F.flush()
                        func(request, 'exception', self.locator, e)
                except Exception:
                    pass


class PaymentConfirmation(CodenerixModel):
    '''
    Store payment confirmations from users
    '''
    payment = models.ForeignKey(PaymentRequest, blank=False, null=False, related_name='paymentconfirmations', on_delete=models.CASCADE)
    ref = models.CharField(_('Reference'), max_length=50, blank=False, null=True, default=None)
    action = models.CharField(_('Action'), max_length=7, choices=PAYMENT_CONFIRMATION_CHOICES, blank=False, null=False)
    data = models.TextField(_('Data'), blank=True, null=True)
    error = models.BooleanField(_('Error'), blank=False, null=False, default=False)
    error_txt = models.TextField(_('Error Text'), blank=True, null=True)

    def __unicode__(self):
        return u"PayConf:{0}-{1}".format(self.payment, self.ref)

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(('payment__locator', _('Locator'), 100))
        fields.append(('payment__order', _('Order Reference'), 100))
        fields.append(('created', _('Created'), 100))
        fields.append(('action', _('Action'), 100))
        fields.append(('payment__total', _('Total'), 100))
        fields.append(('payment__currency', _('Currency'), 100))
        fields.append(('error', _('Error'), 100))
        fields.append(('payment__ref', _('Request Ref'), 100))
        fields.append(('ref', _('Ref'), 100))
        return fields

    def confirm(self, pr, data):
        # Set requested action
        self.action = 'confirm'
        # Launch as a general action
        return self.__action(pr, data)

    def cancel(self, pr, data):
        # Set requested action
        self.action = 'cancel'
        # Launch as a general action
        return self.__action(pr, data)

    def __action(self, pr, data):

        # Autofill class
        self.payment = pr
        self.data = json.dumps(data)
        self.save()

        # Check payment status
        error = None
        if not pr.cancelled:

            # Paypal must check if the payment can be confirmed or not (checking if there is a PaymentAnswer)
            if pr.protocol == 'paypal':
                pa = pr.paymentanswers.filter(ref__isnull=False, error=False)
                if pa.count():
                    error = (7, _("Payment already processed"))
                    self.error = True
                    self.error_txt = json.dumps({'error': error[0], 'errortxt': str(error[1])})
                    self.save()
                    raise PaymentError(*error)

            # Get config
            meta = settings.PAYMENTS.get('meta', {})
            config = settings.PAYMENTS.get(pr.platform, {})

            # Check that PaymentRequest and our actual enviroment is the same
            if pr.real == meta.get('real', False):

                # Get reference
                if pr.protocol == 'paypal':
                    error = self.__action_paypal(config, pr, data, error)
                elif pr.protocol == 'redsys' or pr.protocol == 'redsysxml':
                    error = self.__action_redsys(config, pr, data, error)
                else:
                    error = (1, _("Unknown protocol '{protocol}'").format(protocol=self.protocol))
            else:
                if meta.get('real', False):
                    envsys = 'REAL'
                else:
                    envsys = 'TEST'
                if pr.real:
                    envself = 'REAL'
                else:
                    envself = 'TEST'
                error = (2, _("Wrong environment: this transaction is for '{selfenviron}' environment and system is set to '{sysenviron}'").format(selfenviron=envself, sysenviron=envsys))
        else:
            error = (4, _("Payment has been cancelled/declined, access denied!"))

        # If there was some error, save and launch it!
        if error:
            self.error = True
            self.error_txt = json.dumps({'error': error[0], 'errortxt': str(error[1])})
            self.save()
            raise PaymentError(*error)

    def __action_paypal(self, config, pr, data, error):
        # Set arguments
        payment_id = None
        payer_id = None
        # Get arguments from data if we are confirming a payment
        if self.action == 'confirm':
            for key in data:
                value = data[key]
                if key == 'paymentId':
                    payment_id = value
                elif key == 'PayerID':
                    payer_id = value

        # Check we have all information we need
        if payment_id and payer_id:
            # Select environment
            if pr.real:
                environment = "live"
            else:
                environment = "sandbox"

            # Configure
            paypalrestsdk.configure({
                "mode": environment,
                "client_id": config.get('id', None),
                "client_secret": config.get('secret', None),
            })

            # Locate the payment
            payment = paypalrestsdk.Payment.find(payment_id)

            # Check payment result
            if payment:
                state = payment.to_dict()['state']
                if state == 'created':
                    # Get info about transaction
                    info = payment.to_dict()['transactions'][0]['amount']
                    # Get info about the payer
                    payerinf = payment.to_dict()['payer']
                    # Verify all
                    if float(info['total']) != float(pr.total):
                        error = (3, _("Total does not match: our={our} paypal={paypal}").format(our=float(pr.total), paypal=float(info['total'])))
                    elif info['currency'].upper() != pr.currency.iso4217.upper():
                        error = (3, _("Currency does not math: our={our} paypal={paypal}").format(our=pr.currency.iso4217.upper(), paypal=info['currency'].upper()))
                    elif payerinf['status'] != 'VERIFIED':
                        error = (3, _("Payer hasn't been VERIFIED yet, it is {payer}").format(payer=payerinf['status']))
                    elif payerinf['payer_info']['payer_id'] != payer_id:
                        error = (3, _("Wrong Payer ID: our={our} paypal={paypal}").format(our=payer_id, paypal=payerinf['payer_info']['payer_id']))
                    else:
                        # Everything is fine, payer verified and payment authorized
                        self.ref = payer_id
                        self.save()

                        # Execute payment
                        pa = PaymentAnswer()
                        pa.request = self.data
                        pa.request_date = timezone.now()
                        pa.payment = pr
                        pa.save(feedback=payment)
                else:
                    error = (4, _("Payment is not ready for confirmation, status is '{status}' and it should be 'created'").format(status=state))

            else:
                error = (5, _("Payment not found!"))

        else:

            if self.action == 'cancel':
                # Cancel payment
                pr.cancelled = True
                pr.save()
                # Remember payment confirmation for future reference
                self.save()
            else:
                missing = []
                if not payment_id:
                    missing.append(_("Missing paymentId"))
                if not payer_id:
                    missing.append(_("Missing PayerId"))
                error = (6, _("Missing information in data: {missing}").format(missing=", ".join(missing)))

        # Return error
        return error

    def __action_redsys(self, config, pr, data, error):

        if self.action == 'confirm':
            # Check if there is at least one remote confirmation for this payment
            pa = self.payment.paymentanswers.filter(error=False, ref__isnull=False).first()
            if not pa:
                error = (4, _("Payment is not executed, we didn't get yet the confirmation from REDSYS"))
            elif self.payment.paymentconfirmations.filter(ref__isnull=False).count():
                error = (10, _("Payment is already confirmed"))
            else:
                # Everything is fine, payer verified and payment authorized
                self.ref = pa.ref
                self.save()
        elif self.action == 'cancel':
            # Cancel payment
            pr.cancelled = True
            pr.save()
            # Remember payment confirmation for future reference
            self.save()
        else:
            # Wrong action (this service is valid only for confirm and cancel)
            error = (6, _("Wrong action: {action}").format(action=self.action))

        # We won't get confirmation data from Redsys, not anymore!
        # else:
        #
        #    # Get authkey
        #    authkey = base64.b64decode(config.get('auth_key', ''))
        #
        #    # Set arguments
        #    signature = None
        #    signature_version = None
        #    params = None
        #    paramsb64 = None
        #
        #    # Get arguments from data if we are confirming a payment
        #    if self.action == 'confirm':
        #        for key in data:
        #            value = data[key]
        #            if key == 'Ds_SignatureVersion':
        #                signature_version = value
        #            elif key == 'Ds_MerchantParameters':
        #                paramsb64 = value
        #                try:
        #                    params = json.loads(base64.b64decode(paramsb64).decode())
        #                except Exception:
        #                    params = None
        #            elif key == 'Ds_Signature':
        #                signature = value.replace("/", "_").replace("+", "-")
        #
        #    # Check we have all information we need
        #    if signature and signature_version and paramsb64 and params:
        #
        #        # Check version
        #        if signature_version == 'HMAC_SHA256_V1':
        #
        #            # Build internal signature
        #            signature_internal = redsys_signature(authkey, params.get('Ds_Order', ''), paramsb64, recode=True)
        #
        #            # Verify signature
        #            if signature == signature_internal:
        #
        #                # In this point we have a confirmation request from the user with data in it, example:
        #                # {"Ds_Date":"18%2F08%2F2016","Ds_Hour":"11%3A20","Ds_SecurePayment":"1","Ds_Amount":"1200","Ds_Currency":"978","Ds_Order":"00000070","Ds_MerchantCode":"999008881","Ds_Terminal":"001","Ds_Response":"0000","Ds_TransactionType":"0","Ds_MerchantData":"","Ds_AuthorisationCode":"841950","Ds_Card_Number":"454881******0004","Ds_ConsumerLanguage":"1","Ds_Card_Country":"724"}
        #
        #                # Get info
        #                amount = params.get('Ds_Amount', None)
        #                authorisation = params.get('Ds_AuthorisationCode', None)
        #
        #                # Check if payment is ready for fonfirmation
        #                if amount and authorisation:
        #
        #                    if float(amount) / 100 == self.payment.total:
        #
        #                        # Check if there is at least one remote confirmation for this payment
        #                        if not self.payment.paymentanswers.filter(error=False).count():
        #                            error = (4, "Payment is not ready for executing, the system didn't get yet the confirmation from REDSYS")
        #                        elif self.payment.paymentconfirmations.filter(ref__isnull=False).count():
        #                            error = (10, "Payment is already confirmed")
        #                        else:
        #                            # Everything is fine, payer verified and payment authorized
        #                            self.ref = authorisation
        #                            self.save()
        #                    else:
        #                        error = (3, "Amount doesn't match to the payment request: our={} - remote={}".format(self.payment.total, float(amount) / 100))
        #                else:
        #                    if not amount:
        #                        error = (3, "Missing amount in your confirmation request")
        #                    elif not authorisation:
        #                        error = (3, "Missing authorisation code in your confirmation request")
        #                    else:
        #                        error = (3, "Missing info in your confirmation request")
        #            else:
        #                error = (9, "Invalid signature: our={} - remote={}".format(signature_internal, signature))
        #        else:
        #            error = (9, "Invalid signature version")
        #
        #    else:
        #
        #        if self.action == 'cancel':
        #            # Cancel payment
        #            pr.cancelled = True
        #            pr.save()
        #            # Remember payment confirmation for future reference
        #            self.save()
        #        else:
        #            missing = []
        #            if not params:
        #                missing.append("Ds_MerchantParameters has wrong encoding")  # No Base64
        #            if not paramsb64:
        #                missing.append("Missing Ds_MerchantParameters")
        #            if not signature:
        #                missing.append("Missing Ds_Signature")
        #            if not signature_version:
        #                missing.append("Missing Ds_SignatureVersion")
        #            error = (6, "Missing information in data: {}".format(", ".join(missing)))

        # Return error
        return error


class PaymentAnswer(CodenerixModel):
    '''
    Store payment answers from the remote protocol
    '''
    payment = models.ForeignKey(PaymentRequest, blank=False, null=False, related_name='paymentanswers', on_delete=models.CASCADE)
    ref = models.CharField(_('Reference'), max_length=50, blank=False, null=True, default=None)
    error = models.BooleanField(_('Error'), blank=False, null=False, default=False)
    error_txt = models.TextField(_('Error Text'), blank=True, null=True)

    request = models.TextField(_('Request'), blank=True, null=True)
    answer = models.TextField(_('Answer'), blank=True, null=True)
    request_date = models.DateTimeField(_("Request date"), editable=False, blank=True, null=True)
    answer_date = models.DateTimeField(_("Answer date"), editable=False, blank=True, null=True)

    def __unicode__(self):
        if self.error:
            error = 'KO'
        else:
            error = 'OK'
        return u"PayAns:{0}-{1}::{2}".format(self.payment, self.ref, error)

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(('payment__locator', _('Locator'), 100))
        fields.append(('payment__order', _('Order Reference'), 100))
        fields.append(('request_date', _('Request date'), 100))
        fields.append(('answer_date', _('Answer date'), 100))
        fields.append(('payment__total', _('Total'), 100))
        fields.append(('payment__currency', _('Currency'), 100))
        fields.append(('error', _('Error'), 100))
        fields.append(('payment__ref', _('Request Ref'), 100))
        fields.append(('ref', _('Ref'), 100))
        return fields

    def save(self, feedback=None):

        # Get pr for quicker access to PaymentRequest
        pr = self.payment

        if not pr.cancelled:

            # Check environment
            if pr.real == settings.PAYMENTS.get('meta', {}).get('real', False):

                # Get reference
                if pr.protocol == 'paypal':

                    # Get last confirmation
                    pc = pr.paymentconfirmations.filter(ref__isnull=False).order_by("-created")[0]

                    # Try to nofify paypal automatically about this payment
                    payment_id = pr.ref
                    payer_id = pc.ref

                    # Select environment
                    if pr.real:
                        environment = "live"
                    else:
                        environment = "sandbox"

                    # Configure
                    paypalrestsdk.configure({
                        "mode": environment,
                        "client_id": settings.PAYMENTS.get(pr.platform, {}).get('id', None),
                        "client_secret": settings.PAYMENTS.get(pr.platform, {}).get('secret', None),
                    })

                    # Locate the payment
                    if feedback:
                        payment = feedback
                    else:
                        payment = paypalrestsdk.Payment.find(payment_id)

                    # Check payment result
                    if payment:
                        state = payment.to_dict()['state']
                        if state == 'created':
                            # Get info about transaction
                            info = payment.to_dict()['transactions'][0]['amount']
                            # Get info about the payer
                            payerinf = payment.to_dict()['payer']
                            # Verify all
                            if float(info['total']) != float(pr.total):
                                raise PaymentError(3, _("Total does not match: our={our} paypal={paypal}").format(our=float(pr.total), paypal=float(info['total'])))
                            elif info['currency'].upper() != pr.currency.iso4217.upper():
                                raise PaymentError(3, _("Currency does not math: our={our} paypal={paypal}").format(our=pr.currency.iso4217.upper(), paypal=info['currency'].upper()))
                            elif payerinf['status'] != 'VERIFIED':
                                raise PaymentError(3, _("Payer hasn't been VERIFIED yet, it is {payer}").format(payer=payerinf['status']))
                            elif payerinf['payer_info']['payer_id'] != payer_id:
                                raise PaymentError(3, _("Wrong Payer ID: our={our} paypal={paypal}").format(our=payer_id, paypal=payerinf['payer_info']['payer_id']))
                            else:
                                # Everything is fine, payer verified and payment authorized
                                request = {'payer_id': payer_id}
                                # Save request
                                self.request = json.dumps(request)
                                self.request_date = timezone.now()
                                # Execute payment
                                answer = payment.execute(request)
                                self.answer_date = timezone.now()
                                if answer:
                                    self.answer = json.dumps(answer)
                                else:
                                    self.error = True
                                    self.error_txt = json.dumps(payment.error)
                        else:
                            raise PaymentError(4, _("Payment is not ready for executing, status is '{status}' and it should be 'created'").format(status=state))
                    else:
                        raise PaymentError(5, _("Payment not found!"))

                elif self.payment.protocol in ['redsys', 'redsysxml']:
                    # Protocols which do not need any work to get done during save() process
                    pass
                else:
                    raise PaymentError(1, _("Unknown protocol '{protocol}'").format(protocol=pr.protocol))

            else:
                if settings.PAYMENTS.get('meta', {}).get('real', False):
                    envsys = 'REAL'
                else:
                    envsys = 'TEST'
                if pr.real:
                    envself = 'REAL'
                else:
                    envself = 'TEST'
                raise PaymentError(2, _("Wrong environment: this transaction is for '{selfenviron}' environment and system is set to '{sysenviron}'".format(selfenviron=envself, sysenviron=envsys)))
        else:
            raise PaymentError(4, _("Payment has been cancelled/declined, access denied!"))

        # Save data
        return super(PaymentAnswer, self).save()

    def success(self, pr, data):
        # Got a success payment
        pr.cancelled = False
        pr.save()

        # Check payment status
        pa = pr.paymentanswers.filter(ref__isnull=False, error=False)
        if not pa.count():

            # Autofill class
            self.payment = pr
            self.error = True
            self.error_txt = json.dumps("INIT")
            self.request = json.dumps(data)
            self.request_date = timezone.now()
            self.save()

            # Prepare defatuls answer
            answer = {'result': 'KO'}

            # Check for errors
            error = None
            if not data:
                error = (6, _('Request is empty'))
            elif pr.protocol not in ['redsys', 'redsysxml']:
                error = (1, _("Unknown protocol '{protocol}'").format(protocol=self.protocol))
            else:

                for key in data:
                    value = data[key]
                    if key == 'Ds_SignatureVersion':
                        signature_version = value
                    elif key == 'Ds_MerchantParameters':
                        paramsb64 = value
                        try:
                            params = json.loads(base64.b64decode(paramsb64).decode())
                        except Exception:
                            params = None
                    elif key == 'Ds_Signature':
                        signature = value

                # Check we have all information we need
                if signature and signature_version and paramsb64 and params:

                    # Get authkey
                    authkey = base64.b64decode(settings.PAYMENTS.get(self.payment.platform, {}).get('auth_key', ''))

                    # Check version
                    if signature_version == 'HMAC_SHA256_V1':

                        # Build signature
                        signature_internal = redsys_signature(authkey, params.get('Ds_Order', ''), paramsb64, recode=True)

                        # Verify signature
                        if signature == signature_internal:

                            # In this point we have a confirmation request from the redsys with data in it, example:
                            # {"Ds_Date":"23\/08\/2016","Ds_Hour":"17:52","Ds_SecurePayment":"1","Ds_Card_Number":"454881******0004","Ds_Card_Country":"724","Ds_Amount":"1200","Ds_Currency":"978","Ds_Order":"00000015","Ds_MerchantCode":"999008881","Ds_Terminal":"001","Ds_Response":"0000","Ds_MerchantData":"","Ds_TransactionType":"0","Ds_ConsumerLanguage":"1","Ds_AuthorisationCode":"629178"}

                            # Get info
                            amount = params.get('Ds_Amount', None)
                            authorisation = params.get('Ds_AuthorisationCode', None).strip()

                            # Check if payment is ready for fonfirmation
                            if amount and authorisation:

                                if float(amount) / 100 == self.payment.total:

                                    # Everything is fine, payer verified and payment authorized
                                    self.ref = authorisation
                                    self.error = False
                                    self.error_txt = None
                                    self.save()

                                    # Everything whent fine
                                    answer['result'] = 'OK'
                                else:
                                    error = (3, _("Amount doesn't match to the payment request: our={our} - remote={remote}").format(our=self.payment.total, remote=float(amount) / 100))

                            else:
                                # Find the error if any
                                if not amount:
                                    error = (3, _("Missing amount in your confirmation request"))
                                elif not authorisation:
                                    # Error code
                                    errorcode = params.get('Ds_ErrorCode', None)
                                    if errorcode:
                                        self.ref = errorcode
                                        answer['errorcode'] = errorcode
                                        error = (4, redsys_error(errorcode))
                                    else:
                                        error = (3, _("Missing authorisation code in your confirmation request"))
                                else:
                                    error = (3, _("Missing info in your confirmation request"))

                        else:
                            error = (9, _("Invalid signature version: our={our} - remote={remote}").format(our=signature_internal, remote=signature))

                    else:
                        error = (9, _("Invalid signature version"))
                else:
                    missing = []
                    if not params:
                        missing.append(_("Ds_MerchantParameters has wrong encoding"))  # No Base64
                    if not paramsb64:
                        missing.append(_("Missing Ds_MerchantParameters"))
                    if not signature:
                        missing.append(_("Missing Ds_Signature"))
                    if not signature_version:
                        missing.append(_("Missing Ds_SignatureVersion"))
                    error = (6, _("Missing information in data: {missing}").format(missing=", ".join(missing)))

            # If there are errors
            if error:

                # Prepare to save errors
                self.error = True
                self.error_txt = json.dumps({'error': error[0], 'errortxt': str(error[1])})

                # Set errors in the answer
                answer['error'] = error[0]
                answer['errortxt'] = str(error[1])

            else:

                # No error happened
                self.error = False
                self.error_txt = None

            # Set the answer
            self.answer = json.dumps(answer)
            self.answer_date = timezone.now()

            # Save result and return an answer
            self.save()
            return answer

        else:
            raise PaymentError(7, _("Payment already processed"))


class PaymentError(Exception):
    '''
    ERROR CODES
    1:  Unknown protocol (is it a new protocol?)
    2:  Wrong environment (environment from the payment and the system do not match)
    3:  Information in the transaction does not match (information not verified)
    4:  Payment not approved, decline or cancelled by user
    5:  Payment not found
    6:  Missing information on the request
    7:  Payment already processed
    8:  Unknown platform (did you change your configuration?)
    9:  Information in the transaction is not authorized (signature not valid)
    10: Payment already confirmed
    11: Wrong information on the request
    '''
    pass
