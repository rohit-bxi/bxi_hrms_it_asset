from odoo import _, fields, models
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ICICIOtpWizard(models.TransientModel):
    _name = "icici.otp.wizard"
    _description = "ICICI OTP Verification Wizard"

    otp = fields.Char(
        string="OTP",
        required=True,
        copy=False,
    )

    payslip_ids = fields.Many2many(
        "hr.payslip",
        string="Payslips",
        required=True,
        readonly=True,
    )

    payment_date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.today,
        copy=False,
    )

    def action_confirm_otp(self):
        self.ensure_one()

        if not self.payslip_ids:
            raise ValidationError(
                _("No payslips selected.")
            )

        if not self.otp or not self.otp.strip():
            raise ValidationError(
                _("Please enter the OTP.")
            )

        for slip in self.payslip_ids:

            if slip.icici_payment_status == "paid":
                raise ValidationError(
                    _("Salary has already been released for %s.")
                    % slip.employee_id.name
                )

            if slip.icici_payment_status == "processing":
                raise ValidationError(
                    _("Salary payment is already under processing for %s.")
                    % slip.employee_id.name
                )

            if slip.icici_payment_status == "reversed":
                raise ValidationError(
                    _("Salary payment has already been reversed for %s.")
                    % slip.employee_id.name
                )

            if not slip.icici_reference:
                raise ValidationError(
                    _("ICICI Reference is missing for %s.")
                    % slip.employee_id.name
                )

        try:
            self.payslip_ids.process_bulk_payment(
                self.otp.strip(),
                self.payment_date,
            )

            _logger.info(
                "ICICI bulk payment submitted successfully."
            )

            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        except ValidationError:
            raise

        except Exception:
            _logger.exception(
                "Unexpected ICICI bulk payment error."
            )

            raise ValidationError(
                _(
                    "An unexpected error occurred while processing the ICICI payment. Please contact your administrator."
                )
            )


class IciciReverseWizard(models.TransientModel):
    _name = "icici.reverse.wizard"
    _description = "ICICI Reverse Payment Wizard"

    payslip_id = fields.Many2one(
        "hr.payslip",
        string="Payslip",
        required=True,
        readonly=True,
    )

    file_seq_num = fields.Char(
        string="File Sequence Number",
        required=True,
        readonly=True,
    )

    def action_reverse(self):
        self.ensure_one()

        if not self.payslip_id:
            raise ValidationError(
                _("Payslip not found.")
            )

        if not self.file_seq_num:
            raise ValidationError(
                _("File Sequence Number is required.")
            )

        if self.payslip_id.icici_payment_status != "processing":
            raise ValidationError(
                _("Only payments in Processing state can be reversed.")
            )

        try:
            self.payslip_id.action_reverse_payment(
                self.file_seq_num
            )

            _logger.info(
                "ICICI reverse payment completed successfully."
            )

            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        except ValidationError:
            raise

        except Exception:
            _logger.exception(
                "Unexpected ICICI reverse payment error."
            )

            raise ValidationError(
                _(
                    "An unexpected error occurred while reversing the payment. Please contact your administrator."
                )
            )