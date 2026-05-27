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
                self.otp
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