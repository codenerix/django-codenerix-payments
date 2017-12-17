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

from django.views.generic import View
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _, ugettext as __
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render

from codenerix.views import GenList, GenDetail, GenCreate, GenUpdate, GenDelete, GenForeignKey

from codenerix_payments.models import PaymentRequest, PaymentConfirmation, PaymentAnswer, PaymentError, Currency
from codenerix_payments.forms import PaymentRequestForm, PaymentRequestUpdateForm


class PaymentRequestList(GenList):
    model = PaymentRequest
    linkadd = getattr(settings, 'CDNX_PAYMENTS_REQUEST_CREATE', False)
    show_details = True
    default_ordering = ["-request_date"]
    gentranslate = {'pay': __("Pay"), 'yes': __("Yes"), 'no': __("No"), 'cancel': __("Cancel")}

    def dispatch(self, *args, **kwargs):
        self.client_context = {'cancelurl': reverse('payment_url', kwargs={'action': 'cancel', 'locator': 'LOCATOR'})}
        if getattr(settings, 'CDNX_PAYMENTS_REQUEST_PAY', False):
            self.static_partial_row = "codenerix_payments/partials/paymentslist_rows.html"
        return super(PaymentRequestList, self).dispatch(*args, **kwargs)


class PaymentRequestCreate(GenCreate):
    model = PaymentRequest
    form_class = PaymentRequestForm

    def form_valid(self, form):

        # Get selected platform
        platform = form.cleaned_data["platform"]

        # Get payment profile from configuration
        profile = settings.PAYMENTS[platform]

        # Get the currency
        currency = Currency.objects.filter(iso4217='EUR').first()
        if not currency:
            currency = Currency()
            currency.name = "Euro"
            currency.symbol = u"€".encode("utf-8")
            currency.iso4217 = 'EUR'
            currency.price = 1.0
            currency.save()

        # Set missing variables in the instance
        form.instance.alternative = True
        form.instance.order = 0
        form.instance.reverse = "autorender"
        form.instance.currency = currency
        form.instance.protocol = profile['protocol']

        # Let Django finish the job
        return super(PaymentRequestCreate, self).form_valid(form)


class PaymentRequestUpdate(GenUpdate):
    model = PaymentRequest
    form_class = PaymentRequestUpdateForm


class PaymentRequestDetail(GenDetail):
    model = PaymentRequest
    groups = [
        (
            _('Information'), 6,
            ['locator', 6],
            ['ref', 6],
            ['order', 6],
            ['reverse', 6],
            ['platform', 6],
            ['protocol', 6]
        ),
        (
            _('Process'), 6,
            ['real', 6],
            ['cancelled', 6],
            ['total', 6],
            ['currency', 6],
            ['error', 6],
            ['error_txt', 6],
        ),
        (
            _('Request'), 6,
            ['request_date', 12],
            ['request', 12]
        ),
        (
            _('Answer'), 6,
            ['answer_date', 12],
            ['answer', 12]
        ),
        (
            _('Notes'), 12,
            ['notes', 6]
        ),
    ]
    linkedit = getattr(settings, 'CDNX_PAYMENTS_REQUEST_UPDATE', False)
    linkdelete = getattr(settings, 'CDNX_PAYMENTS_REQUEST_DELETE', False)


class PaymentRequestDelete(GenDelete):
    model = PaymentRequest


class PaymentPlatforms(GenForeignKey):
    model = PaymentRequest

    def get_label(self, pk):
        name = pk
        for platform in settings.PAYMENTS.keys():
            if pk == platform:
                name = settings.PAYMENTS[platform].get('name', platform)
                break
        return name

    def get(self, request, *args, **kwargs):
        # Build answer
        answer = [{'id': None, 'label': '---------'}]
        search = kwargs.get('search', '').lower()

        for platform in settings.PAYMENTS.keys():
            name = settings.PAYMENTS[platform].get('name', platform)
            if platform != 'meta' and (not search or search == '*' or search in platform or search in name.lower()):
                answer.append({'id': platform, 'label': name})

        # Convert the answer to JSON
        json_answer = json.dumps({
            'clear': [],
            'rows': answer,
            'readonly': [],
        })

        # Return response
        return HttpResponse(json_answer, content_type='application/json')


