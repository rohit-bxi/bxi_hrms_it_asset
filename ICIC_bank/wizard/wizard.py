from odoo import models, fields
from odoo.exceptions import ValidationError

import base64
import logging
import json
import random

from datetime import datetime


_logger = logging.getLogger(__name__)


class ICICIOtpWizard(models.TransientModel):
    _name = 'icici.otp.wizard'
    _description = 'ICICI OTP Wizard'

    otp = fields.Char(
        string='OTP',
        required=True
    )

    payslip_ids = fields.Many2many(
        'hr.payslip',
        string='Payslips',
        required=True
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today
    )

    def action_confirm_otp(self):

        self.ensure_one()

        try:
            self.payslip_ids.process_bulk_payment(
                self.otp,
                self.payment_date
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        except Exception as e:
            _logger.exception(
                'ICICI BULK PAYMENT ERROR'
            )
            raise ValidationError(str(e))
        
class IciciReverseWizard(models.TransientModel):
    _name = 'icici.reverse.wizard'
    _description = 'ICICI Reverse Payment'

    payslip_id = fields.Many2one(
        'hr.payslip',
        required=True
    )

    file_seq_num = fields.Char(
        string="File Sequence Number",
        required=True,
        default=lambda self: self.env.context.get('default_file_seq_num')
    )

    def action_reverse(self):
        self.ensure_one()

        payload = {
            "AGGRID": "CIBBULK001",
            "CORPID": "TXBCORP1",
            "USERID": "TXBCORP1.USER1",
            "URN": "CIBTESTING",
            "FILESEQNUM": self.file_seq_num,
            "UNIQUEID": self.payslip_id.icici_unique_id,
            "ISENCRYPTED": "N"
        }
        _logger.info(
            "PAYMENT UNIQUE_ID = %s",
            self.payslip_id.icici_unique_id
        )

        result = self.payslip_id.call_icici_api(
            "https://apibankingonesandbox.icici.bank.in/api/v1/ReverseMis_sv",
            payload
        )

        response = result.get("response")

        if not response:
            raise ValidationError("Empty response from ICICI.")

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            response_json = json.loads(
                response[json_start:json_end]
            )

        except Exception:
            raise ValidationError(response)

        _logger.info(
            "ICICI REVERSE RESPONSE: %s",
            response_json
        )
        if response_json.get("Response") != "Success":
            raise ValidationError(
                response_json.get(
                    "Message",
                    "Reverse failed"
                )
            )

        self.payslip_id.write({
            'icici_payment_status': 'reversed',
            'icici_response': response,
            'icici_generated_otp': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }