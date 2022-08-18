# -*- coding: utf-8 -*-
# @title : 封装数字信封、拆开数字信封、签名、验签的工具类
# @Author : zhanglele
# @Date : 18/6/14
# @Desc :
import base64
import os

import simplejson as sj
import hashlib
import rsa


# 摘要算法，默认为sha256(参照配置文件)
from Crypto import Random
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Crypto.Cipher import AES

import logging
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AES根据16位对齐
BS = 16

# 伪随机数生成器
random_generator = Random.new().read

# 非对称签名
def sign_rsa(content, private_key=None, alg_name=SHA256):
    if not private_key:
        private_key = get_config()['isv_private_key'][0]['value']
    private_key = '-----BEGIN PRIVATE KEY-----\n' +private_key + '\n-----END PRIVATE KEY-----'
    key = RSA.importKey(private_key)
    h = SHA256.new(content.encode('latin-1'))
    signer = PKCS1_v1_5.new(key)
    signature = signer.sign(h)
    return encode_base64(signature)


# 非对称验签
def verify_rsa(content, signature, public_key=None,alg_name=SHA256):
    if not public_key:
        public_key = get_config()['yop_public_key'][0]['value']
    public_key = RSA.importKey('-----BEGIN PUBLIC KEY-----\n'+public_key+ '\n-----END PUBLIC KEY-----')
    h = SHA256.new(bytes(content, encoding='latin-1'))
    verifier = PKCS1_v1_5.new(public_key)
    signature = signature.rstrip('')
    if verifier.verify(h, decode_base64(signature)):
        return True
    return False


# 对称签名
def sign(content,secret=None,alg_name='sha256'):
    if not secret:
        secret = get_config()['aes_secret_key']
    strings = [secret]
    strings.append(content)
    strings.append(secret)
    __alg_func = getattr(hashlib, alg_name)
    signature = __alg_func(''.join(strings)).hexdigest()
    return signature


# 对称验签
def verify(content,signature,secret=None,alg_name='sha256'):
    if not secret:
        secret = get_config()['aes_secret_key']
    strings = [secret]
    strings.append(content)
    strings.append(secret)
    __alg_func = getattr(hashlib, alg_name)
    verify = __alg_func(''.join(strings)).hexdigest()
    return verify == signature


# 封装数字信封
def encrypt(content,private_key=None,public_key=None,alg_name=SHA256):
    if not public_key:
        public_key = get_config()['yop_public_key'][0]['value']
    if not private_key:
        private_key = get_config()['isv_private_key'][0]['value']
    # 生成随机密钥
    random_key = get_random_key_readable(16)
    random_key = '2ivwOb8rRQkQx3v3'
    # 对数据进行签名
    sign_to_base64 = sign_rsa(content,private_key,alg_name)

    # 用随机密钥对数据和签名进行加密
    cipher = AES.new(random_key, AES.MODE_ECB)
    encrypted_data_to_base64 = cipher.encrypt(base64.urlsafe_b64encode(content + '$' + decode_base64(sign_to_base64)))
    encrypted_data_to_base64 = base64.urlsafe_b64encode(encrypted_data_to_base64)
    # 对密钥加密
    public_key = RSA.importKey('-----BEGIN PUBLIC KEY-----\n'+ public_key + '\n-----END PUBLIC KEY-----')
    cipher = Cipher_pkcs1_v1_5.new(public_key)
    encrypted_random_key_to_base64 = base64.urlsafe_b64encode(cipher.encrypt(random_key))
    cigher_text = [encrypted_random_key_to_base64]
    cigher_text.append(encrypted_data_to_base64)
    cigher_text.append('AES')
    cigher_text.append('SHA256')
    return '$'.join(cigher_text)

# 拆开数字信封
def decrypt(content,private_key=None,public_key=None,alg_name=SHA256):
    if not public_key:
        public_key = get_config()['yop_public_key'][0]['value']
    if not private_key:
        private_key = get_config()['isv_private_key'][0]['value']
    args = content.split('$')
    if len(args) != 4:
        raise Exception("source invalid", args)
    # 分解参数
    encrypted_random_key_to_base64 = args[0]
    encrypted_date_to_base64 = args[1]
    symmetric_encrypt_alg = args[2]
    digest_alg = args[3]

    # 用私钥对随机密钥进行解密
    private_key = '-----BEGIN PRIVATE KEY-----\n' +private_key + '\n-----END PRIVATE KEY-----'
    rsakey = RSA.importKey(private_key)
    cipher = Cipher_pkcs1_v1_5.new(rsakey)
    random_key = cipher.decrypt(decode_base64(encrypted_random_key_to_base64),random_generator)

    cipher = AES.new(random_key, AES.MODE_ECB)
    encryped_data = cipher.decrypt(decode_base64(encrypted_date_to_base64))
    # 分解参数
    # encryped_data = decode_base64(encryped_data)
    data = str(encryped_data, encoding='latin-1').split('$')
    source_data = data[0]
    sign_to_base64 = data[1]

    verify_sign = verify_rsa(source_data,sign_to_base64,public_key,digest_alg)
    if not verify_sign:
        raise Exception("verifySign fail!")
    return source_data


# 生成随机密钥
def get_random_key_readable(key_size=16):
    ulen = int(key_size/4*3)
    key = base64.b64encode(os.urandom(ulen))
    return key


# base64解码
def decode_base64(data):
    missing_padding = 4-len(data) % 4
    if missing_padding:
        data += '='*3
    return base64.urlsafe_b64decode(data)


def encode_base64(data):
    data = base64.urlsafe_b64encode(data)
    for i in range(3):
        if data.endswith('='.encode('latin-1')):
            data = data[:-1]
    return data



# 获取配置文件信息
def get_config():
    with open("yop_sdk_config_default.json", 'r') as load_f:
        load_dict = sj.load(load_f)
        return load_dict
