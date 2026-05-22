from odoo import models, fields
from odoo.exceptions import ValidationError

import os
import json
import base64
import random
import string
import logging
import requests

from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Util.Padding import pad, unpad


_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    icici_payment_status = fields.Selection([
        ('draft', 'Draft'),
        ('otp_pending', 'OTP Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed')
    ], default='draft')

    icici_reference = fields.Char()
    icici_file_seq_num = fields.Char()
    icici_response = fields.Text()
    icici_generated_otp = fields.Char()

    def random_16(self):

        return ''.join(
            random.choices(
                string.digits,
                k=16
            )
        )

    def get_icici_public_key(self):
        module_path = os.path.dirname(__file__)
        public_key_path = os.path.join(
            module_path,
            '..',
            'icici_public.pem'
        )
        with open(public_key_path, 'rb') as f:
            key_data = f.read()
        return RSA.import_key(key_data)

    def get_private_key(self):

        module_path = os.path.dirname(__file__)
        private_key_path = os.path.join(
            module_path,
            '..',
            'private_key.pem'
        )
        with open(private_key_path, 'rb') as f:
            key_data = f.read()
        return RSA.import_key(key_data)

    def encrypt_payload(self, payload):

        rsa_key = self.get_icici_public_key()

        json_data = json.dumps(
            payload,
            separators=(',', ':')
        )

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

        encr_data_b64 = base64.b64encode(
            encrypted_data
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

    def decrypt_response(self, response_data):
        encrypted_key = response_data.get(
            'encryptedKey'
        )
        encrypted_data = response_data.get(
            'encryptedData'
        )
        private_key = self.get_private_key()
        encrypted_key_bytes = base64.b64decode(
            encrypted_key
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
            None
        )
        encrypted_data_bytes = base64.b64decode(
            encrypted_data
        )
        iv = encrypted_data_bytes[:16]
        cipher_aes = AES.new(
            aes_key,
            AES.MODE_CBC,
            iv=iv
        )
        try:
            decrypted = unpad(
                cipher_aes.decrypt(
                    encrypted_data_bytes
                ),
                AES.block_size
            )
        except Exception:
            raise ValidationError(
                'ICICI decryption failed.'
            )
        final_response = decrypted[16:]
        return final_response.decode()
    
    def call_icici_api(self, url, payload):
        try:
            encrypted_payload = self.encrypt_payload(
                payload
            )
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'APIKEY': 'HLAo88SpqGCpnwW87KcdwElPsfhPGVyG'
            }
            _logger.info(
                'ICICI REQUEST PAYLOAD: %s',
                encrypted_payload
            )
            response = requests.post(
                url,
                headers=headers,
                json=encrypted_payload,
                timeout=60
            )
            _logger.info(
                'ICICI STATUS CODE: %s',
                response.status_code
            )

            _logger.info(
                'ICICI RESPONSE TEXT: %s',
                response.text
            )

            response.raise_for_status()
            try:
                json_start = response.text.find('{')
                json_end = response.text.rfind('}') + 1
                clean_response = response.text[
                    json_start:json_end
                ]
                response_json = json.loads(
                    clean_response
                )
            except Exception:
                raise ValidationError(
                    f'Invalid ICICI response:\n\n{response}'
                )
            decrypted_response = (
                self.decrypt_response(
                    response_json
                )
            )
            _logger.info(
                'ICICI DECRYPTED RESPONSE: %s',
                decrypted_response
            )

            return {
                'success': True,
                'status_code': response.status_code,
                'response': decrypted_response
            }

        except Exception as e:

            _logger.exception(
                'ICICI API ERROR'
            )

            return {
            'success': False,
            'status_code': getattr(
                response,
                'status_code',
                500
            ),
            'response': str(e)
        }
        
    def action_release_salary(self):

        if not self:

            raise ValidationError(
                'No payslips selected.'
            )

        for slip in self:

            if slip.icici_payment_status == 'paid':

                raise ValidationError(
                    f'Salary already released for {slip.employee_id.name}'
                )

            if slip.state in ['draft', 'cancel']:

                raise ValidationError(
                    f'{slip.employee_id.name} payslip is not confirmed.'
                )

        create_payload = {
            "AGGRID": "CIBBULK001",
            "AGGRNAME": "BULKTESTING",
            "CORPID": "TXBCORP2",
            "USERID": "USER2",
            "URN": "CIBTESTING",
            "UNIQUEID": str(random.randint(10000, 99999))
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/Corporate/CIB_SV/v1/Create'
        )

        result = self[0].call_icici_api(
            url,
            create_payload
        )

        response = result.get(
            'response'
        )

        try:

            json_start = response.find('{')

            json_end = response.rfind('}') + 1

            clean_response = response[
                json_start:json_end
            ]

            response_json = json.loads(
                clean_response
            )

        except Exception:

            raise ValidationError(
                f'Invalid ICICI response:\n\n{response}'
            )

        otp = response_json.get('OTP')

        if not otp:

            raise ValidationError(
                response
            )

        self.write({
            'icici_generated_otp': otp
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'icici.otp.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_ids': self.ids
            }
        }
    
    def process_bulk_payment(self, otp):
        if not self:
            raise ValidationError(
                'No payslips selected.'
            )
        total_amount = 0
        salary_lines = []
        for slip in self:
            if slip.icici_payment_status == 'paid':
                raise ValidationError(
                    f'Salary already released for {slip.employee_id.name}'
                )
            employee = slip.employee_id
            bank_account_rec = (
                employee.bank_account_ids.filtered(
                    lambda b: b.acc_number
                )[:1]
            )
            if not bank_account_rec:
                raise ValidationError(
                    f'Bank account missing for {employee.name}'
                )
            bank_account = (
                bank_account_rec.acc_number
            )
            if not bank_account:
                raise ValidationError(
                    f'Account number missing for {employee.name}'
                )
            amount = int(slip.net_wage)
            if amount <= 0:
                raise ValidationError(
                    f'Invalid salary amount for {employee.name}'
                )
            total_amount += amount

        from datetime import datetime

        today_date = datetime.today().strftime(
            '%d/%m/%Y'
        )
        salary_lines.append(
            f'FHR|7|{today_date}|salarybatch|{total_amount}|INR|000451000301|0011^'
        )
        salary_lines.append(
            f'MDR|000451000301|0011|salary|{total_amount}|INR|salary|ICIC0000011|WIB^'
        )
        for slip in self:
            employee = slip.employee_id
            bank_account = (
                employee.bank_account_ids[:1].acc_number
            )
            amount = int(slip.net_wage)
            salary_lines.append(
                f'MCW|{bank_account}|0411|{employee.name}|{amount}|INR|Salary|ICIC0000011|WIB^'
            )

        salary_file = '\n'.join(
            salary_lines
        )

        encoded_file = base64.b64encode(
            salary_file.encode()
        ).decode()

        payload = {
            "FILE_DESCRIPTION": "PAYROLL",
            "AGGR_ID": "CIBBULK001",
            "URN": "CIBTESTING",
            "AGGR_NAME": "BULKTESTING",
            "USER_ID": "USER2",
            "CORP_ID": "TXBCORP2",
            "UNIQUE_ID": str(random.randint(10000, 99999)),
            "AGOTP": otp,
            "FILE_NAME": f"salary_batch_{datetime.today().strftime('%Y%m%d%H%M%S')}.txt",
            "FILE_CONTENT": encoded_file
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/v1/cibbulkpayment_sv/bulkPayment'
        )

        result = self[0].call_icici_api(
            url,
            payload
        )

        response = result.get(
            'response'
        )
        if result.get('status_code') != 200:

            self.write({
                'icici_payment_status': 'failed',
                'icici_response': response
            })

            raise ValidationError(
                response
            )
        try:
            json_start = response.find('{')

            json_end = response.rfind('}') + 1

            clean_response = response[
                json_start:json_end
            ]

            response_json = json.loads(
                clean_response
            )

        except Exception:

            raise ValidationError(
                f'Invalid ICICI response:\n\n{response}'
        )

        response_code = response_json.get(
            'ResponseCode'
        )

        if response_code == '0000':
            file_seq_num = response_json.get(
                'FILESEQNUM'
            )
            utr = response_json.get(
                'UTR'
            )
            self.write({
                'icici_payment_status': 'processing',
                'icici_response': response,
                'icici_file_seq_num': file_seq_num,
                'icici_reference': utr,
                'icici_generated_otp': False
            })

        else:

            self.write({
                'icici_payment_status': 'failed',
                'icici_response': response
            })

            raise ValidationError(
                response_json.get(
                    'Message',
                    'Bulk payment failed.'
                )
            )
        
    def action_check_payment_status(self):

        self.ensure_one()

        payload = {
            "AGGRID": "CIBBULK001",
            "CORPID": "TXBCORP2",
            "USERID": "TXBCORP2.USER2",
            "URN": "CIBTESTING",
            "FILESEQNUM": self.icici_file_seq_num,
            "ISENCRYPTED": "N"
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/v1/ReverseMis_sv'
        )

        result = self.call_icici_api(
            url,
            payload
        )

        self.icici_response = result.get(
            'response'
        )

        try:

            json_start = response.find('{')

            json_end = response.rfind('}') + 1

            clean_response = response[
                json_start:json_end
            ]

            response_json = json.loads(
                clean_response
            )

        except Exception:

            raise ValidationError(
                f'Invalid ICICI response:\n\n{response}'
            )

        status = response_json.get(
            'STATUS'
        )

        status = (
            response_json.get('STATUS')
            or ''
        ).upper()

        if status in [
            'SUCCESS',
            'PAID',
            'COMPLETED'
        ]:

            self.icici_payment_status = 'paid'

        elif status == 'FAILED':

            self.icici_payment_status = 'failed'