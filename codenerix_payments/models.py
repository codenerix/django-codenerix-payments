#
# django-codenerix-payments
#
# Codenerix GNU
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

# type: ignore

import base64
import datetime
import hashlib
import json
import logging
import math
import sys
import tempfile
import time
import traceback
from decimal import Decimal, InvalidOperation

import paypalrestsdk  # type: ignore
import requests
from codenerix.helpers import (  # type: ignore
    CodenerixEncoder,
    JSONEncoder_newdefault,
    get_client_ip,
)
from codenerix.middleware import get_current_user  # type: ignore
from codenerix.models import CodenerixModel  # type: ignore
from Crypto.PublicKey import RSA  # nosec B413
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.urls import resolve, reverse
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.translation import gettext_lazy as _
from yop_python_sdk.client.yop_client_config import YopClientConfig

# from .sdk_yeepay.sign_rsa.authorization import sign_rsa  # get_query_str,
# from .sdk_yeepay.sign_rsa.yop_security_utils import (  # type: ignore
#     verify_rsa,
#     decrypt,
# )
from yop_python_sdk.client.yopclient import YopClient
from yop_python_sdk.security.encryptor.rsaencryptor import RsaEncryptor

# from suds.client import Client as SOAPClient


# Set new JSON Encoder default
JSONEncoder_newdefault()

CURRENCY_MAX_DIGITS = getattr(
    settings,
    "CDNX_INVOICING_CURRENCY_MAX_DIGITS",
    10,
)
CURRENCY_DECIMAL_PLACES = getattr(
    settings,
    "CDNX_INVOICING_CURRENCY_DECIMAL_PLACES",
    4,
)

PAYMENT_PROTOCOL_CHOICES = (
    ("paypal", _("Paypal")),
    ("redsys", _("Redsys")),
    ("redsysxml", _("Redsys XML")),
    ("yeepay", _("Yeepay")),
)

PAYMENT_CONFIRMATION_CHOICES = (
    ("confirm", _("Confirm")),
    ("cancel", _("Cancel")),
)

REDSYS_LANG_MAP = {
    "es": "001",
    "en": "002",
    "ca": "003",
    "fr": "004",
    "de": "005",
    "nl": "006",
    "it": "007",
    "sv": "008",
    "pt": "009",
    "pl": "011",
    "gl": "012",
    "eu": "013",
    "da": "208",
}

logger = logging.getLogger(__name__)


def redsys_signature(authkey, order, paramsb64, recode=False):
    # Build the signature using Triple DES (CBC mode)
    iv = b"\0" * 8

    # Pad the order to a multiple of 8
    pad_len = 8 - (len(order) % 8)
    padded_order = (order + ("\0" * pad_len)).encode()

    # Encrypt with 3DES (probably this is far deprecated)
    cipher = Cipher(algorithms.TripleDES(authkey), modes.CBC(iv))  # nosec B304
    encryptor = cipher.encryptor()
    claveop = encryptor.update(padded_order) + encryptor.finalize()

    # HMAC-SHA256
    h = hmac.HMAC(claveop, hashes.SHA256())
    h.update(paramsb64.encode())
    dig = h.finalize()

    # Base64 encode the signature
    signature = base64.b64encode(dig).decode()

    if recode:
        signature = signature.replace("+", "-").replace("/", "_")

    return signature


def redsys_error(code):
    errors = {}
    errors["0101"] = "Tarjeta Caducada."
    errors["0102"] = (
        "Tarjeta en excepción transitoria o bajo sospecha de fraude."
    )
    errors["0104"] = "Operación no permitida para esa tarjeta o terminal."
    errors["0106"] = "Intentos de PIN excedidos."
    errors["0116"] = "Disponible Insuficiente."
    errors["0118"] = "Tarjeta no Registrada."
    errors["0125"] = "Tarjeta no efectiva."
    errors["0129"] = "Código de seguridad (CVV2/CVC2) incorrecto."
    errors["0180"] = "Tarjeta ajena al servicio."
    errors["0184"] = "Error en la autenticación del titular."
    errors["0190"] = "Denegación sin especificar motivo."
    errors["0191"] = "Fecha de caducidad errónea."
    errors["0202"] = (
        "Tarjeta en excepción transitoria o bajo sospecha de fraude "
        "con retirada de tarjeta."
    )
    errors["0904"] = "Comercio no registrado en FUC."
    errors["0909"] = "Error de sistema."
    errors["0912"] = "Emisor no disponible."
    errors["0913"] = "Pedido repetido."
    errors["0944"] = "Sesión Incorrecta."
    errors["0950"] = "Operación de devolución no permitida."
    errors["9064"] = "Número de posiciones de la tarjeta incorrecto."
    errors["9078"] = "No existe método de pago válido para esa tarjeta."
    errors["9093"] = "Tarjeta no existente."
    errors["9094"] = "Rechazo servidores internacionales."
    errors["9104"] = (
        "Comercio con “titular seguro” y titular sin clave de compra segura."
    )
    errors["9218"] = (
        "El comercio no permite op. seguras por entrada /operaciones."
    )
    errors["9253"] = "Tarjeta no cumple el check-digit."
    errors["9256"] = "El comercio no puede realizar preautorizaciones."
    errors["9257"] = "Esta tarjeta no permite operativa de preautorizaciones."
    errors["9261"] = (
        "Operación detenida por superar el control de "
        "restricciones en la entrada al SIS."
    )
    errors["9912"] = "Emisor no disponible."
    errors["9913"] = (
        "Error en la confirmación que el comercio envía al TPV Virtual "
        "(solo aplicable en la opción de sincronización SOAP)."
    )
    errors["9914"] = (
        "Confirmación “KO” del comercio (solo aplicable en la opción de "
        "sincronización SOAP)."
    )
    errors["9915"] = "A petición del usuario se ha cancelado el pago."
    errors["9928"] = (
        "Anulación de autorización en diferido realizada por "
        "el SIS (proceso batch)."
    )
    errors["9929"] = (
        "Anulación de autorización en diferido realizada por el comercio."
    )
    errors["9997"] = (
        "Se está procesando otra transacción en SIS con la misma tarjeta."
    )
    errors["9998"] = "Operación en proceso de solicitud de datos de tarjeta."
    errors["9999"] = "Operación que ha sido redirigida al emisor a autenticar."
    errors["SIS0007"] = "Error al desmontar el XML de entrada."
    errors["SIS0008"] = "Error falta Ds_Merchant_MerchantCode."
    errors["SIS0009"] = "Error de formato en Ds_Merchant_MerchantCode."
    errors["SIS0010"] = "Error falta Ds_Merchant_Terminal."
    errors["SIS0011"] = "Error de formato en Ds_Merchant_Terminal."
    errors["SIS0014"] = "Error de formato en Ds_Merchant_Order."
    errors["SIS0015"] = "Error falta Ds_Merchant_Currency."
    errors["SIS0016"] = "Error de formato en Ds_Merchant_Currency."
    errors["SIS0017"] = "Error no se admiten operaciones en pesetas."
    errors["SIS0018"] = "Error falta Ds_Merchant_Amount."
    errors["SIS0019"] = "Error de formato en Ds_Merchant_Amount."
    errors["SIS0020"] = "Error falta Ds_Merchant_MerchantSignature."
    errors["SIS0021"] = "Error la Ds_Merchant_MerchantSignature viene vacía."
    errors["SIS0022"] = "Error de formato en Ds_Merchant_TransactionType."
    errors["SIS0023"] = "Error Ds_Merchant_TransactionType desconocido."
    errors["SIS0024"] = (
        "Error Ds_Merchant_ConsumerLanguage tiene mas de 3 posiciones."
    )
    errors["SIS0025"] = "Error de formato en Ds_Merchant_ConsumerLanguage."
    errors["SIS0026"] = "Error No existe el comercio / terminal enviado."
    errors["SIS0027"] = (
        "Error Moneda enviada por el comercio es diferente a la que "
        "tiene asignada para ese terminal."
    )
    errors["SIS0028"] = "Error Comercio / terminal está dado de baja."
    errors["SIS0030"] = (
        "Error en un pago con tarjeta ha llegado un tipo de "
        "operación no valido."
    )
    errors["SIS0031"] = "Método de pago no definido."
    errors["SIS0033"] = (
        "Error en un pago con móvil ha llegado un tipo de operación que no es "
        "ni pago ni preautorización."
    )
    errors["SIS0034"] = "Error de acceso a la Base de Datos."
    errors["SIS0037"] = "El número de teléfono no es válido."
    errors["SIS0038"] = "Error en java."
    errors["SIS0040"] = (
        "Error el comercio / terminal no tiene ningún método de pago asignado."
    )
    errors["SIS0041"] = (
        "Error en el cálculo de la firma de datos del comercio."
    )
    errors["SIS0042"] = "La firma enviada no es correcta."
    errors["SIS0043"] = "Error al realizar la notificación on-line."
    errors["SIS0046"] = "El BIN de la tarjeta no está dado de alta."
    errors["SIS0051"] = "Error número de pedido repetido."
    errors["SIS0054"] = (
        "Error no existe operación sobre la que realizar la devolución."
    )
    errors["SIS0055"] = (
        "Error no existe más de un pago con el mismo número de pedido."
    )
    errors["SIS0056"] = (
        "La operación sobre la que se desea devolver no está autorizada."
    )
    errors["SIS0057"] = "El importe a devolver supera el permitido."
    errors["SIS0058"] = (
        "Inconsistencia de datos, en la validación de una confirmación."
    )
    errors["SIS0059"] = (
        "Error no existe operación sobre la que realizar la devolución."
    )
    errors["SIS0060"] = (
        "Ya existe una confirmación asociada a la preautorización."
    )
    errors["SIS0061"] = (
        "La preautorización sobre la que se desea confirmar no está "
        "autorizada."
    )
    errors["SIS0062"] = "El importe a confirmar supera el permitido."
    errors["SIS0063"] = "Error. Número de tarjeta no disponible."
    errors["SIS0064"] = (
        "Error. El número de tarjeta no puede tener más de 19 posiciones."
    )
    errors["SIS0065"] = "Error. El número de tarjeta no es numérico."
    errors["SIS0066"] = "Error. Mes de caducidad no disponible."
    errors["SIS0067"] = "Error. El mes de la caducidad no es numérico."
    errors["SIS0068"] = "Error. El mes de la caducidad no es válido."
    errors["SIS0069"] = "Error. Año de caducidad no disponible."
    errors["SIS0070"] = "Error. El Año de la caducidad no es numérico."
    errors["SIS0071"] = "Tarjeta caducada."
    errors["SIS0072"] = "Operación no anulable."
    errors["SIS0074"] = "Error falta Ds_Merchant_Order."
    errors["SIS0075"] = (
        "Error el Ds_Merchant_Order tiene menos de 4 posiciones o más de 12."
    )
    errors["SIS0076"] = (
        "Error el Ds_Merchant_Order no tiene las cuatro primeras posiciones "
        "numéricas."
    )
    errors["SIS0078"] = "Método de pago no disponible."
    errors["SIS0079"] = "Error al realizar el pago con tarjeta."
    errors["SIS0081"] = (
        "La sesión es nueva, se han perdido los datos almacenados."
    )
    errors["SIS0084"] = "El valor de Ds_Merchant_Conciliation es nulo."
    errors["SIS0085"] = "El valor de Ds_Merchant_Conciliation no es numérico."
    errors["SIS0086"] = (
        "El valor de Ds_Merchant_Conciliation no ocupa 6 posiciones."
    )
    errors["SIS0089"] = (
        "El valor de Ds_Merchant_ExpiryDate no ocupa 4 posiciones."
    )
    errors["SIS0092"] = "El valor de Ds_Merchant_ExpiryDate es nulo."
    errors["SIS0093"] = "Tarjeta no encontrada en la tabla de rangos."
    errors["SIS0094"] = "La tarjeta no fue autenticada como 3D Secure."
    errors["SIS0097"] = "Valor del campo Ds_Merchant_CComercio no válido."
    errors["SIS0098"] = "Valor del campo Ds_Merchant_CVentana no válido."
    errors["SIS0112"] = (
        "Error. El tipo de transacción especificado "
        "en Ds_Merchant_Transaction_Type no esta permitido."
    )
    errors["SIS0113"] = "Excepción producida en el servlet de operaciones."
    errors["SIS0114"] = "Error, se ha llamado con un GET en lugar de un POST."
    errors["SIS0115"] = (
        "Error no existe operación sobre la que realizar el pago de la cuota."
    )
    errors["SIS0116"] = (
        "La operación sobre la que se desea pagar una cuota no es "
        "una operación válida."
    )
    errors["SIS0117"] = (
        "La operación sobre la que se desea pagar una "
        "cuota no está autorizada."
    )
    errors["SIS0118"] = "Se ha excedido el importe total de las cuotas."
    errors["SIS0119"] = "Valor del campo Ds_Merchant_DateFrecuency no válido."
    errors["SIS0120"] = (
        "Valor del campo Ds_Merchant_CargeExpiryDate no válido."
    )
    errors["SIS0121"] = "Valor del campo Ds_Merchant_SumTotal no válido."
    errors["SIS0122"] = (
        "Valor del campo Ds_merchant_DateFrecuency o "
        "Ds_Merchant_SumTotal tiene formato incorrecto."
    )
    errors["SIS0123"] = (
        "Se ha excedido la fecha tope para realizar transacciones."
    )
    errors["SIS0124"] = (
        "No ha transcurrido la frecuencia mínima en un pago "
        "recurrente sucesivo."
    )
    errors["SIS0132"] = (
        "La fecha de Confirmación de Autorización no puede superar en "
        "más de 7 días a la de Preautorización."
    )
    errors["SIS0133"] = (
        "La fecha de Confirmación de Autenticación no puede superar en "
        "mas de 45 días a la de Autenticación Previa."
    )
    errors["SIS0139"] = "Error el pago recurrente inicial está duplicado."
    errors["SIS0142"] = "Tiempo excedido para el pago."
    errors["SIS0197"] = (
        "Error al obtener los datos de cesta de la compra en operación "
        "tipo pasarela."
    )
    errors["SIS0198"] = (
        "Error el importe supera el límite permitido para el comercio."
    )
    errors["SIS0199"] = (
        "Error el número de operaciones supera el límite permitido para "
        "el comercio."
    )
    errors["SIS0200"] = (
        "Error el importe acumulado supera el límite permitido para "
        "el comercio."
    )
    errors["SIS0214"] = "El comercio no admite devoluciones."
    errors["SIS0216"] = "Error Ds_Merchant_CVV2 tiene mas de 3/4 posiciones."
    errors["SIS0217"] = "Error de formato en Ds_Merchant_CVV2."
    errors["SIS0218"] = (
        "El comercio no permite operaciones seguras por "
        "la entrada /operaciones."
    )
    errors["SIS0219"] = (
        "Error el número de operaciones de la tarjeta supera el límite "
        "permitido para el comercio."
    )
    errors["SIS0220"] = (
        "Error el importe acumulado de la tarjeta supera el límite "
        "permitido para el comercio."
    )
    errors["SIS0221"] = "Error el CVV2 es obligatorio."
    errors["SIS0222"] = (
        "Ya existe una anulación asociada a la preautorización."
    )
    errors["SIS0223"] = (
        "La preautorización que se desea anular no está autorizada."
    )
    errors["SIS0224"] = (
        "El comercio no permite anulaciones por no tener firma ampliada."
    )
    errors["SIS0225"] = (
        "Error no existe operación sobre la que realizar la anulación."
    )
    errors["SIS0226"] = (
        "Inconsistencia de datos, en la validación de una anulación."
    )
    errors["SIS0227"] = "Valor del campo Ds_Merchan_TransactionDate no válido."
    errors["SIS0229"] = "No existe el código de pago aplazado solicitado."
    errors["SIS0252"] = "El comercio no permite el envío de tarjeta."
    errors["SIS0253"] = "La tarjeta no cumple el check-digit."
    errors["SIS0254"] = (
        "El número de operaciones de la IP supera el límite permitido "
        "por el comercio."
    )
    errors["SIS0255"] = (
        "El importe acumulado por la IP supera el límite permitido "
        "por el comercio."
    )
    errors["SIS0256"] = "El comercio no puede realizar preautorizaciones."
    errors["SIS0257"] = (
        "Esta tarjeta no permite operativa de preautorizaciones."
    )
    errors["SIS0258"] = (
        "Inconsistencia de datos, en la validación de una confirmación."
    )
    errors["SIS0261"] = (
        "Operación detenida por superar el control de restricciones "
        "en la entrada al SIS."
    )
    errors["SIS0270"] = (
        "El comercio no puede realizar autorizaciones en diferido."
    )
    errors["SIS0274"] = (
        "Tipo de operación desconocida o no permitida por esta entrada al SIS."
    )
    errors["SIS0298"] = (
        "El comercio no permite realizar operaciones de Tarjeta en Archivo."
    )
    errors["SIS0319"] = (
        "El comercio no pertenece al grupo especificado en Ds_Merchant_Group."
    )
    errors["SIS0321"] = (
        "La referencia indicada en Ds_Merchant_Identifier no está "
        "asociada al comercio."
    )
    errors["SIS0322"] = "Error de formato en Ds_Merchant_Group."
    errors["SIS0325"] = (
        "Se ha pedido no mostrar pantallas pero no se ha enviado "
        "ninguna referencia de tarjeta."
    )
    errors["SIS0334"] = (
        "Superado los límites de compra con esta tarjeta o IP (ver "
        "parámetros en Redsys). [Velocity checks]"
    )
    errors["SIS0429"] = (
        "Error en la versión enviada por el comercio en el parámetro "
        "Ds_SignatureVersion"
    )
    errors["SIS0430"] = (
        "Error al decodificar el parámetro Ds_MerchantParameters"
    )
    errors["SIS0431"] = (
        "Error del objeto JSON que se envía codificado en el parámetro "
        "Ds_MerchantParameters"
    )
    errors["SIS0432"] = "Error FUC del comercio erróneo"
    errors["SIS0433"] = "Error Terminal del comercio erróneo"
    errors["SIS0434"] = (
        "Error ausencia de número de pedido en la operación "
        "enviada por el comercio"
    )
    errors["SIS0435"] = "Error en el cálculo de la firma"
    code2 = "SIS{}".format(code)
    code3 = code.replace("SIS", "")
    if code in errors:
        return errors[code]
    elif code2 in errors:
        return errors[code2]
    elif code3 in errors:
        return errors[code3]
    else:
        return _("UNKNOWN CODE {code}").format(code=code)


def yeepay_client(config):
    # Prepare Yeepay virtual config
    app_key = config.get("app_key", None)
    endpoint = config.get("endpoint", None)
    public_key = config.get("public_key", None)
    private_key = config.get("private_key", None)
    yconfig = {
        "app_key": app_key,
        "server_root": endpoint,
        "yop_public_key": [{"value": public_key}],
        "http_client": {},
        "isv_private_key": [{"value": private_key}],
    }

    # Prepare Yeepay client with virtual configuration
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        temp_file.write(json.dumps(yconfig).encode())
        temp_file.seek(0)
        client = YopClient(YopClientConfig(temp_file.name))

    # Return Yeepay client
    return client


def yeepay_error(code):
    errors = {}
    errors["1120"] = "超过失败次数限制"
    errors["1123"] = "该卡已过期"
    errors["1117"] = "未找到可用通道，请换卡重试"
    errors["1116"] = "您的账号需要在银行签约，请重新发起交易"
    errors["0001"] = "交易失败，请稍后重试"
    errors["9001"] = "请求重复,请稍候重试"
    errors["1077"] = "绑卡需要加验和验证码"
    errors["1078"] = "未查到对应卡信息"
    errors["1098"] = "系统异常，请联系易宝支付"
    errors["1080"] = "交易失败，请稍后重试"
    errors["1081"] = "商户尚未开通此银行业务"
    errors["1082"] = "银行系统维护中，请稍后重试"
    errors["1083"] = "发卡行不允许此卡交易，请联系发卡行"
    errors["1084"] = (
        "请拨打建行95533客服电话，接通后按#058核实交易，核实成功后可重新进行支付"
    )
    errors["1085"] = (
        "请拨打建行95533客服电话，接通后按#058进行交易核实，核实成功后方能重新进行支付交易"
    )
    errors["1086"] = "卡片有效期错误，请核对后重试"
    errors["1087"] = "银行预留手机号变更，绑卡关系无效"
    errors["1088"] = "该卡未开通电子支付功能或卡信息有误"
    errors["1089"] = "短信验证码发送失败"
    errors["1090"] = "该笔交易金额低于银行规定最低限额，请换卡支付"
    errors["1091"] = "缺少必要的银行卡信息"
    errors["1092"] = "超过银行交易金额限制"
    errors["1093"] = "交易金额超限"
    errors["1094"] = "可用余额不足"
    errors["1095"] = "发卡行不允许此卡交易"
    errors["1096"] = "银行系统异常，请稍后重试"
    errors["1097"] = "无效卡号，请核对后重新输入"
    errors["1099"] = "卡信息输入错误次数超限，请联系发卡行解锁"
    errors["1100"] = "密码有误，请确认后重新提交交易"
    errors["1101"] = "持卡人证件信息有误，请确认后重新提交交易"
    errors["1102"] = "银行卡开户姓名有误，请确认后重新提交交易"
    errors["1103"] = "卡信息有误，请核对后重试"
    errors["1104"] = "银行系统异常，请稍后重试"
    errors["1105"] = "重复交易，请稍后重试"
    errors["1106"] = "该卡不在该银行无卡支付业务范围内，请持卡人联系发卡行"
    errors["1107"] = "银行预留手机号有误，请确认后重新提交交易"
    errors["1001"] = "原交易订单不存在"
    errors["1002"] = "订单已存在"
    errors["1003"] = "创建订单异常"
    errors["1004"] = "交易订单状态错误"
    errors["1005"] = "交易订单已超时取消"
    errors["1006"] = "订单支付信息不存在"
    errors["1007"] = "订单支付状态异常"
    errors["1008"] = "订单金额错误"
    errors["1009"] = "订单入账状态异常"
    errors["1010"] = "订单未入账"
    errors["1011"] = "订单入账记录已经存在"
    errors["1020"] = "商户未开通产品"
    errors["1021"] = "订单状态未同步"
    errors["1022"] = "银行卡无对应卡bin"
    errors["1023"] = "不支持的卡种"
    errors["1024"] = "计费模版不存在"
    errors["1025"] = "由易宝下发短验"
    errors["1026"] = "由商户下发短验"
    errors["1027"] = "由银行下发短验"
    errors["1028"] = "支付处理中"
    errors["1029"] = "原始请求数据为空"
    errors["1030"] = "验证处理中"
    errors["1031"] = "恢复原始请求数据异常"
    errors["1032"] = "验证码发送次数超限"
    errors["1033"] = "验证码验证错误"
    errors["1034"] = "验证码超过重试次数"
    errors["1035"] = "验证码已失效"
    errors["1038"] = "订单类型错误"
    errors["1039"] = "查询清算结果为空"
    errors["1040"] = "分账金额大于等于订单金额"
    errors["1041"] = "分账订单号请求重复"
    errors["1042"] = "子分账方数量超限"
    errors["1043"] = "收款方入账订单状态异常"
    errors["1044"] = "未配置商户计费信息"
    errors["1045"] = "未配置商户场景"
    errors["1046"] = "未配置商户银行验证要素"
    errors["1047"] = "缺少必填要素"
    errors["1048"] = "短验发送失败"
    errors["1049"] = "订单已支付成功"
    errors["1050"] = "支付信息已存在"
    errors["1051"] = "验证码验证方式错误"
    errors["1052"] = "未查询到绑卡记录"
    errors["1053"] = "绑卡ID超时"
    errors["1054"] = "绑卡需要加验"
    errors["1055"] = "绑卡已经成功"
    errors["1056"] = "绑卡失败请发起新的请求"
    errors["1057"] = "绑卡验证中"
    errors["1058"] = "订单已终态请以查询结果为准"
    errors["1059"] = "传入绑卡ID不存在"
    errors["1060"] = "收款方异步通知地址为空"
    errors["1067"] = "付款方未开通会员支付"
    errors["1068"] = "预授权请求处理中"
    errors["1069"] = "预授权完成金额大于发起金额"
    errors["1070"] = "订单已经预授权完成"
    errors["1071"] = "订单已经预授权取消"
    errors["1072"] = "订单已经预授权发起成功"
    errors["1073"] = "订单未支付"
    errors["1079"] = "订单未支付成功"
    errors["1108"] = "黑名单阻断"
    errors["1109"] = "交易限额，超过商户单笔交易限额"
    errors["1110"] = "交易限额，超过商户日累计交易限额"
    errors["1111"] = "交易限额，超过商户月累计交易限额"
    errors["1112"] = "交易限额，超过商户日累计交易次数"
    errors["1113"] = "交易限额，超过商户月累计交易次数"
    errors["1115"] = "交易拦截--规则系统，超过交易限次"
    if code in errors:
        return errors[code]
    else:
        return _("未知的错误代码 {code}").format(code=code)


