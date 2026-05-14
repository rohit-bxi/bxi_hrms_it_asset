from odoo import http
from odoo.http import request

import os
import json
import base64
import random
import string
import requests
import logging

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad

from cryptography import x509
from cryptography.hazmat.primitives import serialization


_logger = logging.getLogger(__name__)


class ICICITestController(http.Controller):

    def random_16(self):
        return ''.join(random.choices(string.digits, k=16))

    @http.route(
        '/icici/test',
        type='json',
        auth='public',
        csrf=False,
        methods=['POST']
    )
    def test_icici(self):

        try:
            module_path = os.path.dirname(
                os.path.dirname(__file__)
            )
            cert_path = os.path.join(
                module_path,
                'icici_public.pem'
            )

            _logger.info("CERT PATH: %s", cert_path)

            with open(cert_path, "rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data)

            public_key = cert.public_key()

            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            rsa_key = RSA.import_key(pem)

            payload = {
                "AGGRID": "CIBBULK001",
                "AGGRNAME": "BULKTESTING",
                "CORPID": "TXBCORP2",
                "USERID": "USER2",
                "URN": "CIBTESTING",
                "UNIQUEID": "11115"
            }

            json_data = json.dumps(payload)

            _logger.info("ORIGINAL PAYLOAD: %s", json_data)

            randomno1 = self.random_16()

            _logger.info("AES KEY GENERATED")

            cipher_rsa = PKCS1_v1_5.new(rsa_key)

            encrypted_key = cipher_rsa.encrypt(
                randomno1.encode()
            )

            encr_key_b64 = base64.b64encode(
                encrypted_key
            ).decode()

            randomno2 = self.random_16()

            data = randomno2 + json_data

            cipher_aes = AES.new(
                randomno1.encode(),
                AES.MODE_CBC,
                iv=randomno2.encode()
            )

            encrypted_data = cipher_aes.encrypt(
                pad(data.encode(), AES.block_size)
            )

            encr_data_b64 = base64.b64encode(
                encrypted_data
            ).decode()

            request_payload = {
                "requestId": "",
                "service": "",
                "encryptedKey": encr_key_b64,
                "oaepHashingAlgorithm": "NONE",
                "iv": "",
                "encryptedData": encr_data_b64,
                "clientInfo": "",
                "optionalParam": ""
            }

            _logger.info("REQUEST PAYLOAD CREATED")

            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "apikey": "HLAo88SpqGCpnwW87KcdwElPsfhPGVyG"
            }

            url = "https://apibankingonesandbox.icici.bank.in/api/Corporate/CIB_SV/v1/Create"

            _logger.info("HITTING ICICI API")

            response = requests.post(
                url,
                headers=headers,
                json=request_payload,
                timeout=60
            )

            _logger.info("STATUS CODE: %s", response.status_code)
            _logger.info("RESPONSE TEXT: %s", response.text)

            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.text
            }

        except Exception as e:

            _logger.exception("ICICI API ERROR")

            return {
                "success": False,
                "error": str(e)
            }