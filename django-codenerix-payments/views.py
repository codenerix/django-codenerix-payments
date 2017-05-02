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
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _

from codenerix.views import GenList, GenDetail

from codenerix_payments.models import PaymentRequest, PaymentConfirmation, PaymentAnswer, PaymentError


class PaymentRequestList(GenList):
    model = PaymentRequest
    linkadd = False
    show_details = True
    default_ordering = ["-request_date"]


class PaymentRequestDetail(GenDetail):
    model = PaymentRequest
    groups = [
        (_('Information'), 6,
            ['locator', 6],
            ['ref', 6],
            ['order', 6],
            ['reverse', 6],
            ['platform', 6],
            ['protocol', 6]
        ),
        (_('Process'), 6,
            ['real', 6],
            ['cancelled', 6],
            ['total', 6],
            ['currency', 6],
            ['error', 6],
            ['error_txt', 6],
        ),
        (_('Request'), 6,
            ['request_date', 12],
            ['request', 12]
        ),
        (_('Answer'), 6,
            ['answer_date', 12],
            ['answer', 12]
        ),
        (_('Notes'), 12,
            ['notes', 6]
        ),
    ]
    linkedit = False
    linkdelete = False


class PaymentConfirmationList(GenList):
    model = PaymentConfirmation
    linkadd = False
    show_details = True
    default_ordering = ["-created"]


class PaymentConfirmationDetail(GenDetail):
    model = PaymentConfirmation
    groups = [
        (_('Information'), 6,
            ['payment', 6],
            ['ref', 6]
        ),
        (_('Process'), 6,
            ['error', 6],
            ['error_txt',6]
        ),
        (_('Result'), 12,
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


class PaymentAnswerDetail(GenDetail):
    model = PaymentAnswer
    groups = [
        (_('Information'), 6,
            ['payment', 6],
            ['ref', 6],
        ),
        (_('Process'), 6,
            ['error', 6],
            ['error_txt', 6],
        ),
        (_('Request'), 6,
            ['request_date', 12],
            ['request', 12]
        ),
        (_('Answer'), 6,
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
        import datetime
        with open("/tmp/codenerix_info.txt", "a") as F:
            now = datetime.datetime.now()
            F.write("\n\n{} - Start\n".format(now))
            
            # Get incoming details
            locator = kwargs.get('locator', None)
            action = kwargs.get('action', None)
            F.write("{} - Start CID;{} ACTION:{}\n".format(now, locator, action))
            
            # Find the payment request
            try:
                pr = PaymentRequest.objects.get(locator=locator)
            except PaymentRequest.DoesNotExist:
                pr = None
            if pr:
                F.write("{} - PR {} - REVERSE:{}\n".format(now, pr, pr.reverse))
            else:
                F.write("{} - PR NOT FOUND!\n")
            
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
                            answer['error'] = 'PC{:02d}'.format(e[0])
                        
                    elif action == 'cancel':
                        pc = PaymentConfirmation()
                        try:
                            pc.cancel(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e[0])
                    else:
                        # ERROR: Unknown action for paypal (only allowed 'confirm' or 'cancel'
                        answer['error'] = 'P004'
                
                # --- REDSYS / REDSYSXML ---
                elif pr.protocol in ['redsys', 'redsysxml']:
                    
                    if action == 'success':
                        
                        F.write("{} - SUCCESS\n".format(now))
                        # This answer must be in JSON format
                        answer_json = True
                        
                        pa = PaymentAnswer()
                        try:
                            answer = pa.success(pr, request.POST)
                            F.write("{} - PA Success\n".format(now))
                            F.flush()
                            pa.payment.notify(request)
                            F.write("{} - NOTIFY Success\n".format(now))
                            F.flush()
                        except PaymentError as e:
                            F.write("{} - NOTIFY Error - {}\n".format(now, e))
                            F.flush()
                            answer['error'] = 'PS{:02d}'.format(e[0])
                        
                    elif action == 'confirm':
                        pc = PaymentConfirmation()
                        try:
                            pc.confirm(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e[0])
                        
                    elif action == 'cancel':
                        pc = PaymentConfirmation()
                        try:
                            pc.cancel(pr, request.GET)
                        except PaymentError as e:
                            answer['error'] = 'PC{:02d}'.format(e[0])
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
                return HttpResponseRedirect(reverse(pr.reverse, kwargs=answer))
            
            # GET:  <QueryDict: {}>
            # POST: <QueryDict: {u'Ds_Signature': [u'cURiymdHBZof0dhnWCHki7muP59t9o5SNJy5nVLrGew='], u'Ds_MerchantParameters': [u'eyJEc19EYXRlIjoiMjNcLzA4XC8yMDE2IiwiRHNfSG91ciI6IjE3OjUyIiwiRHNfU2VjdXJlUGF5bWVudCI6IjEiLCJEc19DYXJkX051bWJlciI6IjQ1NDg4MSoqKioqKjAwMDQiLCJEc19DYXJkX0NvdW50cnkiOiI3MjQiLCJEc19BbW91bnQiOiIxMjAwIiwiRHNfQ3VycmVuY3kiOiI5NzgiLCJEc19PcmRlciI6IjAwMDAwMDE1IiwiRHNfTWVyY2hhbnRDb2RlIjoiOTk5MDA4ODgxIiwiRHNfVGVybWluYWwiOiIwMDEiLCJEc19SZXNwb25zZSI6IjAwMDAiLCJEc19NZXJjaGFudERhdGEiOiIiLCJEc19UcmFuc2FjdGlvblR5cGUiOiIwIiwiRHNfQ29uc3VtZXJMYW5ndWFnZSI6IjEiLCJEc19BdXRob3Jpc2F0aW9uQ29kZSI6IjYyOTE3OCJ9'], u'Ds_SignatureVersion': [u'HMAC_SHA256_V1']}>
            # REQUEST: <WSGIRequest: POST '/payments/action/15/success/'>
            # ARGS: ()
            # KWARGS: {'action': u'success', 'cid': u'15'}
