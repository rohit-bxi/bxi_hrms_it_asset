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
        slips = self.payslip_ids
        if not slips:
            raise ValidationError(
                'No payslips selected.'
            )
        for slip in slips:
            if slip.icici_payment_status == 'paid':
                raise ValidationError(
                    f'Salary already released for '
                    f'{slip.employee_id.name}'
                )
            if not slip.icici_generated_otp:

                raise ValidationError(
                    f'No OTP generated for '
                    f'{slip.employee_id.name}'
                )

            if self.otp != slip.icici_generated_otp:

                raise ValidationError(
                    'Invalid OTP.'
                )

        try:
            slips.process_bulk_payment(
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
            raise ValidationError(
                str(e)
            )
        
class IciciReverseWizard(models.TransientModel):
    _name = 'icici.reverse.wizard'
    _description = 'ICICI Reverse Payment'

    payslip_id = fields.Many2one(
        'hr.payslip',
        required=True
    )

    file_seq_num = fields.Char(
        string="File Sequence Number",
        required=True
    )

    def action_reverse(self):

        self.ensure_one()

        payload = {
            "AGGRID": "CIBBULK001",
            "CORPID": "TXBCORP1",
            "USERID": "TXBCORP1.USER1",
            "URN": "CIBTESTING",
            "FILESEQNUM": self.file_seq_num,
            "UNIQUEID": "797251",
            "ISENCRYPTED": "N"
        }

        _logger.info(
            "ICICI REVERSE PAYLOAD: %s",
            payload
        )

        url = (
            "https://apibankingonesandbox.icici.bank.in"
            "/api/v1/ReverseMis_sv"
        )

        result = self.payslip_id.call_icici_api(
            url,
            payload
        )

        response = result.get("response")

        if not response:
            raise ValidationError(
                "Empty response from ICICI."
            )

        self.payslip_id.icici_response = response

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            clean_response = response[
                json_start:json_end
            ]

            response_json = json.loads(
                clean_response
            )

        except Exception:
            raise ValidationError(response)

        _logger.info(
            "ICICI REVERSE RESPONSE: %s",
            response_json
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }