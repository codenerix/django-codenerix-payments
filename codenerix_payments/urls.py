# -*- coding: utf-8 -*-
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

from django.urls import re_path as url

from codenerix_payments.views import PaymentRequestList, PaymentRequestCreate, PaymentRequestUpdate, PaymentRequestDelete, \
    PaymentConfirmationList, PaymentAnswerList, PaymentAction, \
    PaymentRequestDetail, PaymentConfirmationDetail, PaymentAnswerDetail, PaymentPlatforms, PaymentConfirmationAutorender

from codenerix_payments.views import CurrencyList, CurrencyCreate, CurrencyDetail, CurrencyUpdate, CurrencyDelete
from codenerix_payments.views import Verifysign


urlpatterns = [
    url(r'^verify_sign$', Verifysign.as_view(), name='verify_sign'),

    url(r'^currencys$', CurrencyList.as_view(), name='currency_list'),
    url(r'^currencys/add$', CurrencyCreate.as_view(), name='currency_add'),
    url(r'^currencys/(?P<pk>\w+)$', CurrencyDetail.as_view(), name='currency_detail'),
    url(r'^currencys/(?P<pk>\w+)/edit$', CurrencyUpdate.as_view(), name='currency_edit'),
    url(r'^currencys/(?P<pk>\w+)/delete$', CurrencyDelete.as_view(), name='currency_delete'),


    url(r'^paymentrequests$', PaymentRequestList.as_view(), name='paymentrequest_list'),
    url(r'^paymentrequests/add$', PaymentRequestCreate.as_view(), name='paymentrequest_add'),
    url(r'^paymentrequests/locate/(?P<locator>[a-zA-Z0-9+/]+)$', PaymentRequestDetail.as_view(), {'pk': 0}, name='CNDX_paymenrequest_detail_locator'),
    url(r'^paymentrequests/(?P<pk>\w+)$', PaymentRequestDetail.as_view(), name='paymentrequest_detail'),
    url(r'^paymentrequests/(?P<pk>\w+)/edit$', PaymentRequestUpdate.as_view(), name='paymentrequest_edit'),
    url(r'^paymentrequests/(?P<pk>\w+)/delete$', PaymentRequestDelete.as_view(), name='paymentrequest_delete'),
    url(r'^paymentconfirmations$', PaymentConfirmationList.as_view(), name='paymentconfirmation_list'),
    url(r'^paymentconfirmations/(?P<pk>\w+)$', PaymentConfirmationDetail.as_view(), name='paymentconfirmation_detail'),
    url(r'^paymentanswers$', PaymentAnswerList.as_view(), name='paymentanswer_list'),
    url(r'^paymentanswers/(?P<pk>\w+)$', PaymentAnswerDetail.as_view(), name='paymentanswer_detail'),
    url(r'^action/(?P<locator>[a-zA-Z0-9+/]+)/(?P<action>\w+)/$', PaymentAction.as_view(), name='payment_url'),
    url(r'^platforms/(?P<search>[\w\W]+|\*)$', PaymentPlatforms.as_view(), name='CDNX_payments_platforms'),
    url(r'^confirmation/(?P<locator>[a-zA-Z0-9+/]+)/(?P<action>\w+)/(?P<error>\w+)$', PaymentConfirmationAutorender.as_view(), name='CNDX_payments_confirmation'),
    url(r'^confirmation/(?P<locator>[a-zA-Z0-9+/]+)/(?P<action>\w+)/(?P<error>\w+)/(?P<errortxt>.+)$', PaymentConfirmationAutorender.as_view(), name='CNDX_payments_confirmation'),
]
