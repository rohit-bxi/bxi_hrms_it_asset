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

        for slip in self.payslip_ids:

            if slip.icici_payment_status == "paid":
                raise ValidationError(
                    _("Salary has already been released for %s.")
                    % slip.employee_id.name
                )

            if not slip.icici_generated_otp:
                raise ValidationError(
                    _("OTP has not been generated for %s.")
                    % slip.employee_id.name
                )

            if self.otp != slip.icici_generated_otp:
                raise ValidationError(
                    _("Invalid OTP.")
                )

        try:
            self.payslip_ids.process_bulk_payment(
                self.otp,
                self.payment_date,
            )

            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        except ValidationError:
            raise

        except Exception as exc:
            _logger.exception(
                "Unexpected ICICI bulk payment error: %s",
                exc,
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

        return self.payslip_id.action_reverse_payment(
            self.file_seq_num
        )