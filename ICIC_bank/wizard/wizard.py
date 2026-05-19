from odoo import models, fields
from odoo.exceptions import ValidationError

import base64
import logging


_logger = logging.getLogger(__name__)


class ICICIOtpWizard(models.TransientModel):
    _name = 'icici.otp.wizard'
    _description = 'ICICI OTP Wizard'

    otp = fields.Char(
        string='OTP',
        required=True
    )

    payslip_id = fields.Many2one(
        'hr.payslip',
        required=True
    )

    def action_confirm_otp(self):

        self.ensure_one()

        slip = self.payslip_id

        if slip.icici_payment_status == 'paid':
            raise ValidationError(
                'Salary already released.'
            )

        employee = slip.employee_id

        bank_account_rec = employee.bank_account_ids[:1]

        if not bank_account_rec:
            raise ValidationError(
                'Employee bank account missing.'
            )

        bank_account = bank_account_rec.acc_number

        if not bank_account:
            raise ValidationError(
                'Employee account number missing.'
            )

        amount = int(slip.net_wage)

        if amount <= 0:
            raise ValidationError(
                'Invalid salary amount.'
            )

        salary_file = f'''
FHR|7|05/07/2025|salarybatch|{amount}|INR|000451000301|0011^
MDR|000451000301|0011|salary|{amount}|INR|salary|ICIC0000011|WIB^
MCW|{bank_account}|0411|{employee.name}|{amount}|INR|Salary|ICIC0000011|WIB^
'''.strip()

        _logger.info(
            'ICICI SALARY FILE: %s',
            salary_file
        )

        encoded_file = base64.b64encode(
            salary_file.encode()
        ).decode()

        payload = {
            'FILE_DESCRIPTION': 'PAYROLL',
            'AGGR_ID': 'CIBBULK001',
            'URN': 'CIBTESTING',
            'AGGR_NAME': 'BULKTESTING',
            'USER_ID': 'USER2',
            'CORP_ID': 'TXBCORP2',
            'UNIQUE_ID': str(slip.id),
            'AGOTP': self.otp,
            'FILE_NAME': 'salary.txt',
            'FILE_CONTENT': encoded_file
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/v1/cibbulkpayment_sv/bulkPayment'
        )

        try:

            result = slip.call_icici_api(
                url,
                payload
            )

            response = result.get('response')

            slip.icici_response = response

            _logger.info(
                'ICICI BULK PAYMENT RESPONSE: %s',
                response
            )

            if result.get('status_code') == 200:

                slip.icici_payment_status = 'paid'

            else:

                slip.icici_payment_status = 'failed'

                raise ValidationError(
                    response
                )

        except Exception as e:

            slip.icici_payment_status = 'failed'

            _logger.exception(
                'ICICI BULK PAYMENT ERROR'
            )

            raise ValidationError(
                str(e)
            )