'use strict';
codenerix_addlib('codenerixPaymentRequestControllers');
angular.module('codenerixPaymentRequestControllers', [])

.controller('codenerixPaymentRequestCtrl', ['$scope',
    function($scope) {
        $scope.submit_approval = function(pk, apr) {
            if (apr.form) {
                console.log("Redsys");
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
                console.log("Paypal");
                window.open(apr.url);
            }
        };
    }
]);