class Currency(CodenerixModel):
    """
    Currencies
    """

    name = models.CharField(
        _("Name"),
        max_length=15,
        blank=False,
        null=False,
        unique=True,
    )
    symbol = models.CharField(
        _("Symbol"),
        max_length=2,
        blank=False,
        null=False,
        unique=True,
    )
    iso4217 = models.CharField(
        _("ISO 4217 Code"),
        max_length=3,
        blank=False,
        null=False,
        unique=True,
    )
    price = models.DecimalField(
        _("Price"),
        blank=False,
        null=False,
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_DECIMAL_PLACES,
    )

    def __unicode__(self):
        return "{} ({})".format(smart_str(self.name), smart_str(self.symbol))

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(("name", _("Name"), 100))
        fields.append(("iso4217", _("ISO4217"), 100))
        fields.append(("price", _("Price"), 100))
        fields.append(("symbol", _("Symbol"), 100))
        return fields

    def rate(self, buy):
        # Prepare the call
        url = "http://api.fixer.io/latest"
        payload = {"base": self.iso4217, "symbols": buy.iso4217}
        r = requests.get(url, params=payload)
        if not r.raise_for_status():
            # Read the answer
            data = r.json()
            rate = data["rates"][buy.iso4217]
        return rate


class PaymentRequest(CodenerixModel):
    """
    ref: used to store the reference on the remote system (bank, paypal, google checkout, adyen,...), it is separated for quicker location
    reverse: used to store the reverse URL for this request when we get back an user from a remote system
    platform: selected platform for payment to happen (it is linked to request/answer)
    protocol: selected protocol for payment to happen (it is linked to request/answer)
    request/answer: usable structure for the selected payment system
    """  # noqa: E501

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    locator = models.CharField(
        _("Locator"),
        max_length=64,
        unique=True,
        blank=False,
        null=False,
    )
    ref = models.CharField(
        _("Reference"),
        max_length=50,
        blank=False,
        null=True,
        default=None,
    )
    order = models.PositiveIntegerField(
        _("Order Number"),
        blank=False,
        null=False,
        validators=[MaxValueValidator(78364164096)],
    )
    # 78364164096 => codenerix::hex36 = 7 char
    # validators=[MaxValueValidator(2821109907455)],
    order_ref = models.CharField(
        _("Order Reference"),
        max_length=8,
        blank=False,
        null=False,
    )
    reverse = models.CharField(
        _("Reverse"),
        max_length=64,
        blank=False,
        null=False,
        default="autorender",
    )
    currency = models.ForeignKey(
        Currency,
        blank=False,
        null=False,
        related_name="payments",
        on_delete=models.CASCADE,
    )
    platform = models.CharField(
        _("Platform"),
        max_length=20,
        blank=False,
        null=False,
    )
    protocol = models.CharField(
        _("Protocol"),
        choices=PAYMENT_PROTOCOL_CHOICES,
        max_length=10,
        blank=False,
        null=False,
    )
    real = models.BooleanField(
        _("Real"),
        blank=False,
        null=False,
        default=False,
    )
    error = models.BooleanField(
        _("Error"),
        blank=False,
        null=False,
        default=False,
    )
    error_txt = models.TextField(_("Error Text"), blank=True, null=True)
    cancelled = models.BooleanField(
        _("Cancelled"),
        blank=False,
        null=False,
        default=False,
    )
    total = models.DecimalField(
        _("Total"),
        blank=False,
        null=False,
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_DECIMAL_PLACES,
    )
    notes = models.CharField(
        _("Notes"),
        max_length=30,
        blank=True,
        null=True,
    )  # Observaciones

    request = models.TextField(_("Request"), blank=True, null=True)
    answer = models.TextField(_("Answer"), blank=True, null=True)
    request_date = models.DateTimeField(
        _("Request date"),
        editable=False,
        blank=True,
        null=True,
    )
    answer_date = models.DateTimeField(
        _("Answer date"),
        editable=False,
        blank=True,
        null=True,
    )
    ip = models.GenericIPAddressField(
        _("IP"),
        blank=False,
        null=False,
        editable=False,
    )
    feedback = models.JSONField(_("Feedback"), blank=True, null=True)

    def __unicode__(self):
        return "PayReq({}):{}_{}:{}|{}:{}[{}]".format(
            self.pk,
            self.locator,
            self.platform,
            self.protocol,
            self.ref,
            self.total,
            self.order,
        )

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        if info.request.user.is_superuser:
            fields.append(("user", _("User"), 100))
        fields.append(("is_paid", _("Is paid?"), 100))
        fields.append(("locator", _("Locator"), 100))
        fields.append(("feedback", _("Feedback"), 100))
        fields.append(("order", _("Number"), 100))
        fields.append(("order_ref", _("Reference"), 100))
        fields.append(("request_date", _("Request"), 100))
        fields.append(("answer_date", _("Answer"), 100))
        fields.append(("platform", _("Platform"), 100))
        fields.append(("protocol", _("Protocol"), 100))
        fields.append(("total", _("Total"), 100))
        fields.append(("currency", _("Currency"), 100))
        fields.append(("cancelled", _("Cancelled"), 100))
        fields.append(("error", _("Error"), 100))
        fields.append(("notes", _("Notes"), 100))
        fields.append(("ip", _("IP"), 100))
        if getattr(settings, "CDNX_PAYMENTS_REQUEST_PAY", False):
            fields.append(("get_approval_list", _("Paid"), 100))
        return fields

    def __searchF__(self, info):  # noqa: N802
        def currencies():
            curs = []
            for currency in Currency.objects.all():
                curs.append((currency.pk, currency.name))
            return curs

        def kindpaidfilter(kindfilter):
            if kindfilter == "Y":
                return Q(
                    cancelled=False,
                    paymentanswers__ref__isnull=False,
                    paymentanswers__error=False,
                )
            elif kindfilter == "N":
                return Q(
                    Q(paymentanswers__ref__isnull=True)
                    | Q(paymentanswers__error=True),
                    cancelled=False,
                )
            elif kindfilter == "C":
                return Q(cancelled=True)
            else:
                logger.error(
                    f"PR: Unknown kindpaidfilter '{kindfilter}' for "
                    f"payment request {self.locator}.",
                )
                raise OSError("Kind of paid filter not programmed!")

        tf = {}
        if info.request.user.is_superuser:
            tf["user"] = (
                _("Username"),
                lambda x: Q(user__username__icontains=x),
                "input",
            )
        tf["is_paid"] = (
            _("Is paid?"),
            lambda x: Q(paymentanswers__isnull=not x),
            [(True, _("Yes")), (False, _("No"))],
        )
        tf["order"] = (
            _("Order Number"),
            lambda x: Q(order__icontains=x),
            "input",
        )
        tf["order_ref"] = (
            _("Order Reference"),
            lambda x: Q(order_ref__icontains=x),
            "input",
        )
        tf["total"] = (_("Total"), lambda x: Q(total__icontains=x), "input")
        tf["currency"] = (
            _("Currency"),
            lambda x: Q(currency__pk=x),
            currencies(),
        )
        tf["ip"] = (_("IP"), lambda x: Q(ip__icontains=x), "input")
        if getattr(settings, "CDNX_PAYMENTS_REQUEST_PAY", False):
            tf["get_approval_list"] = (
                _("Approval"),
                kindpaidfilter,
                [("Y", _("Yes")), ("N", _("No")), ("C", _("Cancelled"))],
            )
        return tf

    def __limitQ__(self, info):  # noqa: N802
        limit = {}
        # If user is not a superuser, the shown records depends on the profile
        if not info.request.user.is_superuser:
            limit["user"] = Q(user=info.request.user)

        return limit

    def is_paid(self):
        return bool(
            self.paymentanswers.filter(ref__isnull=False, error=False).first(),
        )

    def get_approval_list(self):
        try:
            apr = self.get_approval()
        except PaymentError as e:
            apr = {"error": str(e)}
            logger.error(
                "PR: Error getting approval for "
                f"payment request {self.locator}: {e}",
            )
        return apr

    def get_approval(self):
        # If the transaction wasn't cancelled
        if not self.cancelled and self.answer:
            # Get approval link
            config = settings.PAYMENTS.get(self.platform, {})
            meta = settings.PAYMENTS.get("meta", {})
            if config and meta:
                if self.protocol == "paypal":
                    approval = self.__get_approval_paypal(meta, config)
                elif self.protocol == "redsys" or self.protocol == "redsysxml":
                    approval = self.__get_approval_redsys(meta, config)
                elif self.protocol == "yeepay":
                    approval = self.__get_approval_yeepay(meta, config)
                else:
                    logger.error(
                        "PR01: Unknown protocol '{protocol}' for "
                        f"payment request {self.locator}.".format(
                            protocol=self.protocol,
                        ),
                    )
                    raise PaymentError(
                        1,
                        _("Unknown protocol '{protocol}'").format(
                            protocol=self.protocol,
                        ),
                    )
            else:
                logger.error(
                    "PR02: Unknown platform '{platform}' for "
                    f"payment request {self.locator}.".format(
                        platform=self.platform,
                    ),
                )
                raise PaymentError(
                    2,
                    _("Unknown platform '{platform}'").format(
                        platform=self.platform,
                    ),
                )
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
        links = answer["links"]
        for link in links:
            # Look for approval URL
            if link["rel"] == "approval_url":
                approval["url"] = link["href"]
                break
        return approval

    def __get_approval_redsys(self, meta, config):
        # Initialize
        approval = {}

        # Get dict
        params = {}

        # AMOUNT: 12 Numeric - Last 2 positions are decimals except for YENS
        amount = int(math.ceil(float(self.total) * 100))
        params["DS_MERCHANT_AMOUNT"] = str(amount)

        # Coherence check for total amount to charge
        if float(amount) / 100 != self.total:
            logger.error(
                "PR11: Amount doesn't match to the payment request: "
                f"stored={self.total} - protocol={float(amount) / 100} "
                f"for payment request {self.locator}.",
            )
            raise PaymentError(
                11,
                _(
                    "Amount doesn't match to the payment request: stored={stored} - protocol={protocol}",  # noqa: E501
                ).format(stored=self.total, protocol=float(amount) / 100),
            )

        # CURRENCY: 4 Numeric
        curcode = self.currency.iso4217
        if curcode == "EUR":
            curcode = "978"
        elif curcode == "USD":
            curcode = "840"
        elif curcode == "GBP":
            curcode = "826"
        elif curcode == "JPY":
            curcode = "392"
        elif curcode == "CHF":
            curcode = "756"
        elif curcode == "CAD":
            curcode = "124"
        else:
            logger.error(
                "PR01: Unknown currency for this protocol '{currency}' "
                f"(available are: EUR, USD, GBP, JPY, CHF & CAD) "
                f"for payment request {self.locator}.".format(
                    currency=curcode,
                ),
            )
            raise PaymentError(
                1,
                _(
                    "Unknown currency for this protocol '{currency}' "
                    "(available are: EUR, USD, GBP, JPY, CHF & CAD)",
                ).format(currency=curcode),
            )
        params["DS_MERCHANT_CURRENCY"] = curcode

        # GET DETAILS
        # name = meta.get('name','')
        url = meta.get("url", "")  # URL when not using SSL

        # Prepare configuration
        code = config.get("merchant_code", "")
        authkey = base64.b64decode(config.get("auth_key", ""))
        success_url = url + reverse(
            "payment_url",
            kwargs={"action": "success", "locator": self.locator},
        )

        # Get reverse
        if self.reverse and self.reverse[:7] in ["http://", "https:/"]:
            return_url = self.reverse
            return_url.replace("{action}", "confirm")
            return_url.replace("{locator}", self.locator)
            cancel_url = self.reverse
            cancel_url.replace("{action}", "cancel")
            cancel_url.replace("{locator}", self.locator)
        else:
            return_url = url + reverse(
                "payment_url",
                kwargs={"action": "confirm", "locator": self.locator},
            )
            cancel_url = url + reverse(
                "payment_url",
                kwargs={"action": "cancel", "locator": self.locator},
            )

        # DETAILS 1
        params["DS_MERCHANT_ORDER"] = self.order_ref

        # TITULAR: Max 60 Alfa Numeric
        # #fields['Ds_Merchant_Titular'] = 'TIT'

        # PRODUCT DESCRIPTION: Max 125 Alfa Numeric
        # #fields['Ds_Merchant_ProductDescription'] = 'DES'

        params["DS_MERCHANT_MERCHANTCODE"] = code  # SELF CODE: 9 Numeric
        params["DS_MERCHANT_MERCHANTURL"] = (
            success_url  # SELF URL BACKEND: 250 Alfa Numeric
        )
        params["DS_MERCHANT_URLOK"] = (
            return_url  # SELF URL USER OK: 250 Alfa Numeric
        )
        params["DS_MERCHANT_URLKO"] = (
            cancel_url  # SELF URL USER KO: 250 Alfa Numeric
        )

        # SELF NAME: 25 Alfa Numeric
        # #fields['Ds_Merchant_MerchantName'] = name

        # LANGUAGE: 3 Numeric
        # lang_code = 0   # Client
        # #fields['Ds_Merchant_ConsumerLanguage'] = lang_code

        # DETAILS 2
        params["DS_MERCHANT_TERMINAL"] = (
            "1"  # TERMINAL: 3 Numeric (Fixed to 1)
        )

        # SELF INFO: 1024 Alfa Numeric
        # #fields['Ds_Merchant_MerchantData'] = 'INFO'

        params["DS_MERCHANT_TRANSACTIONTYPE"] = (
            "0"  # TRANSACTION TYPE: 1 Numeric (Fixed to 1 - Standard Payment)
        )

        # AUTH CODE: 6 Numeric (OPTIONAL)
        # fields['Ds_Merchant_AuthorisationCode'] = ''

        # IDENTIFIER: Max 40 Alfa Numeric
        # #fields['Ds_Merchant_Identifier'] = 'IDENT'

        # GROUP: Max 9 Numeric (OPTIONAL)
        # fields['Ds_Merchant_Group'] = ''

        # DIRECT PAYMENT: 'True' / 'false' (OPTIONAL)
        # fields['Ds_Merchant_DirectPayment'] = ''

        # METHOD: C:CARD / O:IUPAY (only for e-commerce with IUPAY support)
        # fields['Ds_Merchant_PayMethod'] = ''

        # Build the request
        paramsjson = json.dumps(params).encode()
        paramsb64 = base64.b64encode(paramsjson).decode()
        # try:
        #    paramsb64 = ''.join(unicode(base64.encodestring(paramsjson),
        #     'utf-8')).splitlines()
        # except NameError:
        #    paramsb64 = ''.join(base64.encodestring(paramsjson)).splitlines()

        # Build the signature
        signature = redsys_signature(
            authkey,
            params["DS_MERCHANT_ORDER"],
            paramsb64,
        )

        # Prepare the form
        form = {}
        form["Ds_SignatureVersion"] = "HMAC_SHA256_V1"
        form["Ds_MerchantParameters"] = paramsb64
        form["Ds_Signature"] = signature

        # xml =   '<DS_MERCHANT_AMOUNT>'+params['DS_MERCHANT_AMOUNT']+
        #               '</DS_MERCHANT_AMOUNT>'
        # xml+=   '<DS_MERCHANT_ORDER>'+params['DS_MERCHANT_ORDER']+
        #               '</DS_MERCHANT_ORDER>'
        # xml+=   '<DS_MERCHANT_MERCHANTCODE>'
        #               +params['DS_MERCHANT_MERCHANTCODE']+'</DS_MERCHANT_MERCHANTCODE>'
        # xml+=   '<DS_MERCHANT_CURRENCY>'+params['DS_MERCHANT_CURRENCY']+
        #           '</DS_MERCHANT_CURRENCY>'
        # xml+=   '<DS_MERCHANT_PAN>'+card['number']+'</DS_MERCHANT_PAN>'
        # xml+=   '<DS_MERCHANT_CVV2>'+card['ccv2']+'</DS_MERCHANT_CVV2>'
        # xml+=   '<DS_MERCHANT_TRANSACTIONTYPE>'+
        #               params['DS_MERCHANT_TRANSACTIONTYPE']+
        #               '</DS_MERCHANT_TRANSACTIONTYPE>'
        # xml+=   '<DS_MERCHANT_TERMINAL>'+params['DS_MERCHANT_TERMINAL']+
        #               '</DS_MERCHANT_TERMINAL>'
        # xml+=   '<DS_MERCHANT_EXPIRYDATE>'+card['expiry']['year']+
        #           card['expiry']['month']+'</DS_MERCHANT_EXPIRYDATE>'
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
        # finalxml+=    '<DS_SIGNATUREVERSION>HMAC_SHA256_V1'
        #                   '</DS_SIGNATUREVERSION>'
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
        approval["url"] = endpoint
        approval["form"] = form
        return approval

    def __get_approval_yeepay(self, meta, config):
        """
        https://open.yeepay.com/docs/apis/INDUSTRY_SOLUTION/GENERAL/bzshsfk/shouyintai/options__rest__v1.0__cashier__unified__order

        SUCESS:
        {
            'result': {
                'code': '00000',
                'message': 'ABC',
                'uniqueOrderNo': '123',
                'cashierUrl': 'https://cash.yeepay.com/cashier/uc?token=123&merchantNo=123'
            }
        }

        ERROR:
        {
            'result': {
                'code': '00201',
                'message': 'ABC'
            }
        }

        """  # noqa: E501

        # Initialize
        approval = {}
        # Get dict
        answer = json.loads(self.answer)
        # Get links inside the answer
        approval["url"] = answer.get("result", {}).get("cashierUrl", None)
        return approval

    def save(self, *args, **kwargs):
        # Check if we are a new object
        if self.pk:
            new = False
        else:
            new = True

            # Autoset user
            self.user = get_current_user()

            # Autoset locator
            info_decode = str(time.time()) + str(
                datetime.datetime.now().microsecond,
            )
            self.locator = hashlib.sha3_256(info_decode.encode()).hexdigest()

            # Autoset environment
            self.real = settings.PAYMENTS.get("meta", {}).get("real", False)
            # Autoset protocol
            self.protocol = None
            protocol = settings.PAYMENTS.get(self.platform, {}).get(
                "protocol",
                None,
            )
            for key, name in PAYMENT_PROTOCOL_CHOICES:
                if key == protocol:
                    self.protocol = key
            if self.protocol is None:
                logger.error(
                    "PR08: Unknown protocol '{protocol}' for "
                    f"payment request {self.locator}.".format(
                        protocol=protocol,
                    ),
                )
                raise PaymentError(
                    8,
                    _("Unknown platform '{platform}'").format(
                        platorm=self.platform,
                    ),
                )

        # Prepare CodenerixEncoder
        ce = CodenerixEncoder()

        # If no orther specified
        auto_set_order = not self.order
        if auto_set_order:
            # No order number yet
            self.order = 0
        else:
            # Encode order reference
            self.order_ref = ce.numeric_encode(
                self.order,
                dic="hex36",
                length=7,
                cfill="A",
            )

        # Save the model like always
        m = super().save(*args, **kwargs)

        # Autoset order
        if auto_set_order:
            # Set order number
            self.order = self.pk

            # Encode order reference
            self.order_ref = ce.numeric_encode(
                self.pk,
                dic="hex36",
                length=7,
                cfill="A",
            )

        # Execute specific actions for the payment system
        if new:
            if self.platform in settings.PAYMENTS:
                config = settings.PAYMENTS.get(self.platform, {})
                meta = settings.PAYMENTS.get("meta", {})
                if self.real == meta.get("real", False):
                    if self.protocol == "paypal":
                        self.__save_paypal(meta, config)
                    elif self.protocol in ["redsys", "redsysxml"]:
                        # Save request as we go since we don't have to do
                        # anything else
                        now = timezone.now()
                        self.request = "{}"
                        self.answer = "{}"
                        self.request_date = now
                        self.answer_date = now
                        self.save()
                    elif self.protocol == "yeepay":
                        self.__save_yeepay(meta, config)
                    else:
                        # Unknown protocol selected
                        logger.error(
                            "PR01: Unknown protocol '{protocol}' for "
                            f"payment request {self.locator}.".format(
                                protocol=self.protocol,
                            ),
                        )
                        raise PaymentError(
                            1,
                            _("Unknown protocol '{protocol}'").format(
                                protocol=self.protocol,
                            ),
                        )
                else:
                    # Request and configuration do not match
                    if meta.get("real", False):
                        envsys = "REAL"
                    else:
                        envsys = "TEST"
                    if self.real:
                        envself = "REAL"
                    else:
                        envself = "TEST"
                    logger.error(
                        "PR02: Wrong environment for payment request "
                        f"{self.locator}: this transaction is for "
                        f"'{envself}' environment and system is set to "
                        f"'{envsys}'",
                    )
                    raise PaymentError(
                        2,
                        _(
                            "Wrong environment: this transaction is "
                            "for '{selfenviron}' environment and system "
                            "is set to '{sysenviron}'",
                        ).format(selfenviron=envself, sysenviron=envsys),
                    )
            else:
                logger.error(
                    "PR08: Platform '{platform}' not configured "
                    f"for payment request {self.locator}.".format(
                        platform=self.platform,
                    ),
                )
                raise PaymentError(
                    8,
                    _(
                        "Platform '{platform}' not configured in your system",
                    ).format(platform=self.platform),
                )

        # Return the model we have created
        return m

    def __save_paypal(self, meta, config):
        # Select environment
        if self.real:
            environment = "live"
        else:
            environment = "sandbox"

        # Get details
        client_id = config.get("id", None)
        client_secret = config.get("secret", None)
        url = meta.get("url", "")

        # Get reverse
        if self.reverse and self.reverse[:7] in ["http://", "https:/"]:
            return_url = self.reverse
            return_url.replace("{action}", "confirm")
            return_url.replace("{locator}", self.locator)
            cancel_url = self.reverse
            cancel_url.replace("{action}", "cancel")
            cancel_url.replace("{locator}", self.locator)
        else:
            return_url = url + reverse(
                "payment_url",
                kwargs={"action": "confirm", "locator": self.locator},
            )
            cancel_url = url + reverse(
                "payment_url",
                kwargs={"action": "cancel", "locator": self.locator},
            )

        # Configure
        paypalrestsdk.configure(
            {
                "mode": environment,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

        # Request
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
                    "invoice_number": self.order_ref,
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
        try:
            result = payment.create()
        except paypalrestsdk.exceptions.UnauthorizedAccess as e:
            result = None
            payment.error = str(e)
            logger.error(
                "PR: Unauthorized access to Paypal API for "
                f"payment request {self.locator}: {e}",
            )

        # Check result
        if result:
            # Convert payment to dict
            answer = payment.to_dict()
            # Get Reference
            self.ref = answer["id"]
            # Build request
            self.answer = json.dumps(answer)

        else:
            # Get error and save
            self.error = True
            self.error_txt = json.dumps(payment.error)

        # Save everything
        self.answer_date = timezone.now()
        self.save()

    def __save_yeepay(self, meta, config):
        # Get details
        merchant_number = config.get("merchant_number", None)
        expire_minutes = config.get("expire_minutes", 120)
        url = meta.get("url", "")

        # Get Success URL
        success_url = url + reverse(
            "payment_url",
            kwargs={"action": "success", "locator": self.locator},
        )

        # Get reverse
        if self.reverse and self.reverse[:7] in ["http://", "https:/"]:
            return_url = self.reverse
            return_url.replace("{action}", "confirm")
            return_url.replace("{locator}", self.locator)
        else:
            return_url = url + reverse(
                "payment_url",
                kwargs={"action": "confirm", "locator": self.locator},
            )

        # Request
        expire = timezone.now() + datetime.timedelta(minutes=expire_minutes)
        request = {
            "parentMerchantNo": merchant_number,
            "merchantNo": merchant_number,
            "orderId": self.order_ref,
            "orderAmount": self.total,
            "goodsName": self.notes,
            "fundProcessType": "REAL_TIME",
            "notifyUrl": success_url,
            "expiredTime": expire.isoformat(),
            "returnUrl": return_url,
            "aggParam": '{"scene":{"WECHAT":"XIANXIA"}}',
        }

        # Save request
        self.request = json.dumps(request)
        self.request_date = timezone.now()
        self.save()

        # Create payment in Yeepay
        client = yeepay_client(config)
        try:
            answer = client.post(
                api="/rest/v1.0/cashier/unified/order",
                post_params=request,
            )
        except Exception as e:
            answer = None
            error = str(e)
            logger.error(
                "PR: Error creating Yeepay payment for "
                f"payment request {self.locator}: {error}",
            )

        # Check answer
        if answer:
            # Convert payment to dict
            result = answer.get("result", None)
            if result:
                code = result.get("code", None)
                if code == "00000" and "uniqueOrderNo" in result:
                    # Get Reference
                    self.ref = result["uniqueOrderNo"]
                    # Build request
                    self.answer = json.dumps(answer)
                else:
                    # Error code found or not uniqueOrderNo available
                    self.error = True
                    self.error_txt = json.dumps(answer)
            else:
                # No result found
                self.error = True
                self.error_txt = json.dumps(answer)

        else:
            # Get error and save
            self.error = True
            self.error_txt = json.dumps(error)

        # Save everything
        self.answer_date = timezone.now()
        self.save()

    def notify(self, request, answer=None):
        now = datetime.datetime.now()
        # with open("/tmp/codenerix_transaction.txt", "a") as F: # noqa: N806
        F = None  # noqa: N806
        if True:
            if F:
                F.write(f"\n\n{now} -     > NOTIFY FUNCTION\n")
            if self.reverse == "autorender":
                rev = "CNDX_payments_confirmation"
            else:
                rev = self.reverse

            # Resolve reverse
            try:
                resolved = resolve(
                    reverse(
                        rev,
                        kwargs={
                            "locator": 0,
                            "action": "success",
                            "error": 0,
                        },  # noqa: E501
                    ),
                )
            except NoReverseMatch as e:
                if F:
                    F.write(f"{now} -     > EXCEPTION -> {str(e)}\n")
                # Stop silently
                print(f"{now} -     > EXCEPTION -> {str(e)}\n")
                logger.error(
                    f"PR: Error resolving reverse URL '{rev}': {str(e)}",
                )
                return

            # Get function
            func = resolved.func

            # Detect if it is class based view
            if hasattr(func, "view_class"):
                cl = func.view_class
                func = None
            else:
                cl = None

            # Show details
            if F:
                F.write(f"{now} -     > DETAILS:\n")
                F.write(f"{now} -              cl:{cl}\n")
                F.write(f"{now} -            func:{func}\n")
                F.flush()

            # Decide what to do
            try:
                if F:
                    F.write(f"{now} -     > NOTIFY DECISION\n")
                    F.flush()

                # If we have a class based view
                if cl:
                    if hasattr(cl, "payment_paid"):
                        if F:
                            F.write(
                                f"{now} -     > NOTIFY PAID -> "
                                f'CLASS payment_paid("request",'
                                f"{self.locator},{answer})\n",
                            )
                            F.flush()
                        cl().payment_paid(request, self.locator, answer)
                    else:
                        print(f"payment_paid() not handled by {cl}")

                else:
                    # If we have a function
                    if F:
                        F.write(
                            f"{now} -     > NOTIFY PAID -> "
                            f'FUNCTION func("request","paid",'
                            f"{self.locator}, 0)\n",
                        )
                        F.flush()
                    func(request, "paid", self.locator, answer, 0)
            except Exception:
                if F:
                    # Get traceback
                    name = sys.exc_info()[0].__name__
                    err = sys.exc_info()[1]
                    trace = traceback.extract_tb(sys.exc_info()[2])
                    error = f"{name}: {err}"
                    for filename, linenumber, affected, source in trace:
                        error += (
                            f"\n  > Error in {affected} "
                            f"at {filename}:{linenumber} (source: {source})"
                        )

                    # Prepare error
                    try:
                        F.write(f"{now} -     > EXCEPTION -> {error}\n")
                    except Exception:
                        F.write(f"{now} -     > EXCEPTION -> ???\n")
                try:
                    # If we have a class based view
                    if cl:
                        if hasattr(cl, "payment_exception"):
                            if F:
                                F.write(
                                    f"{now} -     > NOTIFY EXCEPTION -> "
                                    f'CLASS payment_exception("request",'
                                    f"{self.locator},{error})\n",
                                )
                                F.flush()
                            cl().payment_exception(
                                request,
                                self.locator,
                                answer,
                                error,
                            )
                        else:
                            print(f"payment_exception() not handled by {cl}")
                            logger.error(
                                f"PR: payment_exception() not handled by {cl}",
                            )
                    else:
                        # If we have a function
                        if F:
                            F.write(
                                f"{now} -     > NOTIFY EXCEPTION -> "
                                f'FUNCTION func("request","exception",'
                                f"{self.locator},{answer},{error})\n",
                            )
                            F.flush()
                        func(
                            request,
                            "exception",
                            self.locator,
                            answer,
                            error,
                        )  # noqa: E501
                except Exception:
                    # Get traceback
                    name = sys.exc_info()[0].__name__
                    err = sys.exc_info()[1]
                    trace = traceback.extract_tb(sys.exc_info()[2])
                    error = f"{name}: {err}"
                    for filename, linenumber, affected, source in trace:
                        error += (
                            f"\n  > Error in {affected} "
                            f"at {filename}:{linenumber} "
                            f"(source: {source})"
                        )
                    if F:
                        # Prepare error
                        try:
                            F.write(f"{now} -     > EXCEPTION -> {error}\n")
                        except Exception:
                            F.write(f"{now} -     > EXCEPTION -> ???\n")
                    print(f"{now} -     > EXCEPTION -> {error}\n")
                    logger.error(f"PR: Error in notify function: {error}")


class PaymentConfirmation(CodenerixModel):
    """
    Store payment confirmations from users
    """

    payment = models.ForeignKey(
        PaymentRequest,
        blank=False,
        null=False,
        related_name="paymentconfirmations",
        on_delete=models.CASCADE,
    )
    ref = models.CharField(
        _("Reference"),
        max_length=50,
        blank=False,
        null=True,
        default=None,
    )
    action = models.CharField(
        _("Action"),
        max_length=7,
        choices=PAYMENT_CONFIRMATION_CHOICES,
        blank=False,
        null=False,
    )
    data = models.TextField(_("Data"), blank=True, null=True)
    error = models.BooleanField(
        _("Error"),
        blank=False,
        null=False,
        default=False,
    )
    error_txt = models.TextField(_("Error Text"), blank=True, null=True)
    ip = models.GenericIPAddressField(
        _("IP"),
        blank=False,
        null=False,
        editable=False,
    )

    def __unicode__(self):
        return "PayConf:{}-{}".format(self.payment, self.ref)

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(("payment__locator", _("Locator"), 100))
        fields.append(("payment__order", _("Order Number"), 100))
        fields.append(("payment__order_ref", _("Order Reference"), 100))
        fields.append(("created", _("Created"), 100))
        fields.append(("action", _("Action"), 100))
        fields.append(("payment__total", _("Total"), 100))
        fields.append(("payment__currency", _("Currency"), 100))
        fields.append(("error", _("Error"), 100))
        fields.append(("payment__ref", _("Request Ref"), 100))
        fields.append(("ref", _("Ref"), 100))
        fields.append(("ip", _("IP"), 100))
        return fields

    def __limitQ__(self, info):  # noqa: N802
        limit = {}
        # If user is not a superuser, the shown records depends on the profile
        if not info.request.user.is_superuser:
            limit["user"] = Q(payment__user=info.request.user)

        return limit

    def confirm(self, pr, data, request):
        # Set requested action
        self.action = "confirm"
        # Launch as a general action
        return self.__action(pr, data, request)

    def cancel(self, pr, data, request):
        # Set requested action
        self.action = "cancel"
        # Launch as a general action
        return self.__action(pr, data, request)

    def __action(self, pr, data, request):
        # Autofill class
        self.ip = get_client_ip(request)
        self.payment = pr
        self.data = json.dumps(data)
        self.save()

        # Check payment status
        error = None
        if not pr.cancelled:
            # Paypal must check if the payment can be confirmed or
            # not (checking if there is a PaymentAnswer)
            if pr.protocol == "paypal":
                pa = pr.paymentanswers.filter(ref__isnull=False, error=False)
                if pa.count():
                    error = (7, _("Payment already processed"))
                    self.error = True
                    self.error_txt = json.dumps(
                        {"error": error[0], "errortxt": str(error[1])},
                    )
                    self.save()
                    logger.error(
                        f"PC07: Payment {pr.locator} already processed, "
                        "action not allowed",
                    )
                    raise PaymentError(*error)

            # Get config
            meta = settings.PAYMENTS.get("meta", {})
            config = settings.PAYMENTS.get(pr.platform, {})

            # Check that PaymentRequest and our actual enviroment is the same
            if pr.real == meta.get("real", False):
                # Get reference
                if pr.protocol == "paypal":
                    error = self.__action_paypal(
                        config,
                        pr,
                        data,
                        error,
                        request,
                    )
                elif pr.protocol == "redsys" or pr.protocol == "redsysxml":
                    error = self.__action_redsys(
                        config,
                        pr,
                        data,
                        error,
                        request,
                    )
                elif pr.protocol == "yeepay":
                    error = self.__action_yeepay(
                        config,
                        pr,
                        data,
                        error,
                        request,
                    )
                else:
                    error = (
                        1,
                        _("Unknown protocol '{protocol}'").format(
                            protocol=pr.protocol,
                        ),
                    )
                    logger.error(
                        f"PC01: Unknown protocol '{pr.protocol}' "
                        f"for payment {pr.locator}",
                    )
            else:
                if meta.get("real", False):
                    envsys = "REAL"
                else:
                    envsys = "TEST"
                if pr.real:
                    envself = "REAL"
                else:
                    envself = "TEST"
                error = (
                    2,
                    _(
                        "Wrong environment: this transaction is "
                        "for '{selfenviron}' environment and system is "
                        "set to '{sysenviron}'",
                    ).format(selfenviron=envself, sysenviron=envsys),
                )
                logger.error(
                    f"PC02: Wrong environment for payment {pr.locator}: "
                    f"self={envself} - system={envsys}",
                )
        else:
            error = (
                4,
                _("Payment has been cancelled/declined, access denied!"),
            )
            logger.error(
                f"PC04: Payment {pr.locator} has been cancelled, "
                "action not allowed",
            )

        # If there was some error, save and launch it!
        if error:
            self.error = True
            self.error_txt = json.dumps(
                {"error": error[0], "errortxt": str(error[1])},
            )
            self.save()
            raise PaymentError(*error)

    def __action_paypal(self, config, pr, data, error, request):
        # Set arguments
        payment_id = None
        payer_id = None
        # Get arguments from data if we are confirming a payment
        if self.action == "confirm":
            for key in data:
                value = data[key]
                if key == "paymentId":
                    payment_id = value
                elif key == "PayerID":
                    payer_id = value

        # Check we have all information we need
        if payment_id and payer_id:
            # Select environment
            if pr.real:
                environment = "live"
            else:
                environment = "sandbox"

            # Configure
            paypalrestsdk.configure(
                {
                    "mode": environment,
                    "client_id": config.get("id", None),
                    "client_secret": config.get("secret", None),
                },
            )

            # Locate the payment
            payment = paypalrestsdk.Payment.find(payment_id)

            # Check payment result
            if payment:
                state = payment.to_dict()["state"]
                if state == "created":
                    # Get info about transaction
                    info = payment.to_dict()["transactions"][0]["amount"]
                    # Get info about the payer
                    payerinf = payment.to_dict()["payer"]
                    # Verify all
                    if float(info["total"]) != float(pr.total):
                        error = (
                            3,
                            _(
                                "Total does not match: our={our} "
                                "paypal={paypal}",
                            ).format(
                                our=float(pr.total),
                                paypal=float(info["total"]),
                            ),
                        )
                        logger.error(
                            f"PC03: Total does not match for payment "
                            f"{pr.locator}: our={pr.total} - "
                            f"paypal={info['total']}",
                        )
                    elif (
                        info["currency"].upper() != pr.currency.iso4217.upper()
                    ):
                        error = (
                            3,
                            _(
                                "Currency does not math: our={our} "
                                "paypal={paypal}",
                            ).format(
                                our=pr.currency.iso4217.upper(),
                                paypal=info["currency"].upper(),
                            ),
                        )
                        logger.error(
                            f"PC03: Currency does not match for payment "
                            f"{pr.locator}: our={pr.currency.iso4217.upper()} "
                            f"- paypal={info['currency'].upper()}",
                        )
                    elif payerinf["status"] != "VERIFIED":
                        error = (
                            3,
                            _(
                                "Payer hasn't been VERIFIED yet, "
                                "it is {payer}",
                            ).format(payer=payerinf["status"]),
                        )
                        logger.error(
                            "PC03: Payer not verified for "
                            f"payment {pr.locator}: "
                            f"{payerinf['status']}",
                        )

                    elif payerinf["payer_info"]["payer_id"] != payer_id:
                        error = (
                            3,
                            _(
                                "Wrong Payer ID: our={our} paypal={paypal}",
                            ).format(
                                our=payer_id,
                                paypal=payerinf["payer_info"]["payer_id"],
                            ),
                        )
                        logger.error(
                            f"PC03: Wrong Payer ID for payment {pr.locator}: "
                            f"our={payer_id} - "
                            f"paypal={payerinf['payer_info']['payer_id']}",
                        )
                    else:
                        # Everything is fine, payer verified and payment
                        # authorized
                        self.ref = payer_id
                        self.save()

                        # Execute payment
                        pa = PaymentAnswer()
                        pa.ip = get_client_ip(request)
                        pa.request = self.data
                        pa.request_date = timezone.now()
                        pa.payment = pr
                        pa.save(feedback=payment)
                else:
                    error = (
                        4,
                        _(
                            "Payment is not ready for confirmation, status "
                            "is '{status}' and it should be 'created'",
                        ).format(status=state),
                    )
                    logger.error(
                        f"PC04: Payment {pr.locator} is not ready for "
                        f"confirmation, status={state}",
                    )

            else:
                error = (5, _("Payment not found!"))
                logger.error(f"PC05: Payment {pr.locator} not found in Paypal")

        else:
            if self.action == "cancel":
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
                error = (
                    6,
                    _("Missing information in data: {missing}").format(
                        missing=", ".join(missing),
                    ),
                )
                logger.error(
                    f"PC06: Missing information for payment {pr.locator}: "
                    f"{', '.join(missing)}",
                )

        # Return error
        return error

    def __action_redsys(self, config, pr, data, error, request):
        if self.action == "confirm":
            # Check if there is at least one remote confirmation for
            # this payment
            pa = self.payment.paymentanswers.filter(
                error=False,
                ref__isnull=False,
            ).first()
            if not pa:
                error = (
                    4,
                    _(
                        "Payment is not executed, we didn't get yet the "
                        "confirmation from REDSYS",
                    ),
                )
                logger.error(
                    f"PC04: Payment {pr.locator} is not executed, "
                    "no confirmation from REDSYS",
                )
            elif self.payment.paymentconfirmations.filter(
                ref__isnull=False,
            ).count():
                error = (10, _("Payment is already confirmed"))
                logger.error(
                    f"PC10: Payment {pr.locator} is already confirmed",
                )
            else:
                # Everything is fine, payer verified and payment authorized
                self.ref = pa.ref
                self.save()
        elif self.action == "cancel":
            # Cancel payment
            pr.cancelled = True
            pr.save()
            # Remember payment confirmation for future reference
            self.save()
        else:
            # Wrong action (this service is valid only for confirm and cancel)
            error = (6, _("Wrong action: {action}").format(action=self.action))
            logger.error(
                f"PC06: Wrong action '{self.action}' for payment {pr.locator}",
            )

        # Return error
        return error

    def __action_yeepay(self, config, pr, data, error, request):
        # data_src es el valor de recibido en $_SERVER["QUERY_STRING"]
        data_src = request.META.get("QUERY_STRING", "")
        # signature_src es el valor recibido en $_REQUEST['signature']
        signature = data.get("sign", "").split("$")[0]

        if signature:
            # cogemos los datos hasta &signature=
            pos = data_src.index("&sign=")
            data = data_src[:pos]

            # Recover character for B64 and recover padding
            # signature = signature.replace("-", "+").replace(
            # "_", "/") + "=" * (
            #     -len(signature) % 4
            # )

            public_key = config.get("public_key", None)
            public_key_imported = RSA.import_key(
                "-----BEGIN PUBLIC KEY-----\n"
                + public_key
                + "\n-----END PUBLIC KEY-----",
            )
            encryptor = RsaEncryptor(public_key=public_key_imported)

            if encryptor.verify_signature(data, signature):
                if self.action == "confirm":
                    # Check if there is at least one remote confirmation for
                    # this payment
                    pa = self.payment.paymentanswers.filter(
                        error=False,
                        ref__isnull=False,
                    ).first()
                    if not pa:
                        error = (
                            4,
                            _(
                                "Payment is not executed, we didn't get yet "
                                "the confirmation from Yeepay",
                            ),
                        )
                        logger.error(
                            f"PC04: Payment {pr.locator} is not executed, "
                            "no confirmation from Yeepay",
                        )
                    elif self.payment.paymentconfirmations.filter(
                        ref__isnull=False,
                    ).count():
                        error = (10, _("Payment is already confirmed"))
                        logger.error(
                            f"PC10: Payment {pr.locator} is already confirmed",
                        )

                    else:
                        # Everything is fine, payer verified and payment
                        # authorized
                        self.ref = pa.ref
                        self.save()
                else:
                    # Wrong action (this service is valid only for confirm
                    # and cancel)
                    error = (
                        6,
                        _("Wrong action: {action}").format(action=self.action),
                    )
                    logger.error(
                        f"PC06: Wrong action '{self.action}' for payment "
                        f"{pr.locator}",
                    )

            else:
                error = (1, _("Invalid sign"))
                logger.error(f"PC01: Invalid sign for payment {pr.locator}")
        else:
            if self.action == "cancel":
                # Find unique order number
                try:
                    answer = json.loads(self.payment.answer)
                except Exception:
                    answer = None
                if answer:
                    unique_order_no = answer.get("result", {}).get(
                        "uniqueOrderNo",
                        None,
                    )
                else:
                    unique_order_no = None

                # Check if we have a unique order number
                if unique_order_no:
                    # Notify Yeepay
                    merchant_number = config.get("merchant_number", None)
                    request = {
                        "orderId": self.payment.order_ref,
                        "uniqueOrderNo": unique_order_no,
                        "parentMerchantNo": merchant_number,
                        "merchantNo": merchant_number,
                    }
                    client = yeepay_client(config)
                    try:
                        answer = client.post(
                            api="/rest/v1.0/trade/order/close",
                            post_params=request,
                        )
                    except Exception as e:
                        answer = None
                        error = str(e)
                        logger.error(
                            f"PC01: Yeepay cancel error for payment "
                            f"{pr.locator}: {error}",
                        )

                    # Analize answer
                    if answer:
                        code = answer.get("result", {}).get("code", None)
                        message = answer.get("result", {}).get("message", None)
                        if code != "OPR0000" or message != "成功":
                            error = (
                                1,
                                _(
                                    f"Yeepay cancel error: code={code} "
                                    f"message={message}",
                                ),
                            )
                            logger.error(
                                f"PC01: Yeepay cancel error for payment "
                                f"{pr.locator}: code={code} message={message}",
                            )

                # Cancel payment
                pr.cancelled = True
                pr.save()
                # Remember payment confirmation for future reference
                self.save()

            else:
                error = (1, _("Not signed"))
                logger.error(f"PC01: Not signed for payment {pr.locator}")

        return error


class PaymentAnswer(CodenerixModel):
    """
    Store payment answers from the remote protocol
    """

    payment = models.ForeignKey(
        PaymentRequest,
        blank=False,
        null=False,
        related_name="paymentanswers",
        on_delete=models.CASCADE,
    )
    ref = models.CharField(
        _("Reference"),
        max_length=50,
        blank=False,
        null=True,
        default=None,
    )
    error = models.BooleanField(
        _("Error"),
        blank=False,
        null=False,
        default=False,
    )
    error_txt = models.TextField(_("Error Text"), blank=True, null=True)

    request = models.TextField(_("Request"), blank=True, null=True)
    answer = models.TextField(_("Answer"), blank=True, null=True)
    request_date = models.DateTimeField(
        _("Request date"),
        editable=False,
        blank=True,
        null=True,
    )
    answer_date = models.DateTimeField(
        _("Answer date"),
        editable=False,
        blank=True,
        null=True,
    )
    ip = models.GenericIPAddressField(
        _("IP"),
        blank=False,
        null=False,
        editable=False,
    )

    def __unicode__(self):
        if self.error:
            error = "KO"
        else:
            error = "OK"
        return "PayAns:{}-{}::{}".format(self.payment, self.ref, error)

    def __str__(self):
        return self.__unicode__()

    def __fields__(self, info):
        fields = []
        fields.append(("payment__locator", _("Locator"), 100))
        fields.append(("payment__order", _("Order Number"), 100))
        fields.append(("payment__order_ref", _("Order Reference"), 100))
        fields.append(("request_date", _("Request date"), 100))
        fields.append(("answer_date", _("Answer date"), 100))
        fields.append(("payment__total", _("Total"), 100))
        fields.append(("payment__currency", _("Currency"), 100))
        fields.append(("error", _("Error"), 100))
        fields.append(("payment__ref", _("Request Ref"), 100))
        fields.append(("ref", _("Ref"), 100))
        fields.append(("ip", _("IP"), 100))
        return fields

    def __limitQ__(self, info):  # noqa: N802
        limit = {}
        # If user is not a superuser, the shown records depends on the profile
        if not info.request.user.is_superuser:
            limit["user"] = Q(payment__user=info.request.user)

        return limit

    def save(self, feedback=None):
        # Get pr for quicker access to PaymentRequest
        pr = self.payment

        if not pr.cancelled:
            # Check environment
            if pr.real == settings.PAYMENTS.get("meta", {}).get("real", False):
                # Get reference
                if pr.protocol == "paypal":
                    # Get last confirmation
                    pc = pr.paymentconfirmations.filter(
                        ref__isnull=False,
                    ).order_by("-created")[0]

                    # Try to nofify paypal automatically about this payment
                    payment_id = pr.ref
                    payer_id = pc.ref

                    # Select environment
                    if pr.real:
                        environment = "live"
                    else:
                        environment = "sandbox"

                    # Configure
                    paypalrestsdk.configure(
                        {
                            "mode": environment,
                            "client_id": settings.PAYMENTS.get(
                                pr.platform,
                                {},
                            ).get("id", None),
                            "client_secret": settings.PAYMENTS.get(
                                pr.platform,
                                {},
                            ).get("secret", None),
                        },
                    )

                    # Locate the payment
                    if feedback:
                        payment = feedback
                    else:
                        payment = paypalrestsdk.Payment.find(payment_id)

                    # Check payment result
                    if payment:
                        state = payment.to_dict()["state"]
                        if state == "created":
                            # Get info about transaction
                            info = payment.to_dict()["transactions"][0][
                                "amount"
                            ]
                            # Get info about the payer
                            payerinf = payment.to_dict()["payer"]
                            # Verify all
                            if float(info["total"]) != float(pr.total):
                                logger.error(
                                    f"PA03: Total does not match for payment "
                                    f"{pr.locator}: our={pr.total} - "
                                    f"paypal={info['total']}",
                                )
                                raise PaymentError(
                                    3,
                                    _(
                                        "Total does not match: our={our} "
                                        "paypal={paypal}",
                                    ).format(
                                        our=float(pr.total),
                                        paypal=float(info["total"]),
                                    ),
                                )
                            elif (
                                info["currency"].upper()
                                != pr.currency.iso4217.upper()
                            ):
                                logger.error(
                                    "PA03: Currency does not match "
                                    "for payment "
                                    f"{pr.locator}: "
                                    f"our={pr.currency.iso4217.upper()} "
                                    f"- paypal={info['currency'].upper()}",
                                )
                                raise PaymentError(
                                    3,
                                    _(
                                        "Currency does not math: our={our} "
                                        "paypal={paypal}",
                                    ).format(
                                        our=pr.currency.iso4217.upper(),
                                        paypal=info["currency"].upper(),
                                    ),
                                )
                            elif payerinf["status"] != "VERIFIED":
                                logger.error(
                                    f"PA03: Payer not verified for payment "
                                    f"{pr.locator}: {payerinf['status']}",
                                )
                                raise PaymentError(
                                    3,
                                    _(
                                        "Payer hasn't been VERIFIED yet, "
                                        "it is {payer}",
                                    ).format(payer=payerinf["status"]),
                                )
                            elif (
                                payerinf["payer_info"]["payer_id"] != payer_id
                            ):
                                logger.error(
                                    f"PA03: Wrong Payer ID for payment "
                                    f"{pr.locator}: our={payer_id} - "
                                    f"paypal={payerinf['payer_info']['payer_id']}",  # noqa: E501
                                )
                                raise PaymentError(
                                    3,
                                    _(
                                        "Wrong Payer ID: our={our} "
                                        "paypal={paypal}",
                                    ).format(
                                        our=payer_id,
                                        paypal=payerinf["payer_info"][
                                            "payer_id"
                                        ],
                                    ),
                                )
                            else:
                                # Everything is fine, payer verified and
                                # payment authorized
                                request = {"payer_id": payer_id}
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
                            logger.error(
                                f"PA04: Payment {pr.locator} is not ready "
                                f"for confirmation, status={state}",
                            )
                            raise PaymentError(
                                4,
                                _(
                                    "Payment is not ready for executing, "
                                    "status is '{status}' and it should "
                                    "be 'created'",
                                ).format(status=state),
                            )
                    else:
                        logger.error(
                            f"PA05: Payment {pr.locator} not found in Paypal",
                        )
                        raise PaymentError(5, _("Payment not found!"))

                elif self.payment.protocol in ["redsys", "redsysxml"]:
                    # Protocols which do not need any work to get done
                    # during save() process
                    pass
                elif self.payment.protocol == "yeepay":
                    pass
                else:
                    logger.error(
                        f"PA01: Unknown protocol '{self.payment.protocol}' "
                        f"for payment {pr.locator}",
                    )
                    raise PaymentError(
                        1,
                        _("Unknown protocol '{protocol}'").format(
                            protocol=pr.protocol,
                        ),
                    )

            else:
                if settings.PAYMENTS.get("meta", {}).get("real", False):
                    envsys = "REAL"
                else:
                    envsys = "TEST"
                if pr.real:
                    envself = "REAL"
                else:
                    envself = "TEST"
                logger.error(
                    f"PA02: Wrong environment for payment {pr.locator}: "
                    f"self={envself} - system={envsys}",
                )
                raise PaymentError(
                    2,
                    _(
                        "Wrong environment: this transaction is "
                        "for '{selfenviron}' environment and system "
                        "is set to '{sysenviron}'".format(
                            selfenviron=envself,
                            sysenviron=envsys,
                        ),
                    ),
                )
        else:
            logger.error(
                f"PC04: Payment {pr.locator} has been cancelled, "
                "access denied",
            )
            raise PaymentError(
                4,
                _("Payment has been cancelled/declined, access denied!"),
            )

        # Save data
        return super().save()

    def success(self, pr, data, request):
        # Got a success payment
        pr.cancelled = False
        pr.save()

        # Prepare defatuls answer
        answer = {"result": "KO"}

        # Check payment status
        pa = pr.paymentanswers.filter(ref__isnull=False, error=False)
        if not pa.count():
            # Autofill class
            self.ip = get_client_ip(request)
            self.payment = pr
            self.error = True
            self.error_txt = json.dumps("INIT")
            self.request = json.dumps(data)
            self.request_date = timezone.now()
            self.save()

            # Check for errors
            error = None
            if not data:
                error = (6, _("Request is empty"))
                logger.error(
                    f"PS06: Request is empty for payment {pr.locator}",
                )
            elif pr.protocol in ["redsys", "redsysxml"]:
                for key in data:
                    value = data[key]
                    if key == "Ds_SignatureVersion":
                        signature_version = value
                    elif key == "Ds_MerchantParameters":
                        paramsb64 = value
                        try:
                            params = json.loads(
                                base64.b64decode(paramsb64).decode(),
                            )
                        except Exception:
                            params = None
                    elif key == "Ds_Signature":
                        signature = value

                # Check we have all information we need
                if signature and signature_version and paramsb64 and params:
                    # Get authkey
                    authkey = base64.b64decode(
                        settings.PAYMENTS.get(self.payment.platform, {}).get(
                            "auth_key",
                            "",
                        ),
                    )

                    # Check version
                    if signature_version == "HMAC_SHA256_V1":
                        # Build signature
                        signature_internal = redsys_signature(
                            authkey,
                            params.get("Ds_Order", ""),
                            paramsb64,
                            recode=True,
                        )

                        # Verify signature
                        if signature == signature_internal:
                            # In this point we have a confirmation request
                            # from the redsys with data in it, example:
                            # {"Ds_Date":"23\/08\/2016","Ds_Hour":"17:52","Ds_SecurePayment":"1","Ds_Card_Number":"454881******0004","Ds_Card_Country":"724","Ds_Amount":"1200","Ds_Currency":"978","Ds_Order":"00000015","Ds_MerchantCode":"999008881","Ds_Terminal":"001","Ds_Response":"0000","Ds_MerchantData":"","Ds_TransactionType":"0","Ds_ConsumerLanguage":"1","Ds_AuthorisationCode":"629178"} # noqa: E501

                            # Get info
                            amount = params.get("Ds_Amount", None)
                            authorisation = params.get(
                                "Ds_AuthorisationCode",
                                None,
                            ).strip()

                            # Check if payment is ready for confirmation
                            if amount and authorisation:
                                if float(amount) / 100 == self.payment.total:
                                    # Everything is fine, payer verified and
                                    # payment authorized
                                    self.ref = authorisation
                                    self.error = False
                                    self.error_txt = None
                                    self.save()

                                    # Everything whent fine
                                    answer["result"] = "OK"
                                else:
                                    error = (
                                        3,
                                        _(
                                            "Amount doesn't match to the "
                                            "payment request: our={our} - "
                                            "remote={remote}",
                                        ).format(
                                            our=self.payment.total,
                                            remote=float(amount) / 100,
                                        ),
                                    )
                                    logger.error(
                                        f"PS03: Amount doesn't match for "
                                        f"payment {pr.locator}: "
                                        f"our={self.payment.total} - "
                                        f"remote={float(amount) / 100}",
                                    )

                            else:
                                # Find the error if any
                                if not amount:
                                    error = (
                                        3,
                                        _(
                                            "Missing amount in your "
                                            "confirmation request",
                                        ),
                                    )
                                    logger.error(
                                        f"PS03: Missing amount for payment "
                                        f"{pr.locator}",
                                    )
                                elif not authorisation:
                                    # Error code
                                    errorcode = params.get(
                                        "Ds_ErrorCode",
                                        None,
                                    )
                                    if errorcode:
                                        self.ref = errorcode
                                        answer["errorcode"] = errorcode
                                        error = (4, redsys_error(errorcode))
                                        logger.error(
                                            f"PS04: Error code {errorcode} "
                                            f"for payment {pr.locator}",
                                        )
                                    else:
                                        error = (
                                            3,
                                            _(
                                                "Missing authorisation code "
                                                "in your confirmation request",
                                            ),
                                        )
                                        logger.error(
                                            "PS03: Missing authorisation code "
                                            f"for payment {pr.locator}",
                                        )
                                else:
                                    error = (
                                        3,
                                        _(
                                            "Missing info in your "
                                            "confirmation request",
                                        ),
                                    )
                                    logger.error(
                                        f"PS03: Missing info for payment "
                                        f"{pr.locator}",
                                    )

                        else:
                            error = (
                                9,
                                _(
                                    "Invalid signature version: our={our} - "
                                    "remote={remote}",
                                ).format(
                                    our=signature_internal,
                                    remote=signature,
                                ),
                            )
                            logger.error(
                                f"PS09: Invalid signature for payment "
                                f"{pr.locator}: our={signature_internal} - "
                                f"remote={signature}",
                            )

                    else:
                        error = (9, _("Invalid signature version"))
                        logger.error(
                            f"PS09: Invalid signature version for payment "
                            f"{pr.locator}: {signature_version}",
                        )
                else:
                    missing = []
                    if not params:
                        missing.append(
                            _("Ds_MerchantParameters has wrong encoding"),
                        )  # No Base64
                    if not paramsb64:
                        missing.append(_("Missing Ds_MerchantParameters"))
                    if not signature:
                        missing.append(_("Missing Ds_Signature"))
                    if not signature_version:
                        missing.append(_("Missing Ds_SignatureVersion"))
                    error = (
                        6,
                        _("Missing information in data: {missing}").format(
                            missing=", ".join(missing),
                        ),
                    )
                    logger.error(
                        f"PS06: Missing information for payment {pr.locator}: "
                        f"{', '.join(missing)}",
                    )

            elif pr.protocol == "yeepay":
                customer_id = data.get("customerIdentification", None)
                response = data.get("response", None)
                if customer_id and response:
                    config = settings.PAYMENTS.get(pr.protocol, {})

                    if customer_id == config.get("app_key", False):
                        private_key = config.get("private_key", None)
                        private_key_imported = RSA.import_key(
                            "-----BEGIN PRIVATE KEY-----\n"
                            + private_key
                            + "\n-----END PRIVATE KEY-----",
                        )
                        public_key = config.get("public_key", None)
                        public_key_imported = RSA.import_key(
                            "-----BEGIN PUBLIC KEY-----\n"
                            + public_key
                            + "\n-----END PUBLIC KEY-----",
                        )

                        encryptor = RsaEncryptor(
                            private_key=private_key_imported,
                            public_key=public_key_imported,
                        )
                        try:
                            infotxt = encryptor.envelope_decrypt(response)
                        except Exception:
                            infotxt = None
                        if infotxt:
                            # Get object
                            info = json.loads(infotxt)
                            if info:
                                # Update request with fresh data
                                self.request = json.dumps(
                                    {
                                        "customerIdentification": customer_id,
                                        "response": info,
                                    },
                                )
                                self.request_date = timezone.now()

                                # Get retCode
                                errorcode = info.get("retCode", None)
                                if errorcode:
                                    # Error code
                                    self.ref = errorcode
                                    answer["errorcode"] = errorcode
                                    error = (4, yeepay_error(errorcode))
                                    logger.error(
                                        f"PS04: Yeepay error code {errorcode} "
                                        f"for payment {pr.locator}",
                                    )
                                else:
                                    # Check for fields existance
                                    for field in [
                                        "merchantNo",
                                        "orderAmount",
                                        "uniqueOrderNo",
                                        "orderId",
                                        "status",
                                    ]:
                                        if field not in info:
                                            error = (
                                                3,
                                                _(
                                                    "Missing {} in your confirmation request".format(  # noqa: E501
                                                        field,
                                                    ),
                                                ),
                                            )
                                            logger.error(
                                                f"PS03: Missing {field} for "
                                                f"payment {pr.locator}",
                                            )
                                            break

                                    # Verify data inside the package
                                    if not error:
                                        # Get data
                                        local_customer_request_no = (
                                            pr.order_ref
                                        )
                                        try:
                                            merchant_num = str(
                                                info["merchantNo"],
                                            )
                                        except ValueError:
                                            merchant_num = None
                                        try:
                                            amount = Decimal(
                                                info["orderAmount"],
                                            )
                                        except InvalidOperation:
                                            amount = None
                                        unique_order = info["uniqueOrderNo"]

                                        if (
                                            info["orderId"]
                                            != local_customer_request_no
                                        ):
                                            error = (
                                                3,
                                                _("orderId invalid"),
                                            )
                                            logger.error(
                                                f"PS03: orderId invalid for "
                                                f"payment {pr.locator}: "
                                                f"{info['orderId']} != "
                                                f"{local_customer_request_no}",
                                            )
                                        elif merchant_num != config.get(
                                            "merchant_number",
                                            None,
                                        ):
                                            error = (
                                                3,
                                                _("merchantNo invalid"),
                                            )
                                            logger.error(
                                                f"PS03: merchantNo invalid "
                                                f"for payment {pr.locator}: "
                                                f"{merchant_num} != "
                                                f"{config.get('merchant_number', None)}",  # noqa: E501
                                            )
                                        elif info["status"] != "SUCCESS":
                                            error = (
                                                3,
                                                _("Status is not 'SUCCESS'"),
                                            )
                                            logger.error(
                                                "PS03: Status is "
                                                "not 'SUCCESS' "
                                                f"for payment {pr.locator}: "
                                                f"{info['status']}",
                                            )
                                        elif amount != pr.total:
                                            error = (3, _("Amount invalid"))
                                            logger.error(
                                                f"PS03: Amount invalid for "
                                                f"payment {pr.locator}: "
                                                f"{amount} != {pr.total}",
                                            )
                                        elif unique_order == "":
                                            error = (
                                                3,
                                                _("uniqueOrderNo empty"),
                                            )
                                            logger.error(
                                                f"PS03: uniqueOrderNo empty "
                                                f"for payment {pr.locator}",
                                            )

                                        if not error:
                                            # Everything is fine, payer
                                            # verified and payment authorized
                                            self.ref = unique_order
                                            self.error = False
                                            self.error_txt = None
                                            self.save()

                                        # Everything went fine
                                        answer["result"] = "OK"

                            else:
                                # The data we have received is
                                # not JSON encoded (save as is)
                                error = (11, _("Data is not JSON"))
                                logger.error(
                                    f"PS11: Data is not JSON for payment "
                                    f"{pr.locator}: {infotxt}",
                                )
                                self.request = json.dumps(
                                    {
                                        "customerIdentification": customer_id,
                                        "response": infotxt,
                                    },
                                )
                                self.request_date = timezone.now()
                        else:
                            error = (9, "Decryption error")
                            logger.error(
                                f"PS09: Decryption error for payment "
                                f"{pr.locator}: {response}",
                            )
                    else:
                        error = (3, _("Customer id unknown"))
                        logger.error(
                            f"PS03: Customer id unknown for payment "
                            f"{pr.locator}: {customer_id}",
                        )
                else:
                    missing = []
                    if customer_id is None:
                        missing.append("customerIdentification")
                    if response is None:
                        missing.append("response")
                    error = (
                        6,
                        _("Missing information in data: {missing}").format(
                            missing=", ".join(missing),
                        ),
                    )
                    logger.error(
                        f"PS06: Missing information for payment {pr.locator}: "
                        f"{', '.join(missing)}",
                    )
            else:
                error = (
                    1,
                    _("Unknown protocol '{protocol}'").format(
                        protocol=pr.protocol,
                    ),
                )
                logger.error(
                    f"PS01: Error {error[0]} for payment {pr.locator}: "
                    f"{error[1]}",
                )

            # If there are errors
            if error:
                # Prepare to save errors
                self.error = True
                self.error_txt = json.dumps(
                    {"error": error[0], "errortxt": str(error[1])},
                )

                # Set errors in the answer
                answer["error"] = error[0]
                answer["errortxt"] = str(error[1])

            else:
                # No error happened
                self.error = False
                self.error_txt = None

            # Set the answer
            self.answer = json.dumps(answer)
            self.answer_date = timezone.now()

            # Save result and return an answer
            self.save()

        else:
            if pr.protocol == "yeepay":
                answer["result"] = "ALREADY_OK"
            else:
                logger.error(
                    f"PS07: Payment {pr.locator} already confirmed, "
                    "can not be processed twice",
                )
                raise PaymentError(7, _("Payment already processed"))

        # Return answer
        return answer


class PaymentError(Exception):
    """
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
    """  # noqa: E501

    pass
