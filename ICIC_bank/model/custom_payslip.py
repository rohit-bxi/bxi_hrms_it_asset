from odoo.fields import Date
from odoo import models, fields, _
from odoo.exceptions import ValidationError

import os
import json
import base64
import random
import string
import logging
import requests
import uuid

from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import AES
from Cryptodome.Cipher import PKCS1_v1_5
from Cryptodome.Util.Padding import pad, unpad

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    icici_payment_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("otp_pending", "OTP Pending"),
            ("processing", "Processing"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("reversed", "Reversed"),
        ],
        string="ICICI Payment Status",
        default="draft",
        copy=False,
    )

    icici_reference = fields.Char(
        string="ICICI Reference",
        copy=False,
        readonly=True,
    )

    icici_file_seq_num = fields.Char(
        string="File Sequence Number",
        copy=False,
        readonly=True,
    )

    icici_response = fields.Text(
        string="ICICI Response",
        copy=False,
        readonly=True,
    )

    icici_generated_otp = fields.Char(
        string="Generated OTP",
        copy=False,
    )

    icici_utr = fields.Char(
        string="UTR Number",
        copy=False,
        readonly=True,
    )

    _icici_public_key_cache = None
    _private_key_cache = None

    def random_16(self):
        """Generate a random 16-digit numeric string."""
        return "".join(
            random.choices(
                string.digits,
                k=16,
            )
        )

    def get_icici_public_key(self):
        """Load and cache the ICICI public key."""

        cls = type(self)

        if cls._icici_public_key_cache:
            return cls._icici_public_key_cache

        module_path = os.path.dirname(__file__)
        public_key_path = os.path.join(
            module_path,
            "..",
            "icici_public.pem",
        )

        if not os.path.exists(public_key_path):
            raise ValidationError(
                _("ICICI public key file not found.")
            )

        try:
            with open(public_key_path, "rb") as key_file:
                key_data = key_file.read()

            cls._icici_public_key_cache = RSA.import_key(
                key_data
            )

            return cls._icici_public_key_cache

        except Exception as exc:
            _logger.exception(
                "Unable to load ICICI public key."
            )
            raise ValidationError(
                _("Unable to load ICICI public key.")
            ) from exc

    def get_private_key(self):
        """Load and cache the client's private key."""

        cls = type(self)

        if cls._private_key_cache:
            return cls._private_key_cache

        module_path = os.path.dirname(__file__)
        private_key_path = os.path.join(
            module_path,
            "..",
            "private_key.pem",
        )

        if not os.path.exists(private_key_path):
            raise ValidationError(
                _("Private key file not found.")
            )

        try:
            with open(private_key_path, "rb") as key_file:
                key_data = key_file.read()

            cls._private_key_cache = RSA.import_key(
                key_data
            )

            return cls._private_key_cache

        except Exception as exc:
            _logger.exception(
                "Unable to load private key."
            )
            raise ValidationError(
                _("Unable to load private key.")
            ) from exc

    def encrypt_payload(self, payload):
        """Encrypt payload as per ICICI Hybrid Encryption specification."""

        rsa_key = self.get_icici_public_key()

        json_data = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        aes_key = self.random_16()
        iv = self.random_16()

        cipher_rsa = PKCS1_v1_5.new(rsa_key)

        encrypted_key = cipher_rsa.encrypt(
            aes_key.encode()
        )

        encrypted_key_b64 = base64.b64encode(
            encrypted_key
        ).decode()

        plaintext = iv + json_data

        cipher_aes = AES.new(
            aes_key.encode(),
            AES.MODE_CBC,
            iv=iv.encode(),
        )

        encrypted_data = cipher_aes.encrypt(
            pad(
                plaintext.encode(),
                AES.block_size,
            )
        )

        encrypted_data_b64 = base64.b64encode(
            encrypted_data
        ).decode()

        return {
            "requestId": "",
            "service": "CIB",
            "encryptedKey": encrypted_key_b64,
            "oaepHashingAlgorithm": "NONE",
            "iv": "",
            "encryptedData": encrypted_data_b64,
            "clientInfo": "",
            "optionalParam": "",
        }

    def decrypt_response(self, response_data):
        """Decrypt ICICI encrypted response."""

        encrypted_key = response_data.get("encryptedKey")
        encrypted_data = response_data.get("encryptedData")

        if not encrypted_key or not encrypted_data:
            raise ValidationError(
                _("Incomplete encrypted response received from ICICI.")
            )

        try:
            private_key = self.get_private_key()

            encrypted_key_bytes = base64.b64decode(
                encrypted_key
            )

            _logger.debug(
                "Encrypted key length: %s",
                len(encrypted_key_bytes),
            )

            cipher_rsa = PKCS1_v1_5.new(
                private_key
            )

            aes_key = cipher_rsa.decrypt(
                encrypted_key_bytes,
                None,
            )

            if not aes_key:
                raise ValidationError(
                    _("Unable to decrypt AES key.")
                )

            encrypted_data_bytes = base64.b64decode(
                encrypted_data
            )

            iv = encrypted_data_bytes[:16]

            cipher_aes = AES.new(
                aes_key,
                AES.MODE_CBC,
                iv=iv,
            )

            decrypted = unpad(
                cipher_aes.decrypt(
                    encrypted_data_bytes
                ),
                AES.block_size,
            )

            return decrypted[16:].decode("utf-8")

        except ValidationError:
            raise

        except Exception as exc:
            _logger.exception(
                "ICICI response decryption failed."
            )
            raise ValidationError(
                _("Unable to decrypt ICICI response.")
            ) from exc

    def call_icici_api(self, url, payload):
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "APIKEY": "HLAo88SpqGCpnwW87KcdwElPsfhPGVyG",
        }

        response = None

        try:
            encrypted_payload = self.encrypt_payload(payload)

            _logger.info(
                "ICICI API Call Started"
            )

            _logger.info(
                "ICICI URL: %s",
                url,
            )

            for attempt in range(3):
                try:
                    _logger.debug(
                        "ICICI Request Payload: %s",
                        encrypted_payload,
                    )

                    response = requests.post(
                        url=url,
                        headers=headers,
                        json=encrypted_payload,
                        timeout=(10, 60),
                    )

                    _logger.info(
                        "ICICI Status Code: %s",
                        response.status_code,
                    )

                    _logger.debug(
                        "ICICI Raw Response: %s",
                        response.text,
                    )

                    break

                except requests.exceptions.ReadTimeout:

                    _logger.warning(
                        "ICICI timeout (%s/3)",
                        attempt + 1,
                    )

                    if attempt == 2:
                        raise ValidationError(
                            _(
                                "ICICI server timeout. Please try again."
                            )
                        )

            if response is None:
                raise ValidationError(
                    _("No response received from ICICI.")
                )

            if response.status_code != 200:

                try:
                    error_json = response.json()

                    error_message = (
                        error_json.get("errormessage")
                        or error_json.get("message")
                        or response.text
                    )

                except ValueError:
                    error_message = response.text

                _logger.error(
                    "ICICI API Error [%s]: %s",
                    response.status_code,
                    error_message,
                )

                raise ValidationError(
                    _("ICICI API Error:\n%s") % error_message
                )

            try:
                response_json = response.json()

            except ValueError as exc:

                _logger.exception(
                    "Invalid JSON received from ICICI."
                )

                raise ValidationError(
                    _("Invalid JSON received from ICICI.")
                ) from exc

            decrypted_response = self.decrypt_response(
                response_json
            )

            _logger.info(
                "ICICI Decrypted Response: %s",
                decrypted_response,
            )

            return {
                "status_code": response.status_code,
                "response": decrypted_response,
            }

        except requests.exceptions.RequestException as exc:

            _logger.exception(
                "Unable to connect to ICICI."
            )

            raise ValidationError(
                _("Unable to connect to ICICI server.")
            ) from exc
        
    def action_release_salary(self):
        if not self:
            raise ValidationError(
                _("No payslips selected.")
            )

        for slip in self:

            if slip.icici_payment_status == "paid":
                raise ValidationError(
                    _("Salary has already been released for %s.")
                    % slip.employee_id.name
                )

            if slip.state in ("draft", "cancel"):
                raise ValidationError(
                    _("%s payslip is not confirmed.")
                    % slip.employee_id.name
                )

            employee = slip.employee_id

            bank_account = employee.bank_account_ids.filtered(
                lambda account: account.acc_number
            )[:1]

            if not bank_account:
                raise ValidationError(
                    _("Bank account is missing for %s.")
                    % employee.name
                )

            if not bank_account.acc_number:
                raise ValidationError(
                    _("Bank account number is missing for %s.")
                    % employee.name
                )

            # Production
            amount = int(slip.net_wage or 0)

            # UAT only
            # amount = 1

            if amount <= 0:
                raise ValidationError(
                    _("Invalid salary amount for %s.")
                    % employee.name
                )

        unique_id = uuid.uuid4().hex[:16].upper()

        _logger.info(
            "ICICI UNIQUE ID: %s",
            unique_id,
        )

        create_payload = {
            "AGGRID": "CIBBULK001",
            "AGGRNAME": "BULKTESTING",
            "CORPID": "TXBCORP1",
            "USERID": "USER1",
            "URN": "CIBTESTING",
            "UNIQUEID": unique_id,
        }

        _logger.info(
            "ICICI Create Payload: %s",
            create_payload,
        )

        url = (
            "https://apibankingonesandbox.icici.bank.in"
            "/api/Corporate/CIB_SV/v1/Create"
        )

        result = self[0].call_icici_api(
            url,
            create_payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            response_json = json.loads(
                response[json_start:json_end]
            )

        except json.JSONDecodeError as exc:

            _logger.exception(
                "Invalid ICICI Create response."
            )

            raise ValidationError(
                _("Invalid response received from ICICI.")
            ) from exc

        otp = (
            response_json.get("OTP")
            or response_json.get("otp")
            or response_json.get("AgOtp")
        )

        if not otp:
            raise ValidationError(
                _("OTP was not received from ICICI.")
            )

        _logger.info(
            "ICICI OTP generated successfully."
        )

        self.write({
            "icici_generated_otp": otp,
            "icici_payment_status": "otp_pending",
            "icici_reference": unique_id,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("ICICI OTP Verification"),
            "res_model": "icici.otp.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payslip_ids": self.ids,
            },
        }
    
    def process_bulk_payment(self, otp, payment_date):
        self.ensure_one()

        if not self:
            raise ValidationError(
                _("No payslips selected.")
            )

        payment_date = Date.to_date(payment_date)

        payment_date_str = payment_date.strftime(
            "%d/%m/%Y"
        )

        _logger.info(
            "Payment Date : %s",
            payment_date_str,
        )

        salary_file = self.generate_salary_file(
            payment_date_str
        )

        _logger.info(
            "ICICI Salary File:\n%s",
            salary_file,
        )

        encoded_file = base64.b64encode(
            salary_file.encode("utf-8")
        ).decode()

        payload = {
            "FILE_DESCRIPTION": "SALARY_BATCH",
            "AGGR_ID": "CIBBULK001",
            "URN": "CIBTESTING",
            "AGGR_NAME": "BULKTESTING",
            "USER_ID": "USER1",
            "CORP_ID": "TXBCORP1",
            "UNIQUE_ID": self[0].icici_reference,
            "AGOTP": otp,
            "FILE_NAME": (
                f"SALARY_{random.randint(1000,9999)}.txt"
            ),
            "FILE_CONTENT": encoded_file,
        }

        _logger.info(
            "ICICI Bulk Payment Payload Prepared."
        )

        result = self[0].call_icici_api(
            "https://apibankingonesandbox.icici.bank.in/api/v1/cibbulkpayment_sv/bulkPayment",
            payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            response_json = json.loads(
                response[json_start:json_end]
            )

        except json.JSONDecodeError as exc:

            _logger.exception(
                "Invalid ICICI Bulk Payment response."
            )

            raise ValidationError(
                _("Invalid response received from ICICI.")
            ) from exc

        _logger.info(
            "ICICI Bulk Payment Response : %s",
            response_json,
        )

        file_seq_num = response_json.get(
            "FILE_SEQUENCE_NUM"
        )

        utr = response_json.get("UTR")

        if not file_seq_num:
            raise ValidationError(
                response_json.get("MESSAGE_DESC")
                or response_json.get("Message")
                or _("ICICI Payment Failed.")
            )

        self.write({
            "icici_payment_status": "processing",
            "icici_file_seq_num": str(file_seq_num),
            "icici_utr": utr,
            "icici_response": response,
            "icici_generated_otp": False,
        })

        _logger.info(
            "ICICI Bulk Payment submitted successfully. File Sequence Number: %s",
            file_seq_num,
        )

        return True
    
    def action_reverse_payment(self, file_seq_num):
        self.ensure_one()

        if not file_seq_num:
            raise ValidationError(
                _("File Sequence Number is required.")
            )

        _logger.info(
            "ICICI Reverse Payment - File Sequence: %s",
            file_seq_num,
        )

        payload = {
            "AGGRID": "CIBBULK001",
            "CORPID": "TXBCORP1",
            "USERID": "TXBCORP1.USER1",
            "URN": "CIBTESTING",
            "FILESEQNUM": file_seq_num,
            "UNIQUEID": self.icici_reference,
            "ISENCRYPTED": "N",
        }

        _logger.info(
            "ICICI Reverse Payload: %s",
            payload,
        )

        result = self.call_icici_api(
            "https://apibankingonesandbox.icici.bank.in/api/v1/ReverseMis_sv",
            payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        _logger.info(
            "ICICI Reverse Response: %s",
            response,
        )

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError as exc:
            _logger.exception(
                "Invalid reverse response from ICICI."
            )
            raise ValidationError(
                _("Invalid response received from ICICI.")
            ) from exc

        xml_data = response_json.get("XML", {})

        if xml_data.get("RESPONSE") != "SUCCESS":
            raise ValidationError(
                xml_data.get(
                    "MESSAGE"
                ) or _("Reverse payment failed.")
            )

        self.write({
            "icici_payment_status": "reversed",
            "icici_response": response,
            "icici_generated_otp": False,
        })

        _logger.info(
            "ICICI payment reversed successfully for payslip %s",
            self.number or self.id,
        )

        return True
    def action_open_reverse_wizard(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Reverse Payment"),
            "res_model": "icici.reverse.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payslip_id": self.id,
                "default_file_seq_num": self.icici_file_seq_num,
            },
        }