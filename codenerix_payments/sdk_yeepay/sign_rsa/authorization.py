# -*- coding: utf-8 -*-
# @title : 拼接需要的headers
# @Author : zhanglele
# @Date : 18/5/21
# @Desc :
import base64
import datetime
import hashlib
import json
import logging
import urllib
import uuid
from urllib.parse import quote, quote_plus

import oss2
import rsa

# import yop_security_utils as yop_security_utils
from .yop_security_utils import get_config, sign_rsa

_DEFAULT_LOGGER = None
DEFAULT_EXPIRATION_IN_SECONDS = '1800'
YOP_ALGORITHM = 'YOP-RSA2048-SHA256'


def get_iso8601_time():
    timestamp = datetime.datetime.utcnow().replace(microsecond=0)
    timestamp = timestamp.isoformat()
    timestamp = timestamp.replace('-','')
    timestamp = timestamp.replace(':','')
    timestamp += 'Z'
    return timestamp


def get_query_str(items,t1 = '=',t2 = '&'):
    sorted_items = sorted(items)
    param_str = str()
    i = 0
    for item in sorted_items:
        i += 1
        param_str += item[0]
        param_str += t1
        if(isinstance(item[1],str)):
            param_str += quote(str(item[1]),'utf-8')
        if i == len(sorted_items):
            break
        param_str += t2
    return param_str


def calculate_file_crc64(file_name, block_size=64 * 1024, init_crc=0):
    with open(file_name, 'rb') as f:
        crc64 = oss2.utils.Crc64(init_crc)
        while True:
            data = f.read(block_size)
            if not data:
                break
            crc64.update(data)

    return crc64.crc


def joint_canonical_request(url,query_dict=None,post='1',post_dict=None,headers=None,logger=None):
    protocol_version = 'yop-auth-v2'
    # app_key = yop_security_utils.get_config()['app_key']
    app_key = get_config()['app_key']
    yop_date = get_iso8601_time()
    expired_seconds = DEFAULT_EXPIRATION_IN_SECONDS
    if not headers:
        headers = {}
    if logger is None:
        logger = get_default_logger()
    query_str = get_query_str(post_dict.items())
    # get
    if not post:
        http_method = 'GET'
        if(query_dict):
            query_str = get_query_str(query_dict=query_dict)
    else:
        http_method = 'POST'
    url = url

    yop_request_id = uuid.uuid4()
    yop_app_key = app_key
    items = post_dict.items()
    param_str = get_query_str(items,t1='=',t2='&')
    post_dict_byte = param_str.encode('utf-8')
    canonical_header_str = 'x-yop-appkey' + ':' + quote(yop_app_key,'utf-8') + '\n' + 'x-yop-date' + ':' + quote(yop_date,'utf-8') + '\n' +  'x-yop-request-id' + ':' + quote(str(yop_request_id),'utf-8')
    signed_headers = 'x-yop-appkey;x-yop-date;x-yop-request-id'

    auth_str = protocol_version + '/' + app_key + '/' + yop_date + '/' + expired_seconds
    canonical_request = auth_str + '\n' + http_method + '\n' + url + '\n' + query_str + '\n' + canonical_header_str
    # signature = yop_security_utils.sign_rsa(canonical_request)
    signature = sign_rsa(canonical_request)

    authorization_header = YOP_ALGORITHM + ' ' + auth_str + '/' + signed_headers + '/' + str(signature,encoding='latin-1')
    headers = {}
    headers['authorization'] = authorization_header + '$SHA256'
    headers['x-yop-request-id'] = str(yop_request_id)
    headers['x-yop-date'] = yop_date
    headers['x-yop-appkey'] = yop_app_key
    return headers


def sign_rsa(content,privateKey):
    privatekey = rsa.PrivateKey.load_pkcs1(
        '-----BEGIN RSA PRIVATE KEY-----\n' + privateKey + '\n-----END RSA PRIVATE KEY-----')
    signature = rsa.sign(content.encode(), privatekey, 'SHA-256')
    sign_content = base64.urlsafe_b64encode(signature)
    return sign_content


