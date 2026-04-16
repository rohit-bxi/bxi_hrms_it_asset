from odoo import fields, models
from odoo.exceptions import UserError
import json
import logging
import requests
_logger = logging.getLogger(__name__)


class HrHire(models.Model):
    _inherit = 'hr.applicant'
    _description = "HR Applicant Extension for Offer Letter"

    first_interview_remark = fields.Text(
        string="First Interview Remark",
        tracking=True,
        help="Feedback provided by the interviewer during the first interview."
    )

    second_interview_remark = fields.Text(
        string="Second Interview Remark",
        tracking=True,
        help="Feedback provided by the interviewer during the second interview."
    )

    # frontend_webhook_url = fields.Char(
    #     string="Frontend Webhook URL",
    #     help="Webhook URL to notify the frontend when a candidate is selected."
    # )
    #
    # notification_sent = fields.Boolean(
    #     string="Notification Sent",
    #     default=False,
    #     readonly=True
    # )

    father_name = fields.Char("Father Name")
    mother_name = fields.Char("Mother Name")
    contact_number = fields.Char("Contact Number")
    aadhar_number = fields.Char("Aadhar Number")
    pan_number = fields.Char("PAN Number")
    full_address = fields.Text("Full Address")
    joining_date = fields.Date(string="Joining Date")

    # Offer Letter Status
    offer_letter_generated = fields.Boolean(
        string="Offer Letter Generated",
        default=False,
        tracking=True
    )

    # Documents
    doc_10th = fields.Binary("10th Marksheet")
    doc_12th = fields.Binary("12th Marksheet")
    doc_graduation = fields.Binary("Graduation Certificate")
    doc_master = fields.Binary("Master Degree Certificate")

    # Other Documents
    form_16 = fields.Binary("Form 16")
    bank_statement = fields.Binary("Bank Statement")
    salary_slip = fields.Binary("Last 3 Month Salary Slip")
    photograph = fields.Binary("Photograph")

    # Experience
    experience_ids = fields.One2many(
        'hr.applicant.experience',
        'applicant_id',
        string="Experience"
    )

    # def _send_selection_notification(self):
    #     """Send notification to frontend for selected candidates."""
    #     for record in self:
    #         # Ensure the candidate is selected (hired)
    #         if not record.stage_id or not record.stage_id.hired_stage:
    #             raise UserError(
    #                 _("Notification can only be sent for selected candidates.")
    #             )
    #
    #         if not record.frontend_webhook_url:
    #             raise UserError(_("Please configure the Frontend Webhook URL."))
    #
    #         payload = {
    #             "applicant_id": record.id,
    #             "candidate_name": record.partner_name or record.name,
    #             "email": record.email_from,
    #             "job_position": record.job_id.name if record.job_id else "",
    #             "status": "selected",
    #         }
    #
    #         headers = {"Content-Type": "application/json"}
    #
    #         try:
    #             response = requests.post(
    #                 record.frontend_webhook_url,
    #                 data=json.dumps(payload),
    #                 headers=headers,
    #                 timeout=10
    #             )
    #
    #             if response.status_code in [200, 201]:
    #                 record.notification_sent = True
    #                 _logger.info(
    #                     "Selection notification sent for applicant ID %s",
    #                     record.id
    #                 )
    #             else:
    #                 raise UserError(
    #                     _("Failed to send notification. Response: %s")
    #                     % response.text
    #                 )
    #
    #         except Exception as e:
    #             _logger.error("Notification Error: %s", str(e))
    #             raise UserError(_("Error sending notification: %s") % str(e))
    #
    # def action_send_selection_notification(self):
    #     """Button action to send notification."""
    #     self._send_selection_notification()

    # ---------------------------------------------------------
    # OFFER LETTER ACTIONS
    # ---------------------------------------------------------
    def action_generate_offer_letter(self):
        """Generate Offer Letter"""
        self.ensure_one()
        if not self.partner_name:
            raise UserError(_("Please enter Full Name."))

        self.offer_letter_generated = True
        return self.env.ref(
            'bxi_hr_recruitment.action_report_offer_letter'
        ).report_action(self)

    def action_view_offer_letter(self):
        """View Offer Letter"""
        self.ensure_one()
        if not self.offer_letter_generated:
            raise UserError(_("Please generate the offer letter first."))
        return self.env.ref(
            'bxi_hr_recruitment.action_report_offer_letter'
        ).report_action(self)

    # ---------------------------------------------------------
    # SEND EMAIL ON STAGE CHANGE
    # ---------------------------------------------------------
    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     if 'stage_id' in vals:
    #         template = self.env.ref(
    #             'bxi_hr_recruitment.email_template_applicant_stage',
    #             raise_if_not_found=False
    #         )
    #
    #         for rec in self:
    #             if template and rec.email_from:
    #                 template.send_mail(rec.id, force_send=True)
    #
    #     return res
    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            template = self.env.ref(
                'bxi_hr_recruitment.email_template_applicant_stage',
                raise_if_not_found=False
            )
            for rec in self:
                if template:
                    template.send_mail(rec.id, force_send=True)

                # Auto-generate offer letter when hired
                if rec.stage_id.name == 'Hired':
                    rec.offer_letter_generated = True
        return res


class HrApplicantExperience(models.Model):
    _name = 'hr.applicant.experience'
    _description = 'Applicant Experience'

    applicant_id = fields.Many2one('hr.applicant')
    company_name = fields.Many2one('res.company', string='Company Name')
    years = fields.Float("Years")
    experience_certificate = fields.Binary(
        "Experience Certificate", attachment=True
    )
    experience_certificate_filename = fields.Char()

    joining_letter = fields.Binary(
        "Joining Letter", attachment=True
    )
    joining_letter_filename = fields.Char()

    relieving_letter = fields.Binary(
        "Relieving Letter", attachment=True
    )
    relieving_letter_filename = fields.Char()

    other_certificate = fields.Binary(
        "Other Certificate", attachment=True
    )
    other_certificate_filename = fields.Char()
