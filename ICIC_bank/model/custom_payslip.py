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
session = requests.Session()


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

    _icici_public_key_cache = None
    def get_icici_public_key(self):
        cls = type(self)
        if cls._icici_public_key_cache:
            return cls._icici_public_key_cache
        module_path = os.path.dirname(__file__)
        public_key_path = os.path.join(
            module_path,
            '..',
            'icici_public.pem'
        )
        with open(public_key_path, 'rb') as f:
            key_data = f.read()
        cls._icici_public_key_cache = RSA.import_key(
            key_data
        )
        return cls._icici_public_key_cache
    
    _private_key_cache = None

    def get_private_key(self):
        cls = type(self)
        if cls._private_key_cache:
            return cls._private_key_cache
        module_path = os.path.dirname(__file__)
        private_key_path = os.path.join(
            module_path,
            '..',
            'private_key.pem'
        )
        with open(private_key_path, 'rb') as f:
            key_data = f.read()
        cls._private_key_cache = RSA.import_key(
            key_data
        )
        return cls._private_key_cache

    def encrypt_payload(self, payload):

        rsa_key = self.get_icici_public_key()

        json_data = json.dumps(
            payload,
            separators=(',', ':'),
            ensure_ascii=False
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
        headers = {
            'accept': '*/*',
            'content-type': 'application/json',
            'APIKEY': 'HLAo88SpqGCpnwW87KcdwElPsfhPGVyG'
        }
        response = None
        try:

            encrypted_payload = self.encrypt_payload(
                payload
            )

            _logger.info(
                'ICICI API CALL STARTED'
            )

            for attempt in range(3):
                _logger.info(
                    'ICICI REQUEST URL: %s',
                    url
                )

                _logger.info(
                    'ICICI REQUEST BODY: %s',
                    encrypted_payload
                )

                try:

                    response = session.post(
                        url,
                        headers=headers,
                        json=encrypted_payload,
                        timeout=(10, 60)
                    )
                    _logger.info(
                        'ICICI RAW RESPONSE: %s',
                        response.text
                    )

                    break

                except requests.exceptions.ReadTimeout:

                    _logger.warning(
                        'ICICI timeout retry %s',
                        attempt + 1
                    )

                    if attempt == 2:

                        raise ValidationError(
                            'ICICI server timeout. Please try again.'
                        )

            if response is None:

                raise ValidationError(
                    'No response from ICICI.'
                )

            _logger.info(
                'ICICI STATUS CODE: %s',
                response.status_code
            )

            if response.status_code != 200:

                try:

                    error_response = response.json()

                    error_message = (
                        error_response.get('errormessage')
                        or error_response.get('message')
                        or response.text
                    )

                except Exception:

                    error_message = response.text

                raise ValidationError(
                    f'ICICI API Error:\n{error_message}'
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

        except requests.exceptions.ConnectionError:

            raise ValidationError(
                'Unable to connect to ICICI server.'
            )

            
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
            employee = slip.employee_id
            bank_account_rec = (
                employee.bank_account_ids.filtered(
                    lambda b: b.acc_number
                )[:1]
            )

            if not bank_account_rec:

                raise ValidationError(
                    f'Employee bank account missing for {employee.name}'
                )

            if not bank_account_rec.acc_number:

                raise ValidationError(
                    f'Employee account number missing for {employee.name}'
                )

            amount = 1
            # amount = int(slip.net_wage)

            if amount <= 0:

                raise ValidationError(
                    f'Invalid salary amount for {employee.name}'
                )

        unique_id = str(
            random.randint(10000, 99999)
        )

        create_payload = {
            "AGGRID": "CIBBULK001",
            "AGGRNAME": "BULKTESTING",
            "CORPID": "TXBCORP2",
            "USERID": "USER2",
            "URN": "CIBTESTING",
            "UNIQUEID": unique_id
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/Corporate/CIB_SV/v1/Create'
        )

        self.env.cr.commit()

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

        otp = (
            response_json.get('OTP')
            or response_json.get('otp')
            or response_json.get('AgOtp')
        )

        _logger.info(
            'ICICI OTP RECEIVED: %s',
            otp
        )

        if not otp:

            raise ValidationError(
                f'OTP not received.\n\n{response}'
            )

        self.write({
            'icici_generated_otp': otp,
            'icici_payment_status': 'otp_pending',
            'icici_reference': unique_id
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

        from datetime import datetime

        today_date = datetime.today().strftime(
            '%d/%m/%Y'
        )
        for slip in self:
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
                (
                    bank_account_rec.acc_number or ''
                ).replace(' ', '').replace('-', '')
            ).strip()
            if not bank_account:
                raise ValidationError(
                    f'Account number missing for {employee.name}'
                )
            bank = bank_account_rec.bank_id
            ifsc = (
                (
                    bank.bic or ''
                ).replace(' ', '')
            ).upper().strip()
            if not ifsc:
                raise ValidationError(
                    f'IFSC missing for {employee.name}'
                )
            # amount = int(
            #     slip.net_wage
            # )
            amount = 1
            if amount <= 0:
                raise ValidationError(
                    f'Invalid amount for {employee.name}'
                )
            total_amount += amount
            if ifsc.upper().startswith('ICIC'):
                transaction_type = 'MCW'
            else:
                transaction_type = 'MCO'

            clean_name = (
                employee.name
                .replace('|', '')
                .replace('^', '')
                .replace('.', '')
                .replace(',', '')
                .strip()
                .upper()[:20]
            )

            if ifsc.startswith('ICIC'):
                line = (
                    f'MCW|{bank_account}|0411|'
                    f'{clean_name}|{amount}|'
                    f'INR|salary|{ifsc}|WIB^'
                )

            else:

                line = (
                    f'MCO|{bank_account}|0011|'
                    f'{clean_name}|{amount}|'
                    f'INR|salary|NFT|{ifsc}^'
                )

            salary_lines.append(line)

        file_lines = [
            (
                f'FHR|7|{today_date}|salarybatch|'
                f'{total_amount}|INR|000451000301|0011^'
            ),
            (
                f'MDR|000451000301|0011|salary|'
                f'{total_amount}|INR|salary|'
                f'ICIC0000011|WIB^'
            )
        ]
        file_lines.extend(
            salary_lines
        )

        salary_file = '\r\n'.join(
            file_lines
        ) + '\r\n'

        _logger.info(
            'ICICI FINAL SALARY FILE:\n%s',
            salary_file
        )

        encoded_file = base64.b64encode(
            salary_file.encode()
        ).decode()

        payload = {
            'FILE_DESCRIPTION': f'TEST{random.randint(100000,999999)}',
            'AGGR_ID': 'CIBBULK001',
            'URN': 'CIBTESTING',
            'AGGR_NAME': 'BULKTESTING',
            'USER_ID': 'USER2',
            'CORP_ID': 'TXBCORP2',
            'UNIQUE_ID': self[0].icici_reference,
            'AGOTP': otp,
            'FILE_NAME': (
                f'salary_{random.randint(10000,99999)}.txt'
            ),
            'FILE_CONTENT': encoded_file
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

        if not response:

            raise ValidationError(
                'Empty response from ICICI.'
            )

        json_start = response.find('{')

        json_end = response.rfind('}') + 1

        clean_response = response[
            json_start:json_end
        ]

        response_json = json.loads(
            clean_response
        )

        response_code = response_json.get(
            'ResponseCode'
        )

        if response_code != '0000':

            raise ValidationError(
                response_json.get(
                    'Message',
                    'ICICI Payment Failed'
                )
            )

        file_seq_num = response_json.get(
            'FILESEQNUM'
        )

        utr = response_json.get(
            'UTR'
        )

        for slip in self:

            slip.icici_payment_status = (
                'processing'
            )

            slip.icici_file_seq_num = (
                file_seq_num
            )

            slip.icici_reference = (
                utr
            )

            slip.icici_response = (
                response
            )

            slip.icici_generated_otp = (
                False
            )

        return True
        
    def action_check_payment_status(self):

        self.ensure_one()

        if not self.icici_file_seq_num:

            raise ValidationError(
                'ICICI File Sequence Number missing.'
            )

        payload = {
            'AGGRID': 'CIBBULK001',
            'CORPID': 'TXBCORP2',
            'USERID': 'TXBCORP2.USER2',
            'URN': 'CIBTESTING',
            'FILESEQNUM': self.icici_file_seq_num,
            'ISENCRYPTED': 'N'
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/v1/ReverseMis_sv'
        )

        result = self.call_icici_api(
            url,
            payload
        )

        response = result.get('response')

        self.icici_response = response

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

            raise ValidationError(response)

        response_code = response_json.get(
            'ResponseCode'
        )

        payment_status = response_json.get(
            'STATUS'
        )

        if (
            response_code == '0000'
            and payment_status == 'SUCCESS'
        ):

            self.icici_payment_status = 'paid'

            self.state = 'paid'

        elif payment_status == 'FAILED':

            self.icici_payment_status = 'failed'

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }