# yop-python-sdk


````
import yp2util
import yp2const

def reset_passwd_url(ouid, webCallBackUrl, returnUrl, logger=None):
    api = 'user/getPswdResetUrl'
    params = {'merchantUserId': ouid,
              'webCallBackUrl': webCallBackUrl,
              'returnUrl': returnUrl,
              }
    return yp2util.restful(api, params=params, logger=logger)
````

//非对称
//上传文件（多文件以';'分割）
import sign_rsa.yp2util_rsa as yp2util_rsa
import yp2util

api = 'file/upload'
params = {
            "fileType":"file",
            "_file": "sign_rsa/test_file.txt;/Users/yp-tc-m-2757/yeepay/11.jpg",
}
yp2util_rsa.restful_upload(api=api, params=params)

//非对称
//普通参数
api = 'auth/idcard'
params = {
            'request_flow_id':'123',
            'name':'dd',
            'id_card_number':'371111190406124366'
}
yp2util_rsa.restful_param(api=api,params=params)


# 普通参数测试-非对称（参数中有json格式）
# api = 'std/trade/order'
# params = {
#             'orderId':'1ss676',
#             'goodsParamExt':'{"goodsDesc":"arara","goodsName":"法人"}',
#             'orderAmount':'898.00',
#             'notifyUrl': 'http://apitest.jiyuxxxu.cn/pay/yee/xxxx',
#             'parentMerchantNo':'10000469938',
#             'merchantNo':'10000463938'
# }
# yp2util_rsa.restful_param(api=api,params=params)


# json传参测试-非对称
api = 'test/token/generate-token'
params = {
    'arg0': 'password',
    'arg1': 'arg1',
    'arg2': 'arg2',
    'arg3': 'arg3',
    'arg4': 'arg4',
    'arg5': 'arg5'
}
yp2util_rsa.restful_json(api=api,params=params)