def joint_canonical_request_json(url,query_dict=None,post = '1',post_dict=None,headers=None,logger=None):
    protocol_version = 'yop-auth-v2'
    # app_key = yop_security_utils.get_config()['app_key']
    app_key = get_config()['app_key']
    yop_date = get_iso8601_time()
    expired_seconds = DEFAULT_EXPIRATION_IN_SECONDS
    if not headers:
        headers = {}
    if logger is None:
        logger = get_default_logger()
    query_str = get_query_str(post_dict.items())
    # get
    if not post:
        http_method = 'GET'
        if(query_dict):
            query_str = get_query_str(query_dict=query_dict)
    else:
        http_method = 'POST'
        query_str = ''
    url = url

    yop_request_id = uuid.uuid4()
    yop_app_key = app_key

    s = hashlib.sha256()
    s.update(json.dumps(post_dict,sort_keys=True,indent =4,separators=(',', ': '),ensure_ascii=True).encode("latin-1"))
    yop_content_sha256 = s.hexdigest()

    canonical_header_str = 'x-yop-appkey' + ':' + quote(yop_app_key,'utf-8') + '\n' + 'x-yop-content-sha256:' + quote(yop_content_sha256,'utf-8') + '\n' + 'x-yop-date' + ':' + quote(yop_date,'utf-8') + '\n' +  'x-yop-request-id' + ':' + quote(str(yop_request_id),'utf-8')
    signed_headers = 'x-yop-appkey;x-yop-content-sha256;x-yop-date;x-yop-request-id'

    auth_str = protocol_version + '/' + app_key + '/' + yop_date + '/' + expired_seconds
    canonical_request = auth_str + '\n' + http_method + '\n' + url + '\n' + query_str + '\n' + canonical_header_str
    # signature = yop_security_utils.sign_rsa(canonical_request)
    signature = sign_rsa(canonical_request)

    authorization_header = YOP_ALGORITHM + ' ' + auth_str + '/' + signed_headers + '/' + str(signature,encoding='latin-1')
    headers = {}
    headers['authorization'] = authorization_header + '$SHA256'
    headers['x-yop-request-id'] = str(yop_request_id)
    headers['x-yop-content-sha256'] = yop_content_sha256
    headers['x-yop-date'] = yop_date
    headers['x-yop-appkey'] = yop_app_key
    return headers


def joint_canonical_request_file(url,query_dict=None,post='1',post_dict=None,headers=None,logger=None):
    protocol_version = 'yop-auth-v2'
    # app_key = yop_security_utils.get_config()['app_key']
    app_key = get_config()['app_key']
    yop_date = get_iso8601_time()
    expired_seconds = DEFAULT_EXPIRATION_IN_SECONDS
    if not headers:
        headers = {}
    if logger is None:
        logger = get_default_logger()

    files = post_dict['_file'].split(';')
    crc64ecma = str()
    i = 0
    for f in files:
        i += 1
        crc64ecma += str(calculate_file_crc64(f))
        if(i == len(files)):
            break
        crc64ecma += '/'
    if '_file' in post_dict:
        del post_dict['_file']
    query_str = get_query_str(post_dict.items())
    # get
    if not post:
        http_method = 'GET'
        if(query_dict):
            query_str = get_query_str(query_dict=query_dict)
    else:
        http_method = 'POST'
    url = url

    yop_request_id = uuid.uuid4()
    yop_app_key = app_key


    items = post_dict.items()
    param_str = get_query_str(items,t1='=',t2='&')
    canonical_header_str = 'x-yop-appkey' + ':' + quote(yop_app_key,'utf-8') + '\n' + 'x-yop-date' + ':' + quote(yop_date,'utf-8') + '\n' + 'x-yop-hash-crc64ecma:' + quote(crc64ecma,'utf-8') + '\n' + 'x-yop-request-id' + ':' + quote(str(yop_request_id),'utf-8')
    signed_headers = 'x-yop-appkey;x-yop-date;x-yop-hash-crc64ecma;x-yop-request-id'

    auth_str = protocol_version + '/' + app_key + '/' + yop_date + '/' + expired_seconds
    canonical_request = auth_str + '\n' + http_method + '\n' + url + '\n' + query_str + '\n' + canonical_header_str
    # signature = yop_security_utils.sign_rsa(canonical_request)
    signature = sign_rsa(canonical_request)

    authorization_header = YOP_ALGORITHM + ' ' + auth_str + '/' + signed_headers + '/' + str(signature,encoding='latin-1')
    headers = {}
    headers['authorization'] = authorization_header + '$SHA256'
    headers['x-yop-request-id'] = str(yop_request_id)
    headers['x-yop-date'] = yop_date
    headers['x-yop-hash-crc64ecma'] = crc64ecma
    headers['x-yop-appkey'] = yop_app_key
    return headers

def combine_url(url, query_dict):
    if not query_dict:
        return url
    if isinstance(query_dict, dict):
        # query_dict = urllib.urlencode(query_dict)
        query_dict = urllib.parse.urlencode(query_dict)
    return url + '?' + query_dict


def handle_request(query_dict):
    if isinstance(query_dict, dict):
        # query_dict = urllib.urlencode(query_dict)
        query_dict = urllib.parse.urlencode(query_dict)
    return query_dict


def get_default_logger():
    global _DEFAULT_LOGGER
    if _DEFAULT_LOGGER is None:
        logger = logging.getLogger('_yeepay2_default_')
        if len(logger.handlers) == 0:
            hdl = logging.StreamHandler()
            hdl.setFormatter(logging.Formatter(
                '%(levelname)s %(asctime)s %(thread)d %(message)s'))
            hdl.setLevel(logging.DEBUG)
            logger.addHandler(hdl)
            logger.setLevel(logging.DEBUG)
        _DEFAULT_LOGGER = logger
    return _DEFAULT_LOGGER
