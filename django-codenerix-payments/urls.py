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

from django.conf.urls import url

from codenerix_payments.views import PaymentRequestList, PaymentConfirmationList, PaymentAnswerList, PaymentAction, \
    PaymentRequestDetail, PaymentConfirmationDetail, PaymentAnswerDetail


urlpatterns = [
    url(r'^paymentrequests$', PaymentRequestList.as_view(), name='paymentrequest_list'),
    url(r'^paymentrequests/(?P<pk>\w+)$', PaymentRequestDetail.as_view(), name='paymentrequest_detail'),
    url(r'^paymentconfirmations$', PaymentConfirmationList.as_view(), name='paymentconfirmation_list'),
    url(r'^paymentconfirmations/(?P<pk>\w+)$', PaymentConfirmationDetail.as_view(), name='paymentconfirmation_detail'),
    url(r'^paymentanswers$', PaymentAnswerList.as_view(), name='paymentanswer_list'),
    url(r'^paymentanswers/(?P<pk>\w+)$', PaymentAnswerDetail.as_view(), name='paymentanswer_detail'),
    url(r'^action/(?P<locator>[a-zA-Z0-9+/]+)/(?P<action>\w+)/$', PaymentAction.as_view(), name='payment_url'),
]