class PaymentConfirmationList(GenList):
    model = PaymentConfirmation
    linkadd = False
    show_details = True
    default_ordering = ["-created"]
    static_partial_row = "codenerix_payments/partials/paymentsconfirmlist_rows.html"
    gentranslate = {'yes': __("Yes"), 'no': __("No")}


class PaymentConfirmationDetail(GenDetail):
    model = PaymentConfirmation
    groups = [
        (
            _('Information'), 6,
            ['payment', 6],
            ['ref', 6]
        ),
        (
            _('Process'), 6,
            ['error', 6],
            ['error_txt', 6]
        ),
        (
            _('Result'), 12,
            ['action', 12],
            ['data', 12]
        ),
    ]
    linkedit = False
    linkdelete = False


class PaymentAnswerList(GenList):
    model = PaymentAnswer
    linkadd = False
    show_details = True
    default_ordering = ["-request_date"]
    static_partial_row = "codenerix_payments/partials/paymentsanswerlist_rows.html"
    gentranslate = {'yes': __("Yes"), 'no': __("No")}


class PaymentAnswerDetail(GenDetail):
    model = PaymentAnswer
    groups = [
        (
            _('Information'), 6,
            ['payment', 6],
            ['ref', 6],
        ),
        (
            _('Process'), 6,
            ['error', 6],
            ['error_txt', 6],
        ),
        (
            _('Request'), 6,
            ['request_date', 12],
            ['request', 12]
        ),
        (
            _('Answer'), 6,
            ['answer', 12],
            ['answer_date', 12]
        ),
    ]
    linkedit = False
    linkdelete = False


