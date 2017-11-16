'use strict';
codenerix_addlib('codenerixPaymentRequestControllers');
angular.module('codenerixPaymentRequestControllers', [])

.controller('codenerixPaymentRequestCtrl', ['$scope', '$timeout',
    function($scope, $timeout) {
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
