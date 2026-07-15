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
        """Submit Bulk Payment after OTP verification."""

        self.ensure_one()

        if not self.payslip_ids:
            raise ValidationError(
                _("No payslips selected.")
            )

        otp = (self.otp or "").strip()

        if not otp:
            raise ValidationError(
                _("Please enter the OTP.")
            )

        if not self.payment_date:
            raise ValidationError(
                _("Please select the Payment Date.")
            )

        # ------------------------------------------------------
        # Validate Payslips
        # ------------------------------------------------------

        for slip in self.payslip_ids:

            if slip.icici_payment_status != "otp_pending":
                raise ValidationError(
                    _(
                        "%s is not waiting for OTP confirmation."
                    )
                    % slip.employee_id.name
                )

            if not slip.icici_reference:
                raise ValidationError(
                    _(
                        "ICICI Reference is missing for %s."
                    )
                    % slip.employee_id.name
                )

        _logger.info("=" * 80)
        _logger.info("ICICI OTP VERIFIED")
        _logger.info("Payment Date : %s", self.payment_date)
        _logger.info("Payslips : %s", self.payslip_ids.ids)
        _logger.info("=" * 80)

        try:

            self.payslip_ids.process_bulk_payment(
                otp,
                self.payment_date,
            )

            _logger.info(
                "ICICI Bulk Payment submitted successfully."
            )

            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        except ValidationError:
            raise

        except Exception as exc:

            _logger.exception(
                "Unexpected ICICI Bulk Payment Error."
            )

            raise ValidationError(
                _(
                    "An unexpected error occurred while processing the salary payment."
                )
            ) from exc


class IciciTransactionStatusWizard(models.TransientModel):
    _name = "icici.transaction.status.wizard"
    _description = "ICICI Transaction Status Wizard"

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

    def action_check_status(self):
        """Fetch ICICI Transaction Status."""

        self.ensure_one()

        if not self.payslip_id:
            raise ValidationError(
                _("Payslip not found.")
            )

        if not self.file_seq_num:
            raise ValidationError(
                _("File Sequence Number is required.")
            )

        if self.payslip_id.icici_payment_status not in (
            "processing",
            "paid",
            "failed",
        ):
            raise ValidationError(
                _(
                    "Transaction status can only be checked after salary processing has started."
                )
            )

        _logger.info("=" * 80)
        _logger.info(
            "ICICI TRANSACTION STATUS CHECK STARTED"
        )
        _logger.info(
            "Payslip : %s",
            self.payslip_id.display_name,
        )
        _logger.info(
            "File Sequence Number : %s",
            self.file_seq_num,
        )
        _logger.info("=" * 80)

        try:

            self.payslip_id.action_check_transaction_status(
                self.file_seq_num
            )

            _logger.info(
                "ICICI Transaction Status fetched successfully."
            )

            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        except ValidationError:
            raise

        except Exception as exc:

            _logger.exception(
                "Unexpected ICICI Transaction Status Error."
            )

            raise ValidationError(
                _(
                    "An unexpected error occurred while fetching the transaction status."
                )
            ) from exc