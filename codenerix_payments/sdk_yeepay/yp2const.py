#!/usr/bin/env python
# coding=utf-8
# Created at 16/9/28

# YOP_BASE_URL = 'http://172.19.100.49:8064/yop-center'
# YOP_BASE_URL = 'https://open.yeepay.com/yop-center'
YOP_BASE_URL = 'http://10.151.30.88:8064/yop-center'

# YOP_MERCHANT_NO = '2'
YOP_APP_KEY = '#'
YOP_SECRET_KEY = '#'
YOP_SIGN_ALG = "sha256"
YOP_API_VERSION = "v1.0"
YOP_VERBOSE_LOG = True
YOP_ISV_PRIVATE_KEY = '#'
YOP_ALGORITHM = 'YOP-RSA2048-SHA256'
YOP_APP_KEY = 'app_5EmeGRJ7w73sL1Qa'
YOP_SECRET_KEY = 'KZrRTlJ88gSh+nfFIUMPLw=='

YOP_API_VERSION = "v3.0"
try:
    from local_settings.yp2const import *
except:
    pass

