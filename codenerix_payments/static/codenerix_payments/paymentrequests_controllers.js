'use strict';
codenerix_addlib('codenerixPaymentRequestControllers');
angular
.module('codenerixPaymentRequestControllers', [])
.factory('Refund', ['$resource', function($resource) {
    return function(refundurl) {
        var url = refundurl.replace("LOCATOR", ":locator");
        return $resource(url, {locator: '@locator'}, {
            refund: {
                method: 'GET',
                params: {
                    amount: '@amount',
                    autorender:1,
                    json:{}
                },
                isArray: false
            }
        });
    }
}])
.controller('codenerixPaymentRequestCtrl', ['$scope', '$timeout','$uibModal','Refund',
    function($scope, $timeout, $uibModal, Refund) {
        $scope.submit_approval = function(pk, apr) {
            if (apr.form) {
                // console.log("Redsys");
                var html = '';
                html+='<form id="PaymentInternalForm'+pk+'" method="post" action="'+apr.url+'" target="PaymentInternalWindow'+pk+'">';
                angular.forEach(apr.form, function(value, key) {
                    html+='<input type="hidden" name="'+key+'" value="'+value+'" />';
                });
                html+='</form>'
                $('#PaymentInternalFormHTML'+pk).html(html);
                window.open('', 'PaymentInternalWindow'+pk);
                $('#PaymentInternalForm'+pk).submit();
            } else {
                // console.log("Paypal");
                window.open(apr.url);
            }
        };
        $scope.submit_return = function(row, returnurl) {

            var title = $scope.data.meta.gentranslate.refund_title + " " + row.order + `(`+ row.order_ref+`)`;
            var amount = 0;
            var max_amount = row.total - row.total_returned;
            var static_url = $scope.data.meta.url_static;
            var template = '<div class=\'modal-body text-center h1\' codenerix-html-compile=\'refundmodal.html\'></div>';
            $scope.refundmodal = {'html': `
                <div class="modal-header ng-scope">
                    <h3 class="modal-title text-center">` + title + `</h3>
                </div>
                <div class="row clearfix ng-scope">
                    <div class="modal-body">
                        <div class='modal-body text-center h4'>
                            <div class="col-md-2"></div>
                            <div class="col-md-8">
                                <form class="form-horizontal">
                                <div class="form-group">
                                    <div class="row clearfix">
                                        <label
                                            class="col-sm-3 control-label"
                                            for="id_amount">
                                                ` + $scope.data.meta.gentranslate.amount + `
                                        </label>
                                        <div class="col-sm-9">
                                            <div class="input-group">
                                                <input
                                                    type="number"
                                                    min="0"
                                                    max="`+ max_amount + `"
                                                    name="amount"
                                                    ng-model="amount"
                                                    style="z-index:30; border-width: 1px;"
                                                    class="form-control"
                                                    ng-class="{'codenerix_invalid': !amount}"
                                                    ng-required="true"
                                                    required
                                                    aria-invalid="true"
                                                    aria-describedby="id_amount_error"
                                                    id="id_amount">
                                                <div class="input-group-addon">`+ row.currency + `</div>
                                            </div>
                                        </div>
                                        <div class="row clearfix">
                                            <div class="col-sm-3"></div>
                                            <div class="col-sm-9 h6 text-primary text-left">
                                                ` + $scope.data.meta.gentranslate.max_refundable_amount + `: `+ max_amount + ` ` + row.currency+ `
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                </form>
                            </div>
                            <div class="col-md-2"></div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer ng-scope">
                    <button type="button" class="btn btn-sm btn-success" ng-disabled="!amount" ng-click="refund(amount)">
                        ` + $scope.data.meta.gentranslate.refund + `
                    </button>
                    <button type="button" class="btn btn-sm btn-danger" ng-click="close()">
                        ` + $scope.data.meta.gentranslate.cancel + `
                    </button>
                </div>`
            };

            var refund_ok = function(amount) {

                // Show success message
                $scope.refundmodal.html = `
                <div class="modal-header ng-scope">
                    <h3 class="modal-title text-center">` + title + `</h3>
                </div>
                <div class="row clearfix ng-scope">
                    <div class="modal-body">
                        <div class='modal-body text-center h4'>
                            <div class="row clearfix ng-scope">
                                <div class="col-md-12 text-success text-center">
                                    <img src='` + static_url + `codenerix/img/check_green.png'>
                                    &nbsp;
                                    ` + $scope.data.meta.gentranslate.refunded + `:
                                    ` + amount + " " + row.currency + `
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer ng-scope">
                    <button type="button" class="btn btn-sm btn-success" ng-click="close()">
                        ` + $scope.data.meta.gentranslate.close + `
                    </button>
                </div>`

                // Refresh parent and close
                $timeout(function() {
                    $scope.$parent.$parent.$parent.$parent.$parent.refresh();
                }, 2000);

            }

            var refund_error = function(response) {
                var html = `
                <div class="modal-header ng-scope">
                    <h3 class="modal-title text-center">` + title + `</h3>
                </div>
                <div class="row clearfix ng-scope">
                    <div class='modal-body text-center h4'>
                        <div class="row clearfix ng-scope">
                            <div class="col-md-1"></div>
                            <div class="col-md-1">
                                <img src='` + static_url + `codenerix/img/ko_red.png'>
                            </div>
                            <div class="col-md-1"></div>
                            <div class="col-md-8">
                                <table class="text-danger">
                                    <tr>
                                        <td align="right"><u>` + $scope.data.meta.gentranslate.error + `:</u></td>
                                        <td>&nbsp;</td>
                                        <td align="left">` + response.error+ `</td>
                                    </tr>
                                    <tr>
                                        <td align="right"><u>` + $scope.data.meta.gentranslate.errortxt + `:</u></td>
                                        <td>&nbsp;</td>
                                        <td align="left">` + response.errortxt+ `</td>
                                    </tr>
                                </table>
                            </div>
                            <div class="col-md-1"></div>
                        </div>
                    </div>
                </div>
                 <div class="modal-footer ng-scope">
                     <button type="button" class="btn btn-sm btn-danger" ng-click="close()">
                        ` + $scope.data.meta.gentranslate.close + `
                     </button>
                 </div>`
                $scope.refundmodal.html = html;
            }


            var refund_failure = function(msg) {
                var html = '<span class=\'text-danger\'><strong>' +
                    $scope.data.meta.gentranslate.error +
                    '</strong></span><br/>';
                html += '<img src=\'' + static_url + 'codenerix/img/warning.gif\'><br/>';
                html += '<button type="button" class="btn btn-sm btn-danger" ng-click="cancel()">' +
                    $scope.data.meta.gentranslate.close + '</button>';
                html += "<hr><h3>" + msg + "</h3>";
                $scope.refundmodal.html = html;
            }

            var functions = function(scope) {
                scope.refundmodal = $scope.refundmodal;
                scope.callback = callback;
                scope.closed = false;
                scope.refund = function(amount) {

                    // Refund request
                    Refund(returnurl).refund({locator:row.locator, amount: amount}, function(response) {
                        if (response.error === 0) {
                            refund_ok(amount);
                        } else {
                            refund_error(response);
                        }
                    }, function(error) {
                        refund_failure("Oppps, something went wrong!");
                    });

                }
                scope.close = function() {
                    scope.$dismiss('cancel');
                    if ((scope.callback != undefined) && !scope.closed) {
                        scope.closed = true
                        scope.callback();
                    }
                };
            };
            var callback = function(scope, answer) {};
            var callback_cancel = function(scope, answer) {
            };

            var modalInstance = openmodal(
                $scope,
                $timeout,
                $uibModal,
                'lm',
                functions,
                callback,
                false,
                callback_cancel,
                template
            );
        };
        $scope.submit_cancel = function(locator, cancelurl) {
            var url = cancelurl.replace("LOCATOR",locator);
            // console.log("Cancel payment "+locator+" jumping to "+url);
            window.open(url+'?autorender=1', '_blank');
            var refresh = function () {
                $scope.$parent.$parent.$parent.$parent.$parent.refresh();
            };
            $timeout(refresh, 2000);
        };
    }
]);
