from datetime import datetime
import uuid
import requests
from odoo import _, fields, models
from odoo.fields import Date
from odoo.exceptions import ValidationError
from secrets import choice
import base64
import json
import logging
import os
import string
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.PublicKey import RSA
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
        index=True,
    )

    icici_file_seq_num = fields.Char(
        string="File Sequence Number",
        copy=False,
        readonly=True,
        index=True,
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
        index=True,
    )

    _icici_public_key_cache = None
    _private_key_cache = None

    def random_16(self):
        """Generate a cryptographically secure 16-digit random number."""
        return "".join(
            choice(string.digits)
            for _ in range(16))

    def get_icici_public_key(self):
        """Load and cache the ICICI public key."""

        cls = type(self)

        if cls._icici_public_key_cache:
            return cls._icici_public_key_cache

        module_path = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.join(
            module_path,
            "..",
            "icici_public.pem",
        )

        if not os.path.isfile(key_path):
            raise ValidationError(
                _("ICICI public key file not found.")
            )

        try:
            with open(key_path, "rb") as file:
                cls._icici_public_key_cache = RSA.import_key(
                    file.read()
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
        """Load and cache client private key."""

        cls = type(self)

        if cls._private_key_cache:
            return cls._private_key_cache

        key_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "private_key.pem",
        )

        if not os.path.isfile(key_path):
            raise ValidationError(
                _("Private key file not found.")
            )

        try:
            with open(key_path, "rb") as file:
                cls._private_key_cache = RSA.import_key(
                    file.read()
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
        """Encrypt payload using ICICI Hybrid Encryption."""

        rsa_key = self.get_icici_public_key()

        json_payload = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
            sort_keys=True,
        )

        aes_key = self.random_16()
        iv = self.random_16()

        cipher_rsa = PKCS1_v1_5.new(rsa_key)

        encrypted_key = base64.b64encode(
            cipher_rsa.encrypt(aes_key.encode("utf-8"))
        ).decode("utf-8")

        cipher_aes = AES.new(
            aes_key.encode("utf-8"),
            AES.MODE_CBC,
            iv.encode("utf-8"),
        )

        plaintext = iv + json_payload

        encrypted_data = base64.b64encode(
            cipher_aes.encrypt(
                pad(
                    plaintext.encode("utf-8"),
                    AES.block_size,
                )
            )
        ).decode("utf-8")

        return {
            "requestId": "",
            "service": "CIB",
            "encryptedKey": encrypted_key,
            "oaepHashingAlgorithm": "NONE",
            "iv": "",
            "encryptedData": encrypted_data,
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

            cipher_rsa = PKCS1_v1_5.new(private_key)

            aes_key = cipher_rsa.decrypt(
                base64.b64decode(encrypted_key),
                None,
            )

            if not aes_key or len(aes_key) != 16:
                raise ValidationError(
                    _("Invalid AES key received from ICICI.")
                )

            encrypted_bytes = base64.b64decode(
                encrypted_data,
                validate=True,
            )

            iv = encrypted_bytes[:16]

            cipher_text = encrypted_bytes[16:]

            cipher_aes = AES.new(
                aes_key,
                AES.MODE_CBC,
                iv,
            )

            decrypted = unpad(
                cipher_aes.decrypt(cipher_text),
                AES.block_size,
            )

            _logger.info(
                "FULL DECRYPTED RAW = %r",
                decrypted,
            )

            full_response = decrypted.decode("utf-8")

            _logger.info(
                "FULL DECRYPTED STRING = %s",
                full_response,
            )

            return full_response

        except ValidationError:
            raise

        except UnicodeDecodeError as exc:
            raise ValidationError(
                _("Unable to decode ICICI response.")
            ) from exc

        except Exception as exc:
            _logger.exception(
                "Unable to decrypt ICICI response."
            )
            raise ValidationError(
                _("Unable to decrypt ICICI response.")
            ) from exc
             
    def call_icici_api(self, url, payload):
        """Call ICICI API using Hybrid Encryption."""
        self.ensure_one()

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "APIKEY": "Xz1K4tKqhYwWEbo0qeTQ30XbRtdJtCNP",
        }

        encrypted_payload = self.encrypt_payload(payload)

        _logger.info("=" * 80)
        _logger.info("ICICI API CALL STARTED")
        _logger.info("URL : %s", url)

        response = None

        for attempt in range(1, 4):

            try:

                response = requests.post(
                    url=url,
                    headers=headers,
                    json=encrypted_payload,
                    timeout=(10, 60),
                )

                _logger.info(
                    "ICICI Response Status : %s",
                    response.status_code,
                )

                if response.status_code != 200:

                    try:
                        error_json = response.json()

                        error_message = (
                            error_json.get("errormessage")
                            or error_json.get("message")
                            or error_json.get("MESSAGE")
                            or response.text
                        )

                    except Exception:
                        error_message = response.text

                    raise ValidationError(
                        _("ICICI API Error:\n%s") % error_message
                    )

                response_json = response.json()

                decrypted_response = self.decrypt_response(
                    response_json
                )

                _logger.info(
                    "RETURNING RESPONSE = %s",
                    decrypted_response,
                )

                return {
                    "status_code": response.status_code,
                    "response": decrypted_response,
                }

            except requests.exceptions.ReadTimeout:

                _logger.warning(
                    "ICICI timeout (%s/3)",
                    attempt,
                )

                if attempt == 3:
                    raise ValidationError(
                        _("ICICI server timeout. Please try again.")
                    )

            except requests.exceptions.ConnectionError as exc:
                raise ValidationError(
                    _("Unable to connect to ICICI server.")
                ) from exc

            except ValidationError:
                raise

            except Exception as exc:

                _logger.exception(
                    "Unexpected ICICI API Error"
                )

                raise ValidationError(
                    _("Unexpected error while communicating with ICICI.")
                ) from exc

        raise ValidationError(
            _("Unable to process ICICI request.")
        )
               
    def action_release_salary(self):
        """Generate ICICI reference and open OTP wizard."""

        for slip in self:

            if slip.icici_payment_status in (
                "otp_pending",
                "processing",
                "paid",
            ):
                raise ValidationError(
                    _(
                        "Salary payment has already been initiated for %s."
                    ) % slip.employee_id.name
                )

            if slip.state != "validated":
                raise ValidationError(
                    _(
                        "%s payslip must be validated before salary release."
                    ) % slip.employee_id.name
                )

            employee = slip.employee_id

            bank_account = employee.bank_account_ids.filtered(
                lambda account: account.acc_number and account.bank_id
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

            if not bank_account.bank_id:
                raise ValidationError(
                    _("Bank is not configured for %s.")
                    % employee.name
                )

            if not bank_account.bank_id.bic:
                raise ValidationError(
                    _("IFSC Code is missing for %s.")
                    % employee.name
                )

            amount = round(slip.net_wage or 0, 2)

            if amount <= 0:
                raise ValidationError(
                    _("Invalid salary amount for %s.")
                    % employee.name
                )

        unique_id = uuid.uuid4().hex[:16].upper()

        while self.search_count([
            ("icici_reference", "=", unique_id)
        ]):
            unique_id = uuid.uuid4().hex[:16].upper()

        create_payload = {
            "AGGRID": "BULK0173",
            "AGGRNAME": "BXITECH",
            "CORPID": "601902129",
            "USERID": "BALCHAND",
            "URN": "SR283346233",
            "UNIQUEID": unique_id,
        }

        _logger.info("=" * 80)
        _logger.info("ICICI Create API Request Started")
        _logger.info(
            "Payload:\n%s",
            json.dumps(create_payload, indent=4),
        )
        _logger.info("=" * 80)

        result = self[0].call_icici_api(
            "https://apibankingone.icici.bank.in/api/Corporate/CIB/v1/Create",
            create_payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        response = response.strip()

        json_start = response.find("{")
        json_end = response.rfind("}")

        if json_start == -1 or json_end == -1:
            raise ValidationError(
                _("Invalid response received from ICICI.\n\n%s")
                % response
            )

        clean_response = response[
            json_start: json_end + 1
        ]

        try:
            response_json = json.loads(clean_response)

        except json.JSONDecodeError as exc:

            _logger.exception(
                "Unable to parse ICICI Create API response."
            )

            raise ValidationError(
                _("Unable to parse ICICI response.")
            ) from exc

        _logger.info(
            "ICICI Create API Response:\n%s",
            json.dumps(response_json, indent=4),
        )

        response_status = (
            response_json.get("RESPONSE")
            or response_json.get("Response")
            or ""
        ).strip().upper()

        if response_status != "SUCCESS":
            raise ValidationError(
                response_json.get("MESSAGE")
                or response_json.get("Message")
                or _("ICICI Create API failed.")
            )

        otp = (
            response_json.get("OTP")
            or response_json.get("otp")
            or response_json.get("AgOtp")
        )

        self.write({
            "icici_reference": unique_id,
            "icici_payment_status": "otp_pending",
            "icici_generated_otp": otp or False,
        })

        if otp:
            _logger.info(
                "OTP received from ICICI API."
            )
        else:
            _logger.info(
                "Create API succeeded. OTP will be received by the authorized user."
            )

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
    
    def generate_salary_file(self, payment_date):
        """
        Generate ICICI salary file in the format shared by ICICI Bank.
        """
        total_amount = 0
        transaction_count = 0
        detail_lines = []
        debit_account = "693905601661"
        for slip in self:
            employee = slip.employee_id
            bank_account = employee.bank_account_ids.filtered(
                lambda b: b.acc_number
            )[:1]
            if not bank_account:
                raise ValidationError(
                    _("Bank account is missing for %s.")
                    % employee.name
                )
            account_number = bank_account.acc_number.strip()
            if not account_number:
                raise ValidationError(
                    _("Bank account number is missing for %s.")
                    % employee.name
                )
            if not bank_account.bank_id:
                raise ValidationError(
                    _("Bank is missing for %s.")
                    % employee.name
                )
            ifsc = (
                bank_account.bank_id.bic or ""
            ).strip()
            if not ifsc:
                raise ValidationError(
                    _("IFSC Code is missing for %s.")
                    % employee.name
                )
            amount = round(slip.net_wage or 0, 2)
            if amount <= 0:
                raise ValidationError(
                    _("Invalid salary amount for %s.")
                    % employee.name
                )
            total_amount += amount
            transaction_count += 1
            transaction_type = (
                "MCW"
                if ifsc.startswith("ICIC")
                else "MCO"
            )
            network = (
                "WIB"
                if ifsc.startswith("ICIC")
                else "NFT"
            )
            ICICI_BRANCH_CODE = "6939"
            employee_branch = ifsc[-4:]
            detail_lines.append(
                "|".join([
                    transaction_type,
                    account_number,
                    employee_branch,
                    employee.name.strip()[:35],
                    str(amount),
                    "INR",
                    "Salary",
                    network,
                    ifsc,
                ]) + "^"
            )
        header = (
            f"FHR|{transaction_count}|"
            f"{payment_date}|"
            f"SALARY|"
            f"{total_amount}|"
            f"INR|"
            f"{debit_account}|"
            f"{ICICI_BRANCH_CODE}^"
        )
        maker = (
            f"MDR|"
            f"{debit_account}|"
            f"{ICICI_BRANCH_CODE}|"
            f"Salary|"
            f"{total_amount}|"
            f"INR|"
            f"Salary Batch|"
            f"ICIC0000011|"
            f"WIB^"
        )

        salary_file = "\r\n".join(
            [header, maker] + detail_lines
        )

        return salary_file
    
    def process_bulk_payment(self, otp, payment_date):
        if not self:
            raise ValidationError(
                _("No payslips selected.")
            )

        if not self[0].icici_reference:
            raise ValidationError(
                _("ICICI Reference is missing.")
            )

        payment_date = Date.to_date(payment_date)
        payment_date_str = payment_date.strftime("%m/%d/%Y")

        _logger.info(
            "Payment Date : %s",
            payment_date_str,
        )

        salary_file = self.generate_salary_file(
            payment_date_str
        )

        _logger.info(
            "ICICI Salary File Generated.%s",salary_file,
        )

        encoded_file = base64.b64encode(
            salary_file.encode("utf-8")
        ).decode()

        payload = {
            "FILE_DESCRIPTION": "Salary Payment",
            "AGGR_ID": "BULK0173",
            "URN": "SR283346233",
            "AGGR_NAME": "BXITECH",
            "USER_ID": "BALCHAND",
            "CORP_ID": "601902129",
            "UNIQUE_ID": self[0].icici_reference,
            "AGOTP": otp,
            "FILE_NAME": (
                f"SALARY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            ),
            "FILE_CONTENT": encoded_file,
        }

        _logger.info(
            "Submitting ICICI Bulk Payment."
        )

        result = self[0].call_icici_api(
            "https://apibankingone.icici.bank.in/api/v1/cibbulkpayment/bulkPayment",
            payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        response = response.strip()
        json_start = response.find("{")
        json_end = response.rfind("}")
        if json_start == -1 or json_end == -1:
            _logger.error(
                "Invalid ICICI Response:\n%s",
                response,
            )
            raise ValidationError(
                _("Invalid ICICI response.\n\n%s") % response
            )
        clean_response = response[
            json_start: json_end + 1
        ]

        try:
            response_json = json.loads(clean_response)

        except json.JSONDecodeError as exc:
            _logger.exception(
                "Unable to parse ICICI response."
            )
            raise ValidationError(
                _("Unable to parse ICICI response.\n\n%s")
                % clean_response
            ) from exc

        _logger.info(
            "ICICI Bulk Payment Response : %s",
            response_json,
        )

        file_seq_num = (
            response_json.get("FILE_SEQUENCE_NUM")
            or response_json.get("FILESEQNUM")
        )

        utr = (
            response_json.get("UTR")
            or response_json.get("UTRNO")
        )

        if not file_seq_num:
            raise ValidationError(
                response_json.get("MESSAGE_DESC")
                or response_json.get("Message")
                or _("ICICI Payment Failed.")
            )

        self.write({
            "icici_payment_status": "processing",
            "icici_file_seq_num": str(file_seq_num),
            "icici_utr": utr or False,
            "icici_response": response,
            "icici_generated_otp": False,
        })

        _logger.info(
            "Bulk payment submitted successfully. File Sequence Number : %s",
            file_seq_num,
        )

        return True


    def action_reverse_payment(self, file_seq_num):
        self.ensure_one()

        if not file_seq_num:
            raise ValidationError(
                _("File Sequence Number is required.")
            )

        if not self.icici_reference:
            raise ValidationError(
                _("ICICI Reference is missing.")
            )

        if self.icici_payment_status not in (
            "processing",
            "failed",
        ):
            raise ValidationError(
                _("Only payments in Processing state can be reversed.")
            )

        payload = {
            "AGGRID": "BULK0173",
            "CORPID": "601902129",
            "USERID": "BALCHAND",
            "URN": "SR283346233",
            "FILESEQNUM": file_seq_num,
            "UNIQUEID": self.icici_reference,
            "ISENCRYPTED": "N",
        }

        _logger.info(
            "Submitting ICICI Reverse Payment."
        )

        result = self.call_icici_api(
            "https://apibankingone.icici.bank.in/api/v1/ReverseMis",
            payload,
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        try:
            response_json = json.loads(response)

        except Exception as exc:
            _logger.exception(
                "Unable to parse reverse response."
            )
            raise ValidationError(
                _("Invalid response received from ICICI.")
            ) from exc

        xml_data = (
            response_json.get("XML")
            or response_json.get("xml")
            or {}
        )
        if xml_data.get("RESPONSE") != "SUCCESS":
            raise ValidationError(
                xml_data.get("MESSAGE")
                or _("Reverse payment failed.")
            )

        self.write({
            "icici_payment_status": "reversed",
            "icici_response": response,
            "icici_generated_otp": False,
            "icici_file_seq_num": False,
        })

        _logger.info(
            "Reverse payment completed successfully."
        )

        return True
    def action_open_reverse_wizard(self):
        self.ensure_one()

        if not self.icici_file_seq_num:
            raise ValidationError(
                _("File Sequence Number is not available.")
            )

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