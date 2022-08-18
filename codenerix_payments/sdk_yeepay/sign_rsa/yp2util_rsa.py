#!/usr/bin/env python
# Created at 16/9/28

import base64
import hashlib
import json
import locale
import logging
import platform
import time
import urllib
import urllib.request as urllib2
from urllib.parse import quote

import simplejson as sj
from sign_rsa.encode import multipart_encode,MultipartParam

from sign_rsa.streaminghttp import register_openers

import sign_rsa.authorization as authorization

_DEFAULT_LOGGER = None
SDK_VERSION = '3.1.1'
import yop_security_utils
PAD_LEN = 16
padding = lambda s: s + (PAD_LEN - len(s) % PAD_LEN) \
                        * chr(PAD_LEN - len(s) % PAD_LEN)
unpadding = lambda s: s[:-ord(s[-1])] if len(s) else s
dict_encoding = lambda dct, enc='utf-8': \
    dict((k, v.encode(enc) if isinstance(v, unicode) else v)
         for k, v in dct.iteritems())
utf8_to_gbk = lambda v: v.decode('utf-8').encode('gbk') if v else ''
decode_gbk = lambda v: urllib.unquote_plus(v).decode('gbk').encode('utf-8') if v else ''


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

def combine_url(url, query_dict):
    if not query_dict:
        return url
    if isinstance(query_dict, dict):
        query_dict = urllib.urlencode(query_dict)
    return url + '?' + query_dict


def http_request(
        url, query_dict=None, post=1, post_dict=None,
        headers=None, timeout=40, verbose=True,
        tryn=1, retry_sleep=2, logger=None, **kwargs):
    t1 = time.time()
    if post and not post_dict:
        post_dict = query_dict if query_dict else ''
        query_dict = None
    if not headers:
        headers = {}
    if logger is None:
        logger = get_default_logger()

    try:
        if not post and not headers:
            _request = combine_url(url=url, query_dict=query_dict)

        else:
            url = combine_url(url=url, query_dict=query_dict)
            if post == 2:
                register_openers()

                post_content = []
                for content in post_dict:
                    if content == '_file':
                        files = post_dict['_file'].split(';')
                        for f in files:
                            post_content.append(MultipartParam.from_file('_file',f))
                    else:
                        post_content.append(MultipartParam(content,post_dict[content]))
                datagen, _h = multipart_encode(post_content)
                headers['content-length'] = _h['Content-Length']
                headers['content-type'] = _h['Content-Type']
            elif post == 3:
                headers['content-type']='application/json'
                datagen = json.dumps(post_dict,sort_keys=True,indent =4,separators=(',', ': '),ensure_ascii=True).encode("latin-1")
                url = combine_url(url=url, query_dict=query_dict)
            else:
                datagen = urllib.parse.urlencode(post_dict).encode(encoding='UTF8') \
                    if post_dict else ''
            _request = urllib2.Request(url, datagen)
            for k, v in headers.items():
                _request.add_header(k, v)
        request = urllib2.urlopen(_request, timeout=timeout)
        data = request.read()
        request.close()
        t2 = time.time()
        if verbose:
            logger.debug('yeepay2_req url=%s,qd=%s,time=%s',
                         url, query_dict, t2 - t1)
        return data
    except Exception as e:
        rcode = e.code if hasattr(e, 'code') else '?'
        rfp = e.fp if hasattr(e, 'fp') else '?'
        qdstr = str(query_dict)
        if qdstr and len(qdstr) >= 500:
            qdstr = qdstr[:500]
        logger.exception('err=%s,code=%s,fp=%s,url=%s,post=%d,q=%s,h=%s',
                         e, rcode, rfp, url, post, qdstr, headers)
        if tryn > 1:
            time.sleep(retry_sleep)
            return http_request(
                url=url, query_dict=query_dict, post=post,
                headers=headers, timeout=timeout, tryn=tryn - 1,
                retry_sleep=retry_sleep, logger=logger, **kwargs)
        return None


