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

import json

from django.views.generic import View
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _, gettext as __
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q
from django.shortcuts import render

from codenerix.helpers import get_client_ip
from codenerix.views import (
    GenList,
    GenDetail,
    GenCreate,
    GenUpdate,
    GenDelete,
    GenForeignKey,
)

from codenerix_payments.models import (
    PaymentRequest,
    PaymentConfirmation,
    PaymentAnswer,
    PaymentError,
    Currency,
)
from codenerix_payments.forms import (
    PaymentRequestForm,
    PaymentRequestUpdateForm,
    CurrencyForm,
)


class CurrencyList(GenList):
    model = Currency


class CurrencyCreate(GenCreate):
    model = Currency
    form_class = CurrencyForm


class CurrencyDetail(GenDetail):
    model = Currency
    form_class = CurrencyForm


class CurrencyUpdate(GenUpdate):
    model = Currency
    form_class = CurrencyForm


class CurrencyDelete(GenDelete):
    model = Currency


class PaymentRequestList(GenList):
    model = PaymentRequest
    linkadd = getattr(settings, "CDNX_PAYMENTS_REQUEST_CREATE", False)
    show_details = True
    default_ordering = ["-request_date"]
    gentranslate = {
        "pay": __("Pay"),
        "paid": __("Paid"),
        "yes": __("Yes"),
        "no": __("No"),
        "cancel": __("Cancel"),
        "cancelled": __("Cancelled"),
        "error": __("Error"),
    }

    def dispatch(self, *args, **kwargs):
        self.client_context = {
            "cancelurl": reverse(
                "payment_url", kwargs={"action": "cancel", "locator": "LOCATOR"}
            )
        }
        if getattr(settings, "CDNX_PAYMENTS_REQUEST_PAY", False):
            self.static_partial_row = (
                "codenerix_payments/partials/paymentslist_rows.html"
            )
        return super(PaymentRequestList, self).dispatch(*args, **kwargs)


class PaymentRequestCreate(GenCreate):
    model = PaymentRequest
    form_class = PaymentRequestForm

    def form_valid(self, form):

        # Get selected platform
        platform = form.cleaned_data["platform"]

        # Get payment profile from configuration
        profile = settings.PAYMENTS[platform]

        currency = form.cleaned_data.get("currency", None)
        if not currency:
            # Get the currency
            currency = Currency.objects.filter(iso4217="EUR").first()
            if not currency:
                currency = Currency()
                currency.name = "Euro"
                currency.symbol = "€".encode("utf-8")
                currency.iso4217 = "EUR"
                currency.price = 1.0
                currency.save()

        reverse = form.cleaned_data.get("reverse", "autorender")
        order = form.cleaned_data.get("order", 0)

        # Set missing variables in the instance
        form.instance.ip = get_client_ip(self.request)
        form.instance.alternative = True
        form.instance.order = order
        form.instance.reverse = reverse
        form.instance.currency = currency
        form.instance.protocol = profile["protocol"]

        # Let Django finish the job
        return super(PaymentRequestCreate, self).form_valid(form)


class PaymentRequestUpdate(GenUpdate):
    model = PaymentRequest
    form_class = PaymentRequestUpdateForm


class PaymentRequestDetail(GenDetail):
    model = PaymentRequest
    groups = [
        (
            _("Information"),
            6,
            ["locator", 6],
            ["ref", 6],
            ["order", 6],
            ["reverse", 6],
            ["platform", 6],
            ["protocol", 6],
        ),
        (
            _("Process"),
            6,
            ["real", 6],
            ["cancelled", 6],
            ["total", 6],
            ["currency", 6],
            ["error", 6],
            ["is_paid", 6, _("Paid")],
            ["error_txt", 6],
        ),
        (_("Request"), 6, ["request_date", 12], ["request", 12]),
        (_("Answer"), 6, ["answer_date", 12], ["answer", 12]),
        (_("Notes"), 12, ["notes", 6]),
        (_("Feedback"), 12, ["feedback", 6]),
    ]

    linkedit = getattr(settings, "CDNX_PAYMENTS_REQUEST_UPDATE", False)
    linkdelete = getattr(settings, "CDNX_PAYMENTS_REQUEST_DELETE", False)

    def get_object(self):
        locator = self.kwargs.get("locator", None)
        if locator:
            return get_object_or_404(self.get_queryset(), locator=locator)
        else:
            return super(PaymentRequestDetail, self).get_object()


class PaymentRequestDelete(GenDelete):
    model = PaymentRequest


class PaymentPlatforms(GenForeignKey):
    model = PaymentRequest

    def get_label(self, pk):
        name = pk
        for platform in settings.PAYMENTS.keys():
            if pk == platform:
                name = settings.PAYMENTS[platform].get("name", platform)
                break
        return name

    def get(self, request, *args, **kwargs):
        # Build answer
        answer = [{"id": None, "label": "---------"}]
        search = kwargs.get("search", "").lower()

        for platform in settings.PAYMENTS.keys():
            name = settings.PAYMENTS[platform].get("name", platform)
            if platform != "meta" and (
                not search
                or search == "*"
                or search in platform
                or search in name.lower()
            ):
                answer.append({"id": platform, "label": name})

        # Convert the answer to JSON
        json_answer = json.dumps(
            {
                "clear": [],
                "rows": answer,
                "readonly": [],
            }
        )

        # Return response
        return HttpResponse(json_answer, content_type="application/json")


