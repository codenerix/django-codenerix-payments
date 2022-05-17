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


import time

from django.core.management.base import BaseCommand, CommandError

from codenerix.lib.debugger import Debugger
from codenerix_payments.models import PaymentRequest, PaymentConfirmation, Currency, PaymentError


class Command(BaseCommand, Debugger):
    
    # Show this when the user types help
    help = "Check paypal library and configuration"
    
    def add_arguments(self, parser):
        
        # Named (optional) arguments
        parser.add_argument(
            '--action',
            action='append',
            dest='action',
            help='Actions can be create, confirm or cancel'
        )
        
        # Named (optional) arguments
        parser.add_argument(
            '--id',
            action='store',
            dest='id',
            type=int,
            help='ID of the action (except create)'
        )
        
        # Named (optional) arguments
        parser.add_argument(
            '--url',
            action='store',
            dest='url',
            help='Confirmation URL from the user to be used in confirm action if available'
        )
    
    def handle(self, *args, **options):
        
        # Autoconfigure Debugger
        self.set_name("PAYPAL")
        self.set_debug()
        
        # Config
        currency_id = "EUR"
        
        # Arguments
        actions = options['action']
        alloptions = actions is None
        cid = None
        if not alloptions:
            for action in actions:
                if action not in ['create', 'confirm', 'cancel']:
                    raise CommandError("Unknow action '{}', you can use 'create', 'confirm' or 'cancel'".format(action))
            if 'confirm' in actions and 'cancel' in actions:
                raise CommandError("Cannot confirm and cancel at the same time")
            for action in ['confirm', 'cancel']:
                if action in actions:
                    cid = options['id']
                    if cid:
                        self.debug("ID detected: {}".format(cid), color='cyan')
                        break
                    else:
                        self.debug("ID required", color='red')
                        raise CommandError('ID required')
        
        # Set and get currency
        cs = Currency.objects.filter(iso4217=currency_id)
        if len(cs) == 0:
            c = Currency()
            c.name = "Euro"  # "Dollar"
            c.symbol = "€".decode("utf-8")  # "$"
            c.iso4217 = currency_id
            c.price = 1.0   # 1.14
            c.save()
            currency = c
        elif len(cs) == 1:
            currency = cs[0]
        else:
            raise IOError("Currency {} found more than once".format(currency_id))
        
        # Payment Request
        if alloptions or 'create' in actions:
            self.debug("Creating Payment Request", color="yellow")
            pr = PaymentRequest()
            pr.order = int(time.time())
            pr.reverse = 'reverse'
            pr.currency = currency
            pr.platform = "paypalonline"
            pr.real = False
            pr.total = 12
            try:
                pr.save()
                self.debug("Payment Request: Created with ID '{}' and LOCATOR '{}'".format(pr.pk, pr.locator), color="green")
            except PaymentError as e:
                self.debug("Payment Request: ERROR - {}".format(e), color="red")
                raise
        else:
            pr = PaymentRequest.objects.get(pk=cid)
            self.debug("Payment Request: Restored ID '{}' and LOCATOR '{}' from database".format(pr.pk, pr.locator), color="green")
        
        # Check if payment hasn't been cancelled before
        if not pr.cancelled:
            # Get Authorization URL
            if alloptions or 'confirm' in actions or 'cancel' in actions:
                # Get approval URL and show to user
                try:
                    self.debug("Approval URL: {}".format(pr.get_approval()['url']), color='cyan')
                except PaymentError as e:
                    self.debug("Approval URL: ERROR - {}".format(e), color="red")
                    raise
                
                # Get confirmation URL
                if options['url']:
                    # Get confirmation URL from command line
                    confirmation = options['url']
                    self.debug("Using confirmation URL from command line: {}".format(confirmation), color='yellow')
                else:
                    # Get confirmation
                    self.debug("Visit approval URL and pay, then when Paypal drives you to our confirmation site, copy and paste the URL here", color='yellow')
                    confirmation = raw_input("URL: ")
                
                # If confirmation URL
                if (len(confirmation.split("?")) > 1) and (len(confirmation.split("/")) > 1):
                    
                    # Process the confirmation URL
                    data = {}
                    for arg in confirmation.split("?")[1].split("&"):
                        (key, value) = arg.split("=")
                        data[key] = value
                    
                    # Get action
                    action = confirmation.split("/")[-2]
                    if action == 'confirm':
                        if (not alloptions) and ('confirm' not in actions):
                            raise CommandError("Not a normal flow payment and not a confirm payment action but URL you gave me was for a confirm payment: 1) or you gave me a mistaken URL, 2) or you told me to do a wrong action")
                    elif action == 'cancel':
                        if (not alloptions) and ('cancel' not in actions):
                            raise CommandError("This is not a cancel payment action but the URL you gave me was for a cancel payment: 1) or you gave me a mistaken URL, 2) or you told me to do a wrong action")
                    else:
                        raise CommandError("The URL that you gave me is not for a 'confirm' neither 'cancel' payment")
                    
                    # Payment Confirm or Cancel
                    if action == 'confirm':
                        self.debug("Confirm payment", color="blue")
                        pc = PaymentConfirmation()
                        try:
                            pc.confirm(pr, data)
                            self.debug("Payment confirmed", color="green")
                        except PaymentError as e:
                            self.debug("Payment confirmed: ERROR - {}".format(e), color="red")
                            raise
                    elif action == 'cancel':
                        # Payment Confirm
                        self.debug("Cancel payment", color="blue")
                        pc = PaymentConfirmation()
                        try:
                            pc.cancel(pr, data)
                            self.debug("Payment canceled", color="yellow")
                        except PaymentError as e:
                            self.debug("Payment cancel: ERROR - {}".format(e), color="red")
                            raise
                else:
                    self.debug("No URL given: stopping process here", color='yellow')
        else:
            raise CommandError("This payment has been cancelled previously, sorry!")