def get_user_agent():
    user_agent = 'python/'
    user_agent = user_agent + SDK_VERSION + '/'
    user_agent = user_agent + platform.system() + '/'
    user_agent = user_agent + platform.platform().split("-")[1] + '/'
    user_agent = user_agent + platform.python_compiler() + '/'
    user_agent = user_agent + platform.python_compiler().split(' ')[1] + '/'
    user_agent = user_agent + platform.python_version()
    # locale_info = locale.getdefaultlocale()[0]
    # language = ''
    # address = ''
    # if locale_info and len(locale_info.split('_')) == 2:
    #     language = locale_info.split('_')[0]
    #     address = locale_info.split('_')[1]
    # user_agent = user_agent + '/' + language + '/' + address
    # user_agent = user_agent.replace(' ', '_')
    return user_agent


def restful_upload(api, params={}, logger=None, verbose=False):
    if not logger:
        logger = get_default_logger()
    url = ''.join([yop_security_utils.get_config()['server_root'], api])
    if not params:
        params = {}
    params['appKey'] = yop_security_utils.get_config()['app_key']
    params['v'] = api.split('/')[2][1:]
    params['method'] = api
    params['ts'] = str(int(round(time.time() * 1000)))
    params['locale'] = 'zh_CN'

    f = str(params['_file'])
    f_list = f.split(';')
    f_list.sort()
    params['_file'] = ';'.join(f_list)
    f = params['_file']
    headers = authorization.joint_canonical_request_file(url=api, post_dict=params)
    headers['user-agent'] = get_user_agent()

    for item in params:
        params[item] = quote(params[item])
    params['_file'] = f
    data = http_request(url, post_dict=params, logger=logger,headers=headers,post=2)
    if verbose:
        logger.debug('api=%s \nparams=%s \ndata=%s', api, params, data)
    try:
        json = sj.loads(data)
        ret = json.get('result', json.get('error', {}))
        return ret, ret.get('code', '-1') if json else '-1'
    except Exception as e:
        logger.exception('err=%s data=%s', e, data)
        return None, '-1'


def restful_param(api, params={},logger=None, verbose=False):
    if not logger:
        logger = get_default_logger()
    url = ''.join([yop_security_utils.get_config()['server_root'], api])
    if not params:
        params = {}
    params['appKey'] = yop_security_utils.get_config()['app_key']
    params['v'] = api.split('/')[2][1:]
    params['method'] = api
    params['ts'] = str(int(round(time.time() * 1000)))
    params['locale'] = 'zh_CN'

    headers = authorization.joint_canonical_request(url=api, post_dict=params,post=1)
    headers['user-agent'] = get_user_agent()
    for item in params:
        params[item] = quote(params[item])

    data = http_request(url, post_dict=params, logger=logger,headers=headers,post=1)
    if verbose:
        logger.debug('api=%s \nparams=%s \ndata=%s', api, params, data)
    try:
        json = sj.loads(data)
        ret = json.get('result', json.get('error', {}))
        return ret, ret.get('code', '-1') if json else '-1'
    except Exception as e:
        logger.exception('err=%s data=%s', e, data)
        return None, '-1'


def restful_json(api, params={}, logger=None, verbose=True):
    if not logger:
        logger = get_default_logger()
    url = ''.join([yop_security_utils.get_config()['server_root'], api])
    if not params:
        params = {}
    params['appKey'] = yop_security_utils.get_config()['app_key']
    params['v'] = api.split('/')[2][1:]
    params['method'] = api
    params['ts'] = str(int(round(time.time() * 1000)))
    params['locale'] = 'zh_CN'

    headers = authorization.joint_canonical_request_json(url=api, post_dict=params)
    headers['user-agent'] = get_user_agent()

    data = http_request(url, post_dict=params, logger=logger,headers=headers,post=3)
    if verbose:
        logger.debug('api=%s \nparams=%s \ndata=%s', api, params, data)
    try:
        json = sj.loads(data)
        ret = json.get('result', json.get('error', {}))
        return ret, ret.get('code', '-1') if json else '-1'
    except Exception as e:
        logger.exception('err=%s data=%s', e, data)
        return None, '-1'