class PaymentConfirmationList(GenList):
    model = PaymentConfirmation
    linkadd = False
    show_details = True
    default_ordering = ["-created"]
    static_partial_row = "codenerix_payments/partials/paymentsconfirmlist_rows.html"
    gentranslate = {"yes": __("Yes"), "no": __("No")}


class PaymentConfirmationDetail(GenDetail):
    model = PaymentConfirmation
    groups = [
        (_("Information"), 6, ["payment", 6], ["ref", 6]),
        (_("Process"), 6, ["error", 6], ["error_txt", 6]),
        (_("Result"), 12, ["action", 12], ["data", 12]),
    ]
    linkedit = False
    linkdelete = False


class PaymentAnswerList(GenList):
    model = PaymentAnswer
    linkadd = False
    show_details = True
    default_ordering = ["-request_date"]
    static_partial_row = "codenerix_payments/partials/paymentsanswerlist_rows.html"
    gentranslate = {"yes": __("Yes"), "no": __("No")}


class PaymentAnswerDetail(GenDetail):
    model = PaymentAnswer
    groups = [
        (
            _("Information"),
            6,
            ["payment", 6],
            ["ref", 6],
        ),
        (
            _("Process"),
            6,
            ["error", 6],
            ["error_txt", 6],
        ),
        (_("Request"), 6, ["request_date", 12], ["request", 12]),
        (_("Answer"), 6, ["answer", 12], ["answer_date", 12]),
    ]
    linkedit = False
    linkdelete = False