class PaymentAction(View):
    '''
    This view is responsible to manage the reuqest from users that are coming to the platform back from the remote systems, it also manage the request from remote system about payment confirmations. The users will be redirected to a reverse URL set in the PaymentRequest when created and the remote systems will get an answer in JSON format.

    ERROR CODES:
    ============
    P001: PaymentRequest not found
    P002: Unknown protocol
    P003: Unknown action for redsys/redsysxml (only allowed 'success', 'confirm' or 'cancel')
    P004: Unknown action for paypal (only allowed 'confirm' or 'cancel')

    PaymentAnswer
    PCxx: Error al gestionar un PaymentConfirmation
    PAxx: Error al gestionar un PaymentAnswer
    PSxx: Error al gestionar un PaymentSuccess
    ( xx : to know these codes please check the class PaymentError in models.py )
    '''

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # import datetime
        # with open("/tmp/codenerix_info.txt", "a") as F:
        if True:
            # now = datetime.datetime.now()
            # F.write("\n\n{} - Start\n".format(now))

            # Get incoming details
            locator = kwargs.get('locator', None)
            action = kwargs.get('action', None)
            # F.write("{} - Start CID;{} ACTION:{}\n".format(now, locator, action))

            # Find the payment request
            try:
                pr = PaymentRequest.objects.get(locator=locator)
            except PaymentRequest.DoesNotExist:
                pr = None
            # if pr:
            #    F.write("{} - PR {} - REVERSE:{}\n".format(now, pr, pr.reverse))
            # else:
            #    F.write("{} - PR NOT FOUND!\n")

            # Prepare answer
            answer = {'action': action, 'locator': locator, 'error': 0}

            # Set the kind of answer (if the reverse string is 'reverse', JSON will be used)
            answer_json = (not pr) or (pr.reverse == 'reverse')

            # Check if we found the payment request
            if pr:

                # --- PAYPAL ---
                if pr.protocol == 'paypal':

                    if action == 'confirm':
                        pc = PaymentConfirmation()
                        try:
                            pc.confirm(pr, request.GET)
                            pc.payment.notify(request)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e.args[0])

                    elif action == 'cancel':
                        pc = PaymentConfirmation()
                        try:
                            pc.cancel(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e.args[0])
                    else:
                        # ERROR: Unknown action for paypal (only allowed 'confirm' or 'cancel'
                        answer['error'] = 'P004'

                # --- REDSYS / REDSYSXML ---
                elif pr.protocol in ['redsys', 'redsysxml']:

                    if action == 'success':

                        # F.write("{} - SUCCESS\n".format(now))
                        # This answer must be in JSON format
                        answer_json = True

                        pa = PaymentAnswer()
                        try:
                            answer = pa.success(pr, request.POST)
                            # F.write("{} - PA Success\n".format(now))
                            # F.flush()
                            pa.payment.notify(request)
                            # F.write("{} - NOTIFY Success\n".format(now))
                            # F.flush()
                        except PaymentError as e:
                            # F.write("{} - NOTIFY Error - {}\n".format(now, e))
                            # F.flush()
                            answer['error'] = 'PS{:02d}'.format(e.args[0])

                    elif action == 'confirm':
                        pc = PaymentConfirmation()
                        try:
                            pc.confirm(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e.args[0])

                    elif action == 'cancel':
                        pc = PaymentConfirmation()
                        try:
                            pc.cancel(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e.args[0])
                    else:
                        # ERROR: Unknown action for redsys/redsysxml (only allowed 'success', 'confirm' or 'cancel'
                        answer['error'] = 'P003'

                # --- Unknown protocol ---
                else:
                    answer['error'] = 'P002'  # ERROR: Unknown protocol

            else:
                # ERROR: PaymentRequest not found
                answer['error'] = 'P001'

            # Return using JSON or normal redirect
            if answer_json:
                return HttpResponse(json.dumps(answer), content_type='application/json')
            else:
                if pr.reverse == 'autorender' or bool(self.request.GET.get('autorender', self.request.POST.get('autorender', False))):
                    return HttpResponseRedirect(reverse('CNDX_payments_confirmation', kwargs=answer))
                else:
                    return HttpResponseRedirect(reverse(pr.reverse, kwargs=answer))

            # GET:  <QueryDict: {}>
            # POST: <QueryDict: {u'Ds_Signature': [u'cURiymdHBZof0dhnWCHki7muP59t9o5SNJy5nVLrGew='], u'Ds_MerchantParameters': [u'eyJEc19EYXRlIjoiMjNcLzA4XC8yMDE2IiwiRHNfSG91ciI6IjE3OjUyIiwiRHNfU2VjdXJlUGF5bWVudCI6IjEiLCJEc19DYXJkX051bWJlciI6IjQ1NDg4MSoqKioqKjAwMDQiLCJEc19DYXJkX0NvdW50cnkiOiI3MjQiLCJEc19BbW91bnQiOiIxMjAwIiwiRHNfQ3VycmVuY3kiOiI5NzgiLCJEc19PcmRlciI6IjAwMDAwMDE1IiwiRHNfTWVyY2hhbnRDb2RlIjoiOTk5MDA4ODgxIiwiRHNfVGVybWluYWwiOiIwMDEiLCJEc19SZXNwb25zZSI6IjAwMDAiLCJEc19NZXJjaGFudERhdGEiOiIiLCJEc19UcmFuc2FjdGlvblR5cGUiOiIwIiwiRHNfQ29uc3VtZXJMYW5ndWFnZSI6IjEiLCJEc19BdXRob3Jpc2F0aW9uQ29kZSI6IjYyOTE3OCJ9'], u'Ds_SignatureVersion': [u'HMAC_SHA256_V1']}>
            # REQUEST: <WSGIRequest: POST '/payments/action/15/success/'>
            # ARGS: ()
            # KWARGS: {'action': u'success', 'cid': u'15'}


class PaymentConfirmationAutorender(View):
    template_name = 'codenerix_payments/confirmation.html'

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):

        # Get PaymentRequest if any
        locator = kwargs.get('locator', None)
        if locator:
            pr = PaymentRequest.objects.filter(locator=locator).first()
        else:
            pr = None

        # Check if it is already paid
        paid = pr.paymentanswers.filter(ref__isnull=False).first()

        # Build context
        context = {}
        context['request'] = pr
        context['confirmation'] = paid
        context['error'] = kwargs.get('error', None)
        context['action'] = kwargs.get('action', None)

        # Render
        return render(request, self.template_name, context)
