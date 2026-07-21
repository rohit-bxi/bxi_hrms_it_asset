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
    _inherit = "account.move"

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
        """Generate a cryptographically secure 16-digit numeric string."""
        return "".join(
            choice(string.digits)
            for _ in range(16)
        )

    def get_icici_public_key(self):
        """Load and cache the ICICI public key."""

        cls = type(self)

        if cls._icici_public_key_cache:
            return cls._icici_public_key_cache

        key_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "icici_public.pem",
        )

        if not os.path.isfile(key_path):
            raise ValidationError(
                _("ICICI public key file not found.")
            )

        try:
            with open(key_path, "rb") as f:
                cls._icici_public_key_cache = RSA.import_key(
                    f.read()
                )

            _logger.info(
                "ICICI public key loaded successfully."
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
        """Load and cache the client private key."""

        cls = type(self)

        if cls._private_key_cache:
            return cls._private_key_cache

        module_path = os.path.abspath(
            os.path.dirname(__file__)
        )

        key_path = os.path.join(
            module_path,
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

        try:
            rsa_key = self.get_icici_public_key()

            json_payload = json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            )

            aes_key = self.random_16()
            iv = self.random_16()

            _logger.info("=" * 80)
            _logger.info("ICICI Payload Encryption Started")

            encrypted_key = base64.b64encode(
                PKCS1_v1_5.new(rsa_key).encrypt(
                    aes_key.encode("utf-8")
                )
            ).decode("utf-8")

            cipher = AES.new(
                aes_key.encode(),
                AES.MODE_CBC,
                iv.encode()
            )

            cipher_text = cipher.encrypt(
                pad(
                    json_payload.encode(),
                    AES.block_size
                )
            )

            # ICICI Option-B: IV prepended to ciphertext
            encrypted_data = base64.b64encode(
                iv.encode("utf-8") + cipher_text
            ).decode("utf-8")

            _logger.info(
                "ICICI Payload Encryption Completed."
            )

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

        except Exception as exc:

            _logger.exception(
                "ICICI payload encryption failed."
            )

            raise ValidationError(
                _("Unable to encrypt ICICI request.")
            ) from exc

    def decrypt_response(self, response_data):
        """Decrypt ICICI encrypted response."""

        encrypted_key = response_data.get("encryptedKey")
        encrypted_data = response_data.get("encryptedData")

        if not encrypted_key:
            raise ValidationError(
                _("ICICI encrypted key is missing.")
            )

        if not encrypted_data:
            raise ValidationError(
                _("ICICI encrypted data is missing.")
            )

        try:

            private_key = self.get_private_key()

            aes_key = PKCS1_v1_5.new(
                private_key
            ).decrypt(
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

            if len(encrypted_bytes) <= 16:
                raise ValidationError(
                    _("Invalid encrypted response received from ICICI.")
                )

            iv = encrypted_bytes[:16]
            cipher_text = encrypted_bytes[16:]

            cipher = AES.new(
                aes_key,
                AES.MODE_CBC,
                iv,
            )

            decrypted = unpad(
                cipher.decrypt(cipher_text),
                AES.block_size,
            )

            _logger.info(
                "FULL DECRYPTED RAW = %r",
                decrypted,
            )

            if len(decrypted) <= 16:
                raise ValidationError(
                    _("Invalid decrypted response received from ICICI.")
                )

            # ICICI specification:
            # Ignore first 16 bytes after decryption.
            full_response = decrypted.decode("utf-8")
            _logger.info(
                "FULL RESPONSE = %s",
                full_response,
            )

            if full_response.startswith("{"):
                return full_response

            return full_response[16:]

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

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "APIKEY": "Xz1K4tKqhYwWEbo0qeTQ30XbRtdJtCNP",
        }

        encrypted_payload = self.encrypt_payload(payload)

        _logger.info("=" * 80)
        _logger.info("ICICI API CALL STARTED")
        _logger.info("URL : %s", url)
        _logger.info("REQUEST :\n%s", json.dumps(payload, indent=4))
        _logger.info("=" * 80)

        for attempt in range(1, 4):

            try:
                _logger.info(
                    json.dumps(
                        encrypted_payload,
                        indent=4
                    )
                )
                response = requests.post(
                    url=url,
                    headers=headers,
                    json=encrypted_payload,
                    timeout=(10, 60),
                )

                _logger.info(
                    "HTTP STATUS : %s",
                    response.status_code,
                )

                if response.status_code != 200:

                    _logger.error("=" * 80)
                    _logger.error("ICICI HTTP ERROR")
                    _logger.error(
                        "Status Code : %s",
                        response.status_code,
                    )
                    _logger.error(
                        "Headers : %s",
                        dict(response.headers),
                    )
                    _logger.error(
                        "Body : %s",
                        response.text,
                    )
                    _logger.error("=" * 80)

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
                        _("ICICI API Error:\n%s")
                        % error_message
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

                if (
                    "encryptedKey" not in response_json
                    or "encryptedData" not in response_json
                ):
                    raise ValidationError(
                        _("Encrypted response not received from ICICI.")
                    )

                decrypted_response = self.decrypt_response(
                    response_json
                )

                _logger.info("=" * 80)
                _logger.info("ICICI API SUCCESS")
                _logger.info(
                    "RESPONSE : %s",
                    decrypted_response,
                )
                _logger.info("=" * 80)

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
                        _(
                            "ICICI server timed out. Please try again."
                        )
                    )

            except requests.exceptions.ConnectionError as exc:

                _logger.exception(
                    "Unable to connect to ICICI."
                )

                if attempt == 3:
                    raise ValidationError(
                        _(
                            "Unable to connect to the ICICI server."
                        )
                    ) from exc

            except ValidationError:
                raise

            except Exception as exc:

                _logger.exception(
                    "Unexpected ICICI API error."
                )

                raise ValidationError(
                    _(
                        "Unexpected error occurred while communicating with ICICI."
                    )
                ) from exc

        raise ValidationError(
            _("Unable to process the ICICI request.")
        )
    
    def action_vendor_bill_release(self):
        """Validate expenses, call ICICI Create API and open OTP wizard."""

        if not self:
            raise ValidationError(
                _("No Vendor Bill selected.")
            )
        for slip in self:

            if slip.icici_payment_status in (
                "otp_pending",
                "processing",
                "paid",
            ):
                raise ValidationError(
                    _(
                        "Vendor bill payment has already been initiated for %s."
                    )
                    % slip.partner_id.name
                )

            if slip.state != "posted":
                raise ValidationError(
                    _(
                        "%s vendor bill must be posted before payment release."
                    )
                    % slip.partner_id.name
                )

            partner = slip.partner_id

            bank_account = partner.bank_ids.filtered(
                lambda account:
                    account.acc_number
                    and account.bank_id
                    and account.bank_id.bic
            )[:1]

            if not bank_account:
                raise ValidationError(
                    _(
                        "Please configure a valid bank account for %s."
                    )
                    % partner.name
                )

            if not bank_account.acc_number:
                raise ValidationError(
                    _("Account Number is missing for %s.")
                    % partner.name
                )

            if not bank_account.bank_id:
                raise ValidationError(
                    _("Bank is not configured for %s.")
                    % partner.name
                )

            if not bank_account.bank_id.bic:
                raise ValidationError(
                    _("IFSC Code is missing for %s.")
                    % partner.name
                )

            amount = float(slip.amount_residual or 0.0)

            if amount <= 0:
                raise ValidationError(
                    _("Invalid Vendor Bill amount for %s.")
                    % partner.name
                )

        # ------------------------------------------------------------------
        # Generate Unique Reference
        # ------------------------------------------------------------------

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
        _logger.info("ICICI CREATE API REQUEST")
        _logger.info(json.dumps(create_payload, indent=4))
        _logger.info("=" * 80)

        result = self.call_icici_api(
            "https://apibankingone.icici.bank.in/api/Corporate/CIB/v1/Create",
            create_payload,
        )

        response = (result.get("response") or "").strip()

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

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

        except Exception as exc:
            _logger.exception(
                "Unable to parse ICICI Create response."
            )

            raise ValidationError(
                _("Unable to parse ICICI Create API response.")
            ) from exc

        _logger.info("=" * 80)
        _logger.info("ICICI CREATE RESPONSE")
        _logger.info(
            json.dumps(response_json, indent=4)
        )
        _logger.info("=" * 80)

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

        vals = {
            "icici_reference": unique_id,
            "icici_payment_status": "otp_pending",
        }

        if otp:
            vals["icici_generated_otp"] = otp

        self.write(vals)

        if otp:
            _logger.info(
                "OTP received from ICICI Create API."
            )
        else:
            _logger.info(
                "OTP has been sent to the authorized ICICI user."
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("ICICI OTP Verification"),
            "res_model": "icici.otp.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_vendor_bill_ids": self.ids,
            },
        }    
    
    def generate_vendor_bill_file(self, payment_date):
        """Generate ICICI Vendor Bill File."""
        payment_date = fields.Date.to_date(
            payment_date
        ).strftime("%m/%d/%Y")

        debit_account = "693905601661"
        debit_branch = "0011"

        transaction_count = 0
        total_amount = 0.00
        detail_lines = []

        for slip in self:

            partner = slip.partner_id

            bank_account = partner.bank_ids.filtered(
                lambda account:
                    account.acc_number
                    and account.bank_id
                    and account.bank_id.bic
            )[:1]

            if not bank_account:
                raise ValidationError(
                    _("Bank account is missing for %s.")
                    % partner.name
                )

            account_number = (
                bank_account.acc_number or ""
            ).strip()

            if not account_number:
                raise ValidationError(
                    _("Account Number is missing for %s.")
                    % partner.name
                )

            if len(account_number) < 9:
                raise ValidationError(
                    _("Invalid Account Number for %s.")
                    % partner.name
                )

            ifsc = (
                bank_account.bank_id.bic or ""
            ).strip().upper()

            if len(ifsc) != 11:
                raise ValidationError(
                    _("Invalid IFSC Code for %s.")
                    % partner.name
                )

            amount = round(
                float(slip.amount_residual or 0.0),
                2,
            )

            if amount <= 0:
                raise ValidationError(
                    _("Invalid vendor bill amount for %s.")
                    % partner.name
                )

            transaction_count += 1
            total_amount += amount

            if ifsc.startswith("ICIC"):
                transaction_type = "MCW"
                network = "WIB"
                branch_code = "0011"
                beneficiary_ifsc = "ICIC0000011"
            else:
                transaction_type = "MCO"
                network = "NFT"
                branch_code = "0011"
                beneficiary_ifsc = ifsc

            partner_name = " ".join(
                partner.name.split()
            )[:35]

            detail_lines.append(
                "|".join([
                    transaction_type,
                    account_number,
                    branch_code,
                    partner_name,
                    f"{amount:.2f}",
                    "INR",
                    "Vendor Bill",
                    network,
                    beneficiary_ifsc,
                ]) + "^"
            )

            _logger.info(
                "Partner : %s | Type : %s | Amount : %.2f | IFSC : %s",
                partner.name,
                transaction_type,
                amount,
                beneficiary_ifsc,
            )

        if transaction_count == 0:
            raise ValidationError(
                _("No valid Vendor Bill found.")
            )
        total_records = transaction_count + 1

        header = (
            f"FHR|{total_records}|"
            f"{payment_date}|"
            f"VENDOR_BILL|"
            f"{total_amount:.2f}|"
            f"INR|"
            f"{debit_account}|"
            f"{debit_branch}^"
        )

        maker = (
            f"MDR|"
            f"{debit_account}|"
            f"{debit_branch}|"
            f"VENDOR_BILL|"
            f"{total_amount:.2f}|"
            f"INR|"
            f"Vendor Bill Batch|"
            f"ICIC0000011|"
            f"WIB^"
        )

        expense_file = "\r\n".join(
            [header, maker] + detail_lines
        )

        _logger.info("=" * 80)
        _logger.info("ICICI EXPENSE FILE GENERATED")
        _logger.info("\n%s", expense_file)
        _logger.info("=" * 80)

        return expense_file
    
    def action_check_transaction_status(self, file_seq_num):
        """Fetch transaction status from ICICI Reverse MIS API."""

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
            "paid",
            "failed",
        ):
            raise ValidationError(
                _("Transaction status can only be checked after salary processing has started.")
            )

        payload = {
            "AGGRID": "BULK0173",
            "CORPID": "601902129",
            "USERID": "601902129.BALCHAND",
            "URN": "SR283346233",
            "FILESEQNUM": file_seq_num,
            "UNIQUEID": self.icici_reference,
            "ISENCRYPTED": "N",
        }

        _logger.info("=" * 80)
        _logger.info("ICICI REVERSE MIS REQUEST")
        _logger.info(json.dumps(payload, indent=4))
        _logger.info("=" * 80)

        result = self.call_icici_api(
            "https://apibankingone.icici.bank.in/api/v1/ReverseMis",
            payload,
        )

        response = (result.get("response") or "").strip()

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

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
            response_json = json.loads(
                clean_response
            )

        except Exception as exc:

            _logger.exception(
                "Unable to parse Reverse MIS response."
            )

            raise ValidationError(
                _("Unable to parse ICICI response.")
            ) from exc

        self.write({
            "icici_response": json.dumps(
                response_json,
                indent=4,
            )
        })

        _logger.info("=" * 80)
        _logger.info("ICICI REVERSE MIS RESPONSE")
        _logger.info(
            json.dumps(
                response_json,
                indent=4,
            )
        )
        _logger.info("=" * 80)

        xml_data = response_json.get("XML")
        if not xml_data:
            raise ValidationError(
                _("XML data not found in ICICI response.")
            )
        if isinstance(xml_data, str):
            try:
                xml_data = json.loads(xml_data)
            except Exception:
                raise ValidationError(
                    _("Invalid XML section received from ICICI.")
                )

        response_status = (
            xml_data.get("RESPONSE")
            or ""
        ).upper()

        if response_status != "SUCCESS":
            raise ValidationError(
                xml_data.get("MESSAGE")
                or _("ICICI returned an unsuccessful response.")
            )

        file_status = (
            xml_data.get("FILE_STATUS")
            or ""
        ).upper()

        records = (
            xml_data.get(
                "FILEUPLOAD_BINARY_OUTPUT",
                {}
            ).get(
                "Records",
                {}
            )
        )
        payment_status = "processing"
        utr = False

        # File has been processed successfully.
        # Actual payment status is determined from transaction records.
        if file_status == "STS":
            payment_status = "processing"

        elif file_status in ("PPD",):
            payment_status = "paid"

        elif file_status in ("FAL", "REC", "REJ"):
            payment_status = "failed"

        else:
            payment_status = "processing"

        if (
            records
            and isinstance(records, dict)
            and records.get("Record")
        ):

            record_lines = records.get("Record")

            if isinstance(record_lines, str):
                record_lines = [record_lines]

            for line in record_lines[1:]:

                columns = line.split("|")

                if len(columns) < 12:
                    continue

                host_reference = columns[7]
                response_code = columns[8]
                response_message = columns[9]
                remarks = columns[10]
                transaction_status = columns[11]

                _logger.info(
                    "Transaction Status : %s",
                    transaction_status,
                )

                _logger.info(
                    "Host Response : %s - %s",
                    response_code,
                    response_message,
                )

                transaction_status = transaction_status.upper()
                if transaction_status == "SUC":
                    payment_status = "paid"
                    utr = host_reference

                elif transaction_status in ("FAL", "FAIL"):
                    payment_status = "failed"

                else:
                    payment_status = "processing"

        self.write({
            "icici_payment_status": payment_status,
            "icici_utr": utr,
        })

        _logger.info("=" * 80)
        _logger.info("FILE STATUS : %s", file_status)
        _logger.info("ODOO STATUS : %s", payment_status)
        _logger.info("UTR : %s", utr)
        _logger.info("=" * 80)

        return True
    
    def process_bulk_payment(self, otp, payment_date):
        """Submit salary file to ICICI after OTP verification."""

        if not self:
            raise ValidationError(
                _("No Vendors selected.")
            )

        otp = (otp or "").strip()

        if not otp:
            raise ValidationError(
                _("Please enter the OTP.")
            )

        for slip in self:

            if slip.icici_payment_status != "otp_pending":
                raise ValidationError(
                    _(
                        "Vendor bill payment is not awaiting OTP for %s."
                    )
                    % slip.partner_id.name
                )

            if not slip.icici_reference:
                raise ValidationError(
                    _(
                        "ICICI Reference is missing for %s."
                    )
                    % slip.partner_id.name
                )

        vendor_file = self.generate_expense_file(
            payment_date
        )

        encoded_file = base64.b64encode(
            vendor_file.encode("utf-8")
        ).decode("utf-8")

        payload = {
            "FILE_DESCRIPTION": "Vendor Bill Payment",
            "AGGR_ID": "BULK0173",
            "URN": "SR283346233",
            "AGGR_NAME": "BXITECH",
            "USER_ID": "BALCHAND",
            "CORP_ID": "601902129",
            "UNIQUE_ID": self[0].icici_reference,
            "AGOTP": otp,
            "FILE_NAME": (
                f"VENDOR_BILL_"
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
            ),
            "FILE_CONTENT": encoded_file,
        }

        _logger.info("=" * 80)
        _logger.info("ICICI BULK PAYMENT REQUEST")
        _logger.info(
            json.dumps(payload, indent=4)
        )
        _logger.info("=" * 80)

        result = self.call_icici_api(
            "https://apibankingone.icici.bank.in/api/v1/cibbulkpayment/bulkPayment",
            payload,
        )

        response = (
            result.get("response") or ""
        ).strip()

        if not response:
            raise ValidationError(
                _("Empty response received from ICICI.")
            )

        json_start = response.find("{")
        json_end = response.rfind("}")

        if json_start == -1 or json_end == -1:
            raise ValidationError(
                _(
                    "Invalid response received from ICICI.\n\n%s"
                )
                % response
            )

        clean_response = response[
            json_start: json_end + 1
        ]

        try:

            response_json = json.loads(
                clean_response
            )

        except Exception as exc:

            _logger.exception(
                "Unable to parse ICICI Bulk Payment response."
            )

            raise ValidationError(
                _(
                    "Unable to parse ICICI Bulk Payment response."
                )
            ) from exc

        _logger.info("=" * 80)
        _logger.info("ICICI BULK PAYMENT RESPONSE")
        _logger.info(
            json.dumps(
                response_json,
                indent=4,
            )
        )
        _logger.info("=" * 80)

        response_status = (
            response_json.get("RESPONSE")
            or response_json.get("Response")
            or response_json.get("response")
            or response_json.get("status")
            or response_json.get("Status")
            or ""
        ).strip().upper()

        message = (
            response_json.get("MESSAGE_DESC")
            or response_json.get("MESSAGE")
            or response_json.get("Message")
            or response_json.get("message")
            or ""
        )

        is_success = (
            response_status == "SUCCESS"
            or "SUCCESSFULLY" in message.upper()
            or "SUCCESS" in message.upper()
        )

        if not is_success:
            raise ValidationError(
                message or _("ICICI Bulk Payment failed.")
            )

        file_sequence = (
            response_json.get("FILE_SEQUENCE_NUM")
            or response_json.get("FILESEQNUM")
            or ""
        )

        if not file_sequence and message:
            import re
            match = re.search(r"File Sequence\s*(?:No|Number)?\s*:\s*\[?(\d+)\]?", message, re.IGNORECASE)
            if match:
                file_sequence = match.group(1)

        utr = (
            response_json.get("UTR")
            or response_json.get("UTR_NUMBER")
            or ""
        )

        self.write({
            "icici_payment_status": "processing",
            "icici_generated_otp": False,
            "icici_file_seq_num": file_sequence,
            "icici_utr": utr,
            "icici_response": json.dumps(
                response_json,
                indent=4,
            ),
        })

        _logger.info("=" * 80)
        _logger.info(
            "ICICI BULK PAYMENT SUBMITTED SUCCESSFULLY"
        )
        _logger.info(
            "FILE SEQUENCE : %s",
            file_sequence,
        )
        _logger.info(
            "UTR : %s",
            utr,
        )
        _logger.info("=" * 80)

        return True


    def action_open_transaction_status_wizard(self):
        """Open ICICI Transaction Status Wizard."""

        self.ensure_one()

        if self.icici_payment_status not in (
            "processing",
            "paid",
            "failed",
        ):
            raise ValidationError(
                _(
                    "Transaction status can only be checked after vendor bill processing has started."
                )
            )

        if not self.icici_file_seq_num:
            raise ValidationError(
                _("File Sequence Number is not available.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Transaction Status"),
            "res_model": "icici.transaction.status.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_vendor_bill_id": self.id,
                "default_file_seq_num": self.icici_file_seq_num,
            },
        }