class PaymentAction(View):
    """
    This view is responsible to manage the request from users that are coming to the platform back from the remote systems, it also manage the request from remote system about payment confirmations. The users will be redirected to a reverse URL set in the PaymentRequest when created and the remote systems will get an answer in JSON format.

    ERROR CODES:
    ============
    P001: PaymentRequest not found
    P002: Unknown protocol
    P003: Unknown action for redsys/redsysxml (only allowed 'success', 'confirm' or 'cancel')
    P004: Unknown action for paypal (only allowed 'confirm' or 'cancel')
    P005: Unknown action for yeepay (only allowed 'confirm')

    PaymentAnswer
    PCxx: Error al gestionar un PaymentConfirmation
    PAxx: Error al gestionar un PaymentAnswer
    PSxx: Error al gestionar un PaymentSuccess
    ( xx : to know these codes please check the class PaymentError in models.py )
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # import datetime
        # with open("/tmp/codenerix_info.txt", "a") as F:
        if True:
            # now = datetime.datetime.now()
            # F.write("\n\n{} - Start\n".format(now))

            # Get incoming details
            locator = kwargs.get("locator", None)
            action = kwargs.get("action", None)
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
            answer = {"action": action, "locator": locator, "error": 0}

            # Set the kind of answer (if the reverse string is 'reverse', JSON will be used)
            answer_json = (not pr) or (pr.reverse == "reverse")

            # Check if we found the payment request
            if pr:

                # --- PAYPAL ---
                if pr.protocol == "paypal":

                    if action == "confirm":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.confirm(pr, request.GET, request)
                            pc.payment.notify(request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    elif action == "cancel":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.cancel(pr, request.GET, request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    else:
                        # ERROR: Unknown action for paypal (only allowed 'confirm' or 'cancel'
                        answer["error"] = "P004"

                # --- REDSYS / REDSYSXML ---
                elif pr.protocol in ["redsys", "redsysxml"]:

                    if action == "success":

                        # F.write("{} - SUCCESS\n".format(now))
                        # This answer must be in JSON format
                        answer_json = True

                        pa = PaymentAnswer()
                        # pa.ip = get_client_ip(self.request)
                        try:
                            answer = pa.success(pr, request.POST, request)
                            # F.write("{} - PA Success\n".format(now))
                            # F.flush()
                            pa.payment.notify(request, answer=answer)
                            # F.write("{} - NOTIFY Success\n".format(now))
                            # F.flush()
                        except PaymentError as e:
                            # F.write("{} - NOTIFY Error - {}\n".format(now, e))
                            # F.flush()
                            answer["error"] = "PS{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    elif action == "confirm":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.confirm(pr, request.GET, request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    elif action == "cancel":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.cancel(pr, request.GET, request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    else:
                        # ERROR: Unknown action for redsys/redsysxml (only allowed 'success', 'confirm' or 'cancel'
                        answer["error"] = "P003"

                # --- YEEPAY ---
                elif pr.protocol == "yeepay":

                    if action == "success":

                        # F.write("{} - SUCCESS\n".format(now))
                        # This answer must be in JSON format
                        answer_json = True

                        pa = PaymentAnswer()
                        # pa.ip = get_client_ip(self.request)
                        try:
                            answer = pa.success(pr, request.POST, request)
                            # F.write("{} - PA Success\n".format(now))
                            # F.flush()
                            pa.payment.notify(request, answer=answer)
                            # F.write("{} - NOTIFY Success\n".format(now))
                            # F.flush()
                        except PaymentError as e:
                            # F.write("{} - NOTIFY Error - {}\n".format(now, e))
                            # F.flush()
                            answer["error"] = "PS{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    elif action == "confirm":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.confirm(pr, request.GET, request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    elif action == "cancel":
                        pc = PaymentConfirmation()
                        # pc.ip = get_client_ip(self.request)
                        try:
                            pc.cancel(pr, request.GET, request)
                        except PaymentError as e:
                            answer["error"] = "PC{:02d}".format(e.args[0])
                            if settings.DEBUG:
                                answer["errortxt"] = str(e.args[1])

                    else:
                        # ERROR: Unknown action for yeepay (only allowed 'success', 'confirm' or 'cancel')
                        answer["error"] = "P005"

                # --- Unknown protocol ---
                else:
                    answer["error"] = "P002"  # ERROR: Unknown protocol

            else:
                # ERROR: PaymentRequest not found
                answer["error"] = "P001"

            # Return using JSON or normal redirect
            if answer_json:
                return HttpResponse(json.dumps(answer), content_type="application/json")
            else:
                if pr.reverse == "autorender" or bool(
                    self.request.GET.get(
                        "autorender", self.request.POST.get("autorender", False)
                    )
                ):
                    keys = ["action", "error", "locator"]
                    if settings.DEBUG:
                        keys.append("errortxt")
                    newanswer = {}
                    for key in keys:
                        if key in answer:
                            newanswer[key] = answer[key]
                        else:
                            newanswer[key] = "-"
                    return HttpResponseRedirect(
                        reverse("CNDX_payments_confirmation", kwargs=newanswer)
                    )
                else:
                    return HttpResponseRedirect(reverse(pr.reverse, kwargs=answer))

            # GET:  <QueryDict: {}>
            # POST: <QueryDict: {u'Ds_Signature': [u'cURiymdHBZof0dhnWCHki7muP59t9o5SNJy5nVLrGew='], u'Ds_MerchantParameters': [u'eyJEc19EYXRlIjoiMjNcLzA4XC8yMDE2IiwiRHNfSG91ciI6IjE3OjUyIiwiRHNfU2VjdXJlUGF5bWVudCI6IjEiLCJEc19DYXJkX051bWJlciI6IjQ1NDg4MSoqKioqKjAwMDQiLCJEc19DYXJkX0NvdW50cnkiOiI3MjQiLCJEc19BbW91bnQiOiIxMjAwIiwiRHNfQ3VycmVuY3kiOiI5NzgiLCJEc19PcmRlciI6IjAwMDAwMDE1IiwiRHNfTWVyY2hhbnRDb2RlIjoiOTk5MDA4ODgxIiwiRHNfVGVybWluYWwiOiIwMDEiLCJEc19SZXNwb25zZSI6IjAwMDAiLCJEc19NZXJjaGFudERhdGEiOiIiLCJEc19UcmFuc2FjdGlvblR5cGUiOiIwIiwiRHNfQ29uc3VtZXJMYW5ndWFnZSI6IjEiLCJEc19BdXRob3Jpc2F0aW9uQ29kZSI6IjYyOTE3OCJ9'], u'Ds_SignatureVersion': [u'HMAC_SHA256_V1']}>
            # REQUEST: <WSGIRequest: POST '/payments/action/15/success/'>
            # ARGS: ()
            # KWARGS: {'action': u'success', 'cid': u'15'}


class PaymentConfirmationAutorender(View):
    template_name = "codenerix_payments/confirmation.html"

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):

        # Get PaymentRequest if any
        locator = kwargs.get("locator", None)
        if locator:
            pr = PaymentRequest.objects.filter(locator=locator).first()
        else:
            pr = None

        # Check if it is already paid
        paid = pr.paymentanswers.filter(ref__isnull=False).first()

        # Build context
        context = {}
        context["request"] = pr
        context["confirmation"] = paid
        context["error"] = kwargs.get("error", None)
        context["errortxt"] = kwargs.get("errortxt", None)
        context["action"] = kwargs.get("action", None)

        # Render
        return render(request, self.template_name, context)


class Verifysign(View):
    template_name = "codenerix_payments/confirmation.html"

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        answer = {"hola": "OK"}
        print(request.__dict__)
        print(request.GET)
        """
        print(request._post.keys())
        print(len(request._post.keys()))
        print("_______________________")
        post_str = list(request._post.keys())[0]
        print(post_str)
        print(type(post_str))
        print("_______________________")
        post = json.loads(post_str)
        print(post)
        print("_______________________")
        """

        # print(request.GET['authtoken'])
        return HttpResponse(json.dumps(answer), content_type="application/json")
        """

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
        """
