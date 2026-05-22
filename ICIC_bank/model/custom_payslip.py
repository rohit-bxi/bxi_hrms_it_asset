from odoo import models, fields
from odoo.exceptions import ValidationError

import os
import json
import base64
import random
import string
import logging
import requests

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad

from cryptography import x509
from cryptography.hazmat.primitives import serialization


_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    icici_payment_status = fields.Selection([
        ('draft', 'Draft'),
        ('otp_pending', 'OTP Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed')
    ], default='draft')

    icici_response = fields.Text()

    icici_reference = fields.Char()

    icici_file_seq_num = fields.Char()

    def random_16(self):

        return ''.join(
            random.choices(
                string.digits,
                k=16
            )
        )

    def get_icici_public_key(self):

        module_path = os.path.dirname(
            os.path.dirname(__file__)
        )

        cert_path = os.path.join(
            module_path,
            'icici_public.pem'
        )

        with open(cert_path, 'rb') as f:

            cert_data = f.read()

        cert = x509.load_pem_x509_certificate(
            cert_data
        )

        public_key = cert.public_key()

        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return RSA.import_key(pem)

    def encrypt_payload(self, payload):

        rsa_key = self.get_icici_public_key()

        json_data = json.dumps(payload)

        randomno1 = self.random_16()

        cipher_rsa = PKCS1_v1_5.new(
            rsa_key
        )

        encrypted_key = cipher_rsa.encrypt(
            randomno1.encode()
        )

        encr_key_b64 = base64.b64encode(
            encrypted_key
        ).decode()

        # RANDOM IV
        randomno2 = self.random_16()

        data = randomno2 + json_data

        cipher_aes = AES.new(
            randomno1.encode(),
            AES.MODE_CBC,
            iv=randomno2.encode()
        )

        encrypted_data = cipher_aes.encrypt(
            pad(
                data.encode(),
                AES.block_size
            )
        )

        # PREPEND IV
        final_encrypted_data = (
            randomno2.encode() +
            encrypted_data
        )

        encr_data_b64 = base64.b64encode(
            final_encrypted_data
        ).decode()

        return {
            'requestId': '',
            'service': 'CIB',
            'encryptedKey': encr_key_b64,
            'oaepHashingAlgorithm': 'NONE',
            'iv': '',
            'encryptedData': encr_data_b64,
            'clientInfo': '',
            'optionalParam': ''
        }

    def call_icici_api(
        self,
        url,
        payload
    ):

        encrypted_payload = self.encrypt_payload(
            payload
        )

        headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'apikey': 'HLAo88SpqGCpnwW87KcdwElPsfhPGVyG'
        }

        try:

            response = requests.post(
                url,
                headers=headers,
                json=encrypted_payload,
                timeout=60,
                verify=True
            )

            response.raise_for_status()

            _logger.info(
                'ICICI RAW RESPONSE: %s',
                response.text
            )

            response_json = response.json()

            decrypted_response = self.decrypt_response(
                response_json
            )

            _logger.info(
                'ICICI DECRYPTED RESPONSE: %s',
                decrypted_response
            )

            return {
                'status_code': response.status_code,
                'response': decrypted_response
            }

        except Exception as e:

            _logger.exception(
                'ICICI API ERROR'
            )

            return {
                'status_code': 500,
                'response': str(e)
            }
        
    def action_release_salary(self):

        self.ensure_one()

        if self.icici_payment_status == 'paid':

            raise ValidationError(
                'Salary already released.'
            )

        if self.state != 'validated':

            raise ValidationError(
                'Payslip must be confirmed.'
            )

        employee = self.employee_id

        bank_account_rec = employee.bank_account_ids[:1]

        if not bank_account_rec:

            raise ValidationError(
                'Employee bank account missing.'
            )

        bank_account = bank_account_rec.acc_number

        if not bank_account:

            raise ValidationError(
                'Employee bank account missing.'
            )

        amount = self.net_wage

        if amount <= 0:

            raise ValidationError(
                'Invalid salary amount.'
            )

        payload = {
            'AGGRID': 'CIBBULK001',
            'AGGRNAME': 'BULKTESTING',
            'CORPID': 'TXBCORP2',
            'USERID': 'USER2',
            'URN': 'CIBTESTING',
            'UNIQUEID': str(self.id)
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/Corporate/CIB_SV/v1/Create'
        )

        result = self.call_icici_api(
            url,
            payload
        )

        self.icici_response = result.get(
            'response'
        )

        self.icici_payment_status = (
            'otp_pending'
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter OTP',
            'res_model': 'icici.otp.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_id': self.id,
            }
        }

    def decrypt_response(self, response_data):

        try:

            encrypted_key = response_data.get(
                'encryptedKey'
            )

            encrypted_data = response_data.get(
                'encryptedData'
            )

            module_path = os.path.dirname(
                os.path.dirname(__file__)
            )

            private_key_path = os.path.join(
                module_path,
                'private_key.pem'
            )

            with open(private_key_path, 'rb') as f:

                private_key = RSA.import_key(
                    f.read()
                )

            encrypted_key_bytes = (
                base64.b64decode(
                    encrypted_key
                )
            )

            _logger.info(
                'Encrypted key length: %s',
                len(encrypted_key_bytes)
            )

            cipher_rsa = PKCS1_v1_5.new(
                private_key
            )

            aes_key = cipher_rsa.decrypt(
                encrypted_key_bytes,
                b'ERROR'
            )

            if aes_key == b'ERROR':

                raise ValidationError(
                    'AES key decryption failed'
                )

            encrypted_data_bytes = (
                base64.b64decode(
                    encrypted_data
                )
            )

            iv = encrypted_data_bytes[:16]

            encrypted_payload = (
                encrypted_data_bytes[16:]
            )

            cipher_aes = AES.new(
                aes_key,
                AES.MODE_CBC,
                iv=iv
            )

            decrypted = cipher_aes.decrypt(
                encrypted_payload
            )

            decrypted = unpad(
                decrypted,
                AES.block_size
            )

            final_response = decrypted[16:]

            return final_response.decode(
                'utf-8',
                errors='ignore'
            )

        except Exception as e:

            _logger.exception(
                'ICICI RESPONSE DECRYPTION ERROR'
            )

            return str(e)