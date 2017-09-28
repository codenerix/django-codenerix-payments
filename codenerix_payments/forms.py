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

from django.utils.translation import ugettext as _

from codenerix.forms import GenModelForm
from codenerix_payments.models import PaymentRequest


class PaymentRequestForm(GenModelForm):
    class Meta:
        model = PaymentRequest
        exclude = [
            'locator',
            'ref',
            'order',
            'reverse',
            'currency',
            'protocol',
            'real',
            'error',
            'error_txt',
            'cancelled',
            'request',
            'answer']
        autofill = {
            'platform': ['select', 3, 'CDNX_payments_platforms'],
        }

    def __groups__(self):
        g = [
            (_('Details'), 12,
                ['total', 6],
                ['platform', 6],
                ['notes', 12],)
        ]
        return g


class PaymentRequestUpdateForm(GenModelForm):
    class Meta:
        model = PaymentRequest
        exclude = [
            'total',
            'ref',
            'platform',
            'locator',
            'order',
            'reverse',
            'currency',
            'protocol',
            'real',
            'error',
            'error_txt',
            'cancelled',
            'request',
            'answer']

    def __groups__(self):
        g = [
            (_('Details'), 12,
                ['notes', 12],)
        ]
        return g
