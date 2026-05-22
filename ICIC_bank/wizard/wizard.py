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

        # ==========================================
        # VALIDATIONS
        # ==========================================

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

        total_amount = 0

        salary_lines = []

        # ==========================================
        # VALIDATE EMPLOYEES
        # ==========================================

        for slip in slips:

            employee = slip.employee_id

            bank_account_rec = (
                employee.bank_account_ids.filtered(
                    lambda b: b.acc_number
                )[:1]
            )

            if not bank_account_rec:

                raise ValidationError(
                    f'Employee bank account missing '
                    f'for {employee.name}'
                )

            bank_account = (
                bank_account_rec.acc_number
            )

            amount = int(slip.net_wage)

            if amount <= 0:

                raise ValidationError(
                    f'Invalid salary amount '
                    f'for {employee.name}'
                )

            total_amount += amount

        # ==========================================
        # DATE
        # ==========================================

        today_date = datetime.today().strftime(
            '%d/%m/%Y'
        )

        # ==========================================
        # FILE HEADER
        # ==========================================

        salary_lines.append(
            f'FHR|7|{today_date}|salarybatch|'
            f'{total_amount}|INR|000451000301|0011^'
        )

        # ==========================================
        # MDR
        # ==========================================

        salary_lines.append(
            f'MDR|000451000301|0011|salary|'
            f'{total_amount}|INR|salary|'
            f'ICIC0000011|WIB^'
        )

        # ==========================================
        # EMPLOYEE LINES
        # ==========================================

        for slip in slips:

            employee = slip.employee_id

            bank_account = (
                employee.bank_account_ids.filtered(
                    lambda b: b.acc_number
                )[:1].acc_number
            )

            amount = int(slip.net_wage)

            salary_lines.append(
                f'MCW|{bank_account}|0411|'
                f'{employee.name}|{amount}|INR|'
                f'Salary|ICIC0000011|WIB^'
            )

        # ==========================================
        # FINAL FILE
        # ==========================================

        salary_file = '\n'.join(
            salary_lines
        )

        _logger.info(
            'ICICI BULK SALARY FILE: %s',
            salary_file
        )

        encoded_file = base64.b64encode(
            salary_file.encode()
        ).decode()

        # ==========================================
        # FILE NAME
        # ==========================================

        file_name = (
            f'salary_batch_'
            f'{datetime.today().strftime("%Y%m%d%H%M%S")}.txt'
        )

        # ==========================================
        # BULK PAYMENT PAYLOAD
        # ==========================================

        payload = {
            'FILE_DESCRIPTION': 'PAYROLL',
            'AGGR_ID': 'CIBBULK001',
            'URN': 'CIBTESTING',
            'AGGR_NAME': 'BULKTESTING',
            'USER_ID': 'USER2',
            'CORP_ID': 'TXBCORP2',
            'UNIQUE_ID': str(
                random.randint(10000, 99999)
            ),
            'AGOTP': self.otp,
            'FILE_NAME': file_name,
            'FILE_CONTENT': encoded_file
        }

        url = (
            'https://apibankingonesandbox.icici.bank.in'
            '/api/v1/cibbulkpayment_sv/bulkPayment'
        )

        try:

            result = slips[0].call_icici_api(
                url,
                payload
            )

            response = result.get(
                'response'
            )

            _logger.info(
                'ICICI BULK PAYMENT RESPONSE: %s',
                response
            )

            # ======================================
            # FAILURE
            # ======================================

            if result.get('status_code') != 200:

                slips.write({
                    'icici_payment_status': 'failed',
                    'icici_response': response
                })

                raise ValidationError(
                    response
                )

            # ======================================
            # RESPONSE JSON
            # ======================================

            response_json = json.loads(
                response
            )

            response_code = response_json.get(
                'ResponseCode'
            )

            # ======================================
            # SUCCESS
            # ======================================

            if response_code == '0000':

                file_seq_num = response_json.get(
                    'FILESEQNUM'
                )

                utr = response_json.get(
                    'UTR'
                )

                slips.write({
                    'icici_payment_status': 'processing',
                    'icici_response': response,
                    'icici_file_seq_num': file_seq_num,
                    'icici_reference': utr,
                    'icici_generated_otp': False
                })

            else:

                slips.write({
                    'icici_payment_status': 'failed',
                    'icici_response': response
                })

                raise ValidationError(
                    response_json.get(
                        'Message',
                        'ICICI Payment Failed'
                    )
                )

            # ======================================
            # RELOAD
            # ======================================

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        except Exception as e:

            slips.write({
                'icici_payment_status': 'failed'
            })

            _logger.exception(
                'ICICI BULK PAYMENT ERROR'
            )

            raise ValidationError(
                str(e)
